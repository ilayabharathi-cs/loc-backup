"""Streaming file uploader with integrity verification, change detection, and retry."""

import os
import time
import random
import datetime
from typing import Optional, Callable
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

from agent.src.backup.models import DiscoveredFile, FileUploadResult
from agent.src.backup.hashing import calculate_file_sha256, DEFAULT_HASH_CHUNK_SIZE
from agent.src.config import AgentConfig
from agent.src.logger import get_logger


class FileUploader:
    """Uploads discovered files to the server using streaming chunked transfers."""

    def __init__(self, config: AgentConfig, client_id: str, run_id: int):
        self.config = config
        self.client_id = client_id
        self.run_id = run_id
        self.base_url = config.server_url.rstrip("/")
        self.max_retries = config.max_retries
        self.timeout = config.request_timeout_seconds
        self.logger = get_logger()

    def upload_file(
        self,
        file_info: DiscoveredFile,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> FileUploadResult:
        """
        Stream a file to the server and verify integrity.
        progress_callback: called with chunk bytes for real-time progress.
        """
        file_path = file_info.original_path

        # 1. Check if file is accessible
        if not file_info.is_accessible:
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=file_path,
                size_bytes=0,
                status="locked",
                error_message=file_info.error_message or "File was inaccessible during scan"
            )

        # 2. Capture pre-upload stats for change-during-backup detection
        try:
            stat_before = os.stat(file_path)
            pre_size = stat_before.st_size
            pre_mtime = stat_before.st_mtime
        except (PermissionError, OSError) as e:
            self.logger.warning(f"File locked/inaccessible: '{file_path}': {e}")
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=file_path,
                size_bytes=0,
                status="locked",
                error_message=str(e)
            )

        # 3. Calculate streaming SHA-256
        try:
            sha256_hash, hashed_bytes = calculate_file_sha256(file_path)
        except (PermissionError, OSError) as e:
            self.logger.warning(f"Could not read file for hashing: '{file_path}': {e}")
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=file_path,
                size_bytes=0,
                status="locked",
                error_message=str(e)
            )

        # 4. Check for changes during hashing
        try:
            stat_after_hash = os.stat(file_path)
            if stat_after_hash.st_mtime != pre_mtime or stat_after_hash.st_size != pre_size:
                self.logger.warning(f"File changed during hashing: '{file_path}'")
                return FileUploadResult(
                    file_name=file_info.file_name,
                    original_path=file_path,
                    size_bytes=pre_size,
                    sha256=sha256_hash,
                    status="changed_during_backup",
                    error_message="File modified while calculating checksum"
                )
        except OSError:
            pass

        # 5. Perform streaming upload with retry
        attempt = 0
        backoff = 1.0
        upload_url = f"{self.base_url}/api/v1/backups/upload"

        # Prepare HTTP headers
        mtime_iso = datetime.datetime.fromtimestamp(pre_mtime, datetime.timezone.utc).isoformat()
        headers = {
            "User-Agent": f"RetroVault-Agent/{self.config.agent_version}",
            "X-Client-ID": self.client_id,
            "X-Run-ID": str(self.run_id),
            "X-Original-Path": file_path,
            "X-Relative-Path": file_info.relative_path,
            "X-SHA256": sha256_hash,
            "X-File-Size": str(pre_size),
            "X-Modified-Time": mtime_iso,
            "Content-Type": "application/octet-stream",
            "Content-Length": str(pre_size)
        }

        while attempt < self.max_retries:
            attempt += 1
            try:
                # Open and stream file
                with open(file_path, "rb") as f_in:
                    # Generator or direct stream
                    req = Request(upload_url, data=f_in, headers=headers, method="POST")
                    with urlopen(req, timeout=self.timeout) as resp:
                        resp_data = resp.read().decode("utf-8")
                        res_json = json.loads(resp_data) if resp_data else {}

                        if not res_json.get("success", False):
                            raise URLError(f"Server error: {res_json.get('error') or res_json.get('message')}")

                        if progress_callback:
                            progress_callback(pre_size)

                        return FileUploadResult(
                            file_name=file_info.file_name,
                            original_path=file_path,
                            size_bytes=pre_size,
                            sha256=sha256_hash,
                            status="uploaded",
                            retries=attempt - 1
                        )

            except HTTPError as e:
                err_text = ""
                try:
                    err_text = e.read().decode("utf-8")
                except Exception:
                    pass

                self.logger.warning(
                    f"Upload HTTP {e.code} for '{file_info.file_name}' (attempt {attempt}/{self.max_retries}): {err_text}"
                )
                if e.code in (400, 403, 404, 422) and attempt >= 2:
                    return FileUploadResult(
                        file_name=file_info.file_name,
                        original_path=file_path,
                        size_bytes=pre_size,
                        sha256=sha256_hash,
                        status="failed",
                        error_message=f"HTTP {e.code}: {err_text}",
                        retries=attempt
                    )

            except (URLError, TimeoutError, ConnectionError, OSError) as e:
                self.logger.warning(
                    f"Upload connection failure for '{file_info.file_name}' (attempt {attempt}/{self.max_retries}): {e}"
                )

            if attempt < self.max_retries:
                sleep_time = backoff + random.uniform(0.1, 0.4)
                time.sleep(sleep_time)
                backoff = min(backoff * 2.0, 16.0)

        return FileUploadResult(
            file_name=file_info.file_name,
            original_path=file_path,
            size_bytes=pre_size,
            sha256=sha256_hash,
            status="failed",
            error_message=f"Failed to upload after {self.max_retries} attempts.",
            retries=attempt
        )
