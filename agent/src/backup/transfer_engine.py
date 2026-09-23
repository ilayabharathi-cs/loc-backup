"""Reliable chunked resumable file transfer engine for RetroVault Agent V4."""

import os
import time
import hashlib
import threading
from typing import Optional, Callable, Dict, Any, Set
from dataclasses import dataclass

from agent.src.config import AgentConfig
from agent.src.api_client import BackendApiClient, ApiClientError
from agent.src.backup.models import DiscoveredFile, FileUploadResult
from agent.src.backup.hashing import calculate_file_sha256
from agent.src.backup.retry_engine import RetryEngine
from agent.src.backup.checkpoint_manager import CheckpointManager, BackupCheckpointData
from agent.src.windows.locked_files import LockedFileHandler, FileLockState
from agent.src.logger import get_logger


class TransferEngine:
    """
    Coordinates chunked resumable file uploads with server-side authority,
    idempotent chunk streaming, locked file handling, and crash checkpointing.
    """

    def __init__(
        self,
        config: AgentConfig,
        client_id: str,
        run_id: int,
        policy_id: Optional[int],
        api_client: BackendApiClient,
        checkpoint_manager: CheckpointManager,
        retry_engine: Optional[RetryEngine] = None,
        locked_file_handler: Optional[LockedFileHandler] = None
    ):
        self.config = config
        self.client_id = client_id
        self.run_id = run_id
        self.policy_id = policy_id
        self.api_client = api_client
        self.checkpoint_manager = checkpoint_manager
        self.retry_engine = retry_engine or RetryEngine(
            base_delay=1.0,
            max_delay=float(config.retry_backoff_max_seconds),
            factor=2.0
        )
        self.locked_file_handler = locked_file_handler or LockedFileHandler()
        self.logger = get_logger()

    def transfer_file(
        self,
        file_info: DiscoveredFile,
        change_type: str = "FULL",
        progress_callback: Optional[Callable[[int], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> FileUploadResult:
        """
        Transfer a single file to the repository using resumable chunks.
        Respects server-confirmed chunk authority, skipping already persisted chunks.
        """
        orig_path = file_info.original_path

        # 1. Inspect accessibility and locked state
        inspection = self.locked_file_handler.inspect_file(orig_path, file_info.relative_path)
        if inspection.state == FileLockState.LOCKED:
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=0,
                status="locked",
                error_message=inspection.error_message or "File is locked by another process"
            )
        elif inspection.state in (FileLockState.ACCESS_DENIED, FileLockState.NOT_FOUND):
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=0,
                status="failed",
                error_message=inspection.error_message or f"File inaccessible ({inspection.state.value})"
            )

        effective_path = inspection.effective_path
        file_size = inspection.size_bytes
        file_mtime = inspection.modified_time

        # 2. Compute full file checksum
        try:
            full_sha256, _ = calculate_file_sha256(effective_path)
        except Exception as e:
            self.logger.warning(f"Failed to calculate hash for '{effective_path}': {e}")
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=file_size,
                status="failed",
                error_message=f"Hashing error: {e}"
            )

        # 3. Verify file did not change during reading (CHANGED_DURING_BACKUP protection)
        if not self.locked_file_handler.verify_consistency_after_read(effective_path, file_size, file_mtime):
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=file_size,
                sha256=full_sha256,
                status="changed_during_backup",
                error_message="File modified while calculating checksum"
            )

        # 4. Initiate or query upload session on server
        mtime_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(file_mtime))
        try:
            session_data = self.retry_engine.execute_with_retry(
                lambda: self.api_client.create_upload_session(
                    run_id=self.run_id,
                    file_path=orig_path,
                    relative_path=file_info.relative_path,
                    total_size=file_size,
                    chunk_size=self.config.chunk_size,
                    change_type=change_type,
                    expected_sha256=full_sha256,
                    file_mtime=mtime_iso
                ),
                operation_name=f"Create upload session for '{file_info.file_name}'"
            )
        except Exception as e:
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=file_size,
                status="failed",
                error_message=f"Failed to create upload session: {e}"
            )

        session_id = session_data.get("upload_session_id") or session_data.get("session_id")
        chunk_size = session_data["chunk_size"]
        total_chunks = session_data["total_chunks"]

        # 5. SERVER AUTHORITY: Query server for confirmed persisted chunks
        try:
            status_data = self.retry_engine.execute_with_retry(
                lambda: self.api_client.get_upload_session_status(session_id),
                operation_name=f"Query upload session status for {session_id}"
            )
            confirmed_chunks: Set[int] = set(status_data.get("received_chunks") or status_data.get("confirmed_chunks") or [])
        except Exception as e:
            self.logger.warning(f"Could not retrieve server session status: {e}. Defaulting to empty.")
            confirmed_chunks = set()

        self.logger.info(
            f"Transferring '{file_info.file_name}' ({file_size} bytes, {total_chunks} chunks). "
            f"Server confirmed chunks: {len(confirmed_chunks)}/{total_chunks}."
        )

        # 6. Stream missing chunks
        bytes_uploaded = sum(chunk_size for c in confirmed_chunks if c < total_chunks - 1)
        if (total_chunks - 1) in confirmed_chunks:
            last_chunk_sz = file_size - ((total_chunks - 1) * chunk_size)
            bytes_uploaded += max(0, last_chunk_sz)

        try:
            with open(effective_path, "rb") as f:
                for chunk_idx in range(total_chunks):
                    if stop_event and stop_event.is_set():
                        self.logger.info(f"Transfer interrupted for '{file_info.file_name}' at chunk {chunk_idx}")
                        self._persist_checkpoint(
                            file_info=file_info,
                            session_id=session_id,
                            chunk_idx=chunk_idx,
                            bytes_uploaded=bytes_uploaded,
                            state="INTERRUPTED"
                        )
                        return FileUploadResult(
                            file_name=file_info.file_name,
                            original_path=orig_path,
                            size_bytes=file_size,
                            status="interrupted",
                            error_message="Backup was interrupted by stop signal"
                        )

                    # Skip already confirmed chunks (0 bytes uploaded over network!)
                    if chunk_idx in confirmed_chunks:
                        if progress_callback:
                            c_sz = chunk_size if chunk_idx < total_chunks - 1 else (file_size - (chunk_idx * chunk_size))
                            progress_callback(c_sz)
                        continue

                    # Read chunk bytes
                    offset = chunk_idx * chunk_size
                    f.seek(offset)
                    actual_read_size = chunk_size if chunk_idx < total_chunks - 1 else (file_size - offset)
                    chunk_bytes = f.read(actual_read_size)
                    chunk_sha = hashlib.sha256(chunk_bytes).hexdigest()

                    # Upload chunk with retry engine
                    self.retry_engine.execute_with_retry(
                        lambda c_idx=chunk_idx, c_data=chunk_bytes, c_hash=chunk_sha, c_off=offset: self.api_client.upload_chunk(
                            session_id=session_id,
                            chunk_index=c_idx,
                            chunk_bytes=c_data,
                            chunk_sha256=c_hash,
                            offset=c_off
                        ),
                        operation_name=f"Upload chunk {chunk_idx}/{total_chunks} for '{file_info.file_name}'"
                    )

                    confirmed_chunks.add(chunk_idx)
                    bytes_uploaded += len(chunk_bytes)
                    if progress_callback:
                        progress_callback(len(chunk_bytes))

                    # Persist local checkpoint
                    self._persist_checkpoint(
                        file_info=file_info,
                        session_id=session_id,
                        chunk_idx=chunk_idx,
                        bytes_uploaded=bytes_uploaded,
                        state="BACKING_UP"
                    )

        except Exception as e:
            self.logger.error(f"Error transferring chunks for '{file_info.file_name}': {e}")
            self._persist_checkpoint(
                file_info=file_info,
                session_id=session_id,
                chunk_idx=max(confirmed_chunks) if confirmed_chunks else 0,
                bytes_uploaded=bytes_uploaded,
                state="INTERRUPTED"
            )
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=file_size,
                status="failed",
                error_message=str(e)
            )

        # 7. Finalize upload session on server
        try:
            complete_res = self.retry_engine.execute_with_retry(
                lambda: self.api_client.complete_upload_session(
                    session_id=session_id,
                    final_sha256=full_sha256,
                    total_size=file_size
                ),
                operation_name=f"Complete upload session for '{file_info.file_name}'"
            )
            storage_obj = complete_res.get("storage_object")
        except Exception as e:
            return FileUploadResult(
                file_name=file_info.file_name,
                original_path=orig_path,
                size_bytes=file_size,
                status="failed",
                error_message=f"Failed to finalize session on server: {e}"
            )

        return FileUploadResult(
            file_name=file_info.file_name,
            original_path=orig_path,
            size_bytes=file_size,
            sha256=full_sha256,
            storage_object=storage_obj,
            status="vss_recovered" if inspection.is_vss_used else "uploaded"
        )

    def _persist_checkpoint(
        self,
        file_info: DiscoveredFile,
        session_id: str,
        chunk_idx: int,
        bytes_uploaded: int,
        state: str
    ) -> None:
        """Helper to atomically save local and server checkpoint."""
        try:
            cp_data = BackupCheckpointData(
                run_id=self.run_id,
                client_id=self.client_id,
                policy_id=self.policy_id,
                current_file=file_info.file_name,
                current_file_path=file_info.original_path,
                file_size=file_info.size_bytes,
                source_mtime=file_info.modified_time,
                change_type="FULL",
                upload_session_id=session_id,
                upload_object_id=None,
                bytes_uploaded=bytes_uploaded,
                bytes_verified=bytes_uploaded,
                last_successful_chunk=chunk_idx,
                retry_count=0,
                timestamp=time.time(),
                checkpoint_version=1,
                state=state
            )
            self.checkpoint_manager.save_checkpoint(cp_data)
        except Exception as e:
            self.logger.warning(f"Failed to write local checkpoint: {e}")
