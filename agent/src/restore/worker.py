import time
import os
import threading
from typing import Dict, Any
import urllib.request

from agent.src.logger import get_logger

class RestoreWorker:
    def __init__(self, config, identity, api_client, stop_event, poll_interval_seconds=10):
        self.config = config
        self.identity = identity
        self.api_client = api_client
        self.stop_event = stop_event
        self.poll_interval = poll_interval_seconds
        self.logger = get_logger()

    def run_loop(self):
        self.logger.info("Restore Worker polling started.")
        while not self.stop_event.is_set():
            try:
                self.poll_for_jobs()
            except Exception as e:
                self.logger.error(f"Error in RestoreWorker poll: {e}")
            
            # Wait for poll interval or stop event
            self.stop_event.wait(self.poll_interval)
            
    def poll_for_jobs(self):
        client_id = self.identity.client_id
        if not client_id:
            return
            
        try:
            res = self.api_client._make_request("GET", f"/agents/{client_id}/restore-jobs/pending")
            jobs = res.get("data", [])
        except Exception as e:
            self.logger.warning(f"Failed to poll restore jobs: {e}")
            return
            
        for job in jobs:
            self.process_job(job, client_id)
            
    def process_job(self, job: Dict[str, Any], client_id: str):
        job_id = job["id"]
        restore_id = job["restore_id"]
        target_path = job["target_path"]
        
        self.logger.info(f"Picked up pending restore job {restore_id}")
        
        # Report RUNNING
        try:
            self.api_client._make_request("POST", f"/agents/{client_id}/restore-jobs/{job_id}/status", {"status": "RUNNING"})
        except Exception:
            pass

        # Get items for the job
        try:
            res = self.api_client._make_request("GET", f"/restore/jobs/{restore_id}/items")
            items = res.get("data", [])
        except Exception as e:
            self.logger.error(f"Failed to fetch items for {restore_id}: {e}")
            self._update_status(client_id, job_id, "FAILED", error=str(e))
            return
            
        total = len(items)
        completed = 0
        failed = 0
        
        # Execute the restore
        for item in items:
            if self.stop_event.is_set():
                self._update_status(client_id, job_id, "CANCELLED")
                return

            try:
                dest = item["destination_path"]
                # Resolve the destination
                from agent.src.restore.path_validator import PathValidator
                
                # The backend already resolved the destination_path on the server side using the server's path_validator
                # But since it's the server's path_validator, it might have added /mnt/c/ or ~/Restored_Windows_Drive/
                # We should use the item's relative_path and the job's target_path!
                rel_path = item.get("relative_path")
                if not rel_path:
                    # fallback
                    rel_path = os.path.basename(dest)

                # Fix: Combine job's target_path with relative_path on the agent
                if target_path == "<ORIGINAL>":
                    final_dest = item.get("original_path") or dest
                else:
                    clean_rel = rel_path.replace('\\', '/').strip('/')
                    final_dest = os.path.join(target_path, clean_rel)

                os.makedirs(os.path.dirname(final_dest), exist_ok=True)
                
                # Download file
                file_id = item["backup_file_id"]
                if not file_id:
                    self.logger.warning(f"No backup_file_id for item {item['id']}")
                    failed += 1
                    continue
                    
                download_url = f"{self.api_client.base_url}/api/v1/restore/files/{file_id}/download"
                
                req = urllib.request.Request(download_url)
                token = self.api_client.credentials.get_auth_token()
                if token:
                    req.add_header("Authorization", f"Bearer {token}")
                    
                with urllib.request.urlopen(req, timeout=60) as resp, open(final_dest, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                
                completed += 1
            except Exception as e:
                self.logger.error(f"Failed to restore item {item.get('id')}: {e}")
                failed += 1
                
        # Final status
        status = "COMPLETED"
        if failed > 0:
            status = "PARTIAL"
        if failed == total and total > 0:
            status = "FAILED"
            
        self._update_status(client_id, job_id, status, completed, failed, total)
        self.logger.info(f"Finished restore job {restore_id} with status {status}")
        
    def _update_status(self, client_id, job_id, status, completed=0, failed=0, total=0, error=None):
        payload = {
            "status": status,
            "completed_files": completed,
            "failed_files": failed,
            "total_files": total
        }
        if total > 0:
            payload["progress_percent"] = (completed / total) * 100
        if error:
            payload["error_message"] = error
            
        try:
            self.api_client._make_request("POST", f"/agents/{client_id}/restore-jobs/{job_id}/status", payload)
        except Exception:
            pass

