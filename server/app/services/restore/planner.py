"""Restore Planner for RetroVault V6 Disaster Recovery Engine.

Handles:
1. Logical Recovery Point manifest reconstruction (inheriting incremental states, omitting DELETED files).
2. Virtual file tree representation for UI browsing and filtering.
3. Pre-flight restore preview without disk modification.
4. Validation of StorageObjects and paths.
"""

import os
from typing import Dict, List, Optional, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.recovery_point import RecoveryPoint
from app.models.backup_run import BackupRun
from app.models.backup_file import BackupFile
from app.models.storage_object import StorageObject
from app.services.restore.path_validator import PathValidator, PathSafetyError


class RestorePlanner:
    """Plans, inspects, and previews restore operations from Recovery Points."""

    @staticmethod
    def get_recovery_point_logical_files(db: Session, recovery_point_id: int) -> List[BackupFile]:
        """
        Reconstruct the exact logical manifest for a Recovery Point.
        Uses BackupFile records for the run. If incremental files inherited from parent runs
        are not all present in the immediate run, traverses backward through parent runs.
        Strictly excludes DELETED tombstone records.
        """
        rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
        if not rp:
            raise ValueError(f"Recovery Point {recovery_point_id} not found")

        current_run = db.query(BackupRun).filter(BackupRun.id == rp.backup_run_id).first()
        if not current_run:
            raise ValueError(f"BackupRun {rp.backup_run_id} for Recovery Point {recovery_point_id} not found")

        # Collect runs from newest (current) to oldest (initial full)
        runs_to_inspect = [current_run]
        curr = current_run
        while curr and curr.backup_type == "incremental" and curr.baseline_run_id:
            parent = db.query(BackupRun).filter(BackupRun.id == curr.baseline_run_id).first()
            if parent and parent.id != curr.id and parent not in runs_to_inspect:
                runs_to_inspect.append(parent)
                curr = parent
            else:
                break

        # Traverse from newest to oldest run, tracking paths
        seen_paths: Set[str] = set()
        deleted_paths: Set[str] = set()
        active_files: List[BackupFile] = []

        for run in runs_to_inspect:
            files = db.query(BackupFile).filter(BackupFile.backup_run_id == run.id).all()
            for f in files:
                rel = f.relative_path or os.path.basename(f.original_path)
                norm_rel = rel.replace("/", "\\").lower()

                if norm_rel in seen_paths:
                    continue
                seen_paths.add(norm_rel)

                ct = (f.change_type or "FULL").upper()
                if ct == "DELETED" or f.upload_status == "deleted":
                    deleted_paths.add(norm_rel)
                    continue

                if norm_rel not in deleted_paths:
                    active_files.append(f)

        return active_files

    @classmethod
    def build_virtual_tree(cls, files: List[BackupFile]) -> Dict[str, Any]:
        """
        Construct a hierarchical folder-tree dict suitable for UI browsing.
        Root is {"name": "/", "type": "directory", "children": {...}, "size": total_size}
        """
        root = {
            "name": "Root",
            "path": "",
            "type": "directory",
            "size": 0,
            "children": {}
        }

        for f in files:
            rel = f.relative_path or os.path.basename(f.original_path)
            clean_rel = rel.replace("\\", "/").strip("/")
            parts = clean_rel.split("/")

            curr = root
            for i, part in enumerate(parts):
                is_file = (i == len(parts) - 1)
                sub_path = "/".join(parts[:i + 1])

                if is_file:
                    curr["children"][part] = {
                        "id": f.id,
                        "name": part,
                        "path": sub_path,
                        "type": "file",
                        "size": f.size_bytes or 0,
                        "sha256": f.sha256,
                        "change_type": f.change_type,
                        "modified_time": f.modified_time.isoformat() if f.modified_time else None
                    }
                    curr["size"] += (f.size_bytes or 0)
                else:
                    if part not in curr["children"]:
                        curr["children"][part] = {
                            "name": part,
                            "path": sub_path,
                            "type": "directory",
                            "size": 0,
                            "children": {}
                        }
                    curr = curr["children"][part]

        def convert_children_to_list(node: Dict[str, Any]) -> Dict[str, Any]:
            if node["type"] == "directory":
                child_list = []
                total_sz = 0
                for c in node["children"].values():
                    converted = convert_children_to_list(c)
                    child_list.append(converted)
                    total_sz += converted.get("size", 0)
                node["size"] = total_sz
                node["children"] = sorted(child_list, key=lambda x: (x["type"] != "directory", x["name"].lower()))
            return node

        return convert_children_to_list(root)

    @classmethod
    def filter_files(
        cls,
        files: List[BackupFile],
        restore_mode: str,
        selected_paths: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        extension: Optional[str] = None
    ) -> List[BackupFile]:
        """Filter files based on restore mode and selection criteria."""
        filtered = files

        if search_query:
            q = search_query.lower()
            filtered = [f for f in filtered if q in f.file_name.lower() or (f.relative_path and q in f.relative_path.lower())]

        if extension:
            ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            filtered = [f for f in filtered if f.file_name.lower().endswith(ext)]

        if restore_mode == "FULL_RECOVERY_POINT":
            return filtered

        norm_selected = [p.replace("/", "\\").strip("\\").lower() for p in (selected_paths or []) if p]

        if not norm_selected:
            return filtered if restore_mode == "SELECTION" else []

        result = []
        for f in filtered:
            rel = (f.relative_path or os.path.basename(f.original_path)).replace("/", "\\").strip("\\").lower()

            if restore_mode == "FILE":
                if rel in norm_selected or f.file_name.lower() in norm_selected:
                    result.append(f)
            elif restore_mode == "FOLDER":
                for sel in norm_selected:
                    if rel == sel or rel.startswith(sel + "\\"):
                        result.append(f)
                        break
            elif restore_mode == "SELECTION":
                for sel in norm_selected:
                    if rel == sel or rel.startswith(sel + "\\"):
                        result.append(f)
                        break
            else:
                result.append(f)

        return result

    @classmethod
    def calculate_preview(
        cls,
        db: Session,
        recovery_point_id: int,
        restore_mode: str,
        destination_root: str,
        conflict_mode: str = "OVERWRITE",
        selected_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a pre-flight restore plan without modifying physical files.
        Predicts actions (CREATE, OVERWRITE, SKIP, CONFLICT, RENAME),
        calculates logical size and estimated stored read bytes.
        """
        rp = db.query(RecoveryPoint).filter(RecoveryPoint.id == recovery_point_id).first()
        if not rp:
            raise ValueError(f"Recovery Point {recovery_point_id} not found")

        all_files = cls.get_recovery_point_logical_files(db, recovery_point_id)
        candidate_files = cls.filter_files(all_files, restore_mode, selected_paths)

        actions = {
            "CREATE": 0,
            "OVERWRITE": 0,
            "SKIP": 0,
            "CONFLICT": 0,
            "RENAME": 0
        }

        items_preview = []
        total_logical_bytes = 0
        estimated_stored_bytes = 0

        for f in candidate_files:
            rel = f.relative_path or os.path.basename(f.original_path)
            clean_rel = PathValidator.sanitize_relative_path(rel)
            target_dest = PathValidator.resolve_destination(destination_root, clean_rel)

            total_logical_bytes += (f.size_bytes or 0)

            # Check underlying storage object
            stored_sz = f.size_bytes or 0
            if f.storage_object_id:
                so = db.query(StorageObject).filter(StorageObject.id == f.storage_object_id).first()
                if so:
                    stored_sz = so.stored_size
            estimated_stored_bytes += stored_sz

            # Check destination existence
            exists = os.path.exists(target_dest)
            predicted_action = "CREATE"

            if exists:
                if conflict_mode == "SKIP":
                    predicted_action = "SKIP"
                elif conflict_mode == "OVERWRITE":
                    predicted_action = "OVERWRITE"
                elif conflict_mode == "RENAME":
                    predicted_action = "RENAME"
                elif conflict_mode == "FAIL":
                    predicted_action = "CONFLICT"

            actions[predicted_action] += 1
            items_preview.append({
                "backup_file_id": f.id,
                "file_name": f.file_name,
                "relative_path": clean_rel,
                "destination_path": target_dest,
                "size_bytes": f.size_bytes or 0,
                "stored_size_bytes": stored_sz,
                "sha256": f.sha256,
                "predicted_action": predicted_action,
                "destination_exists": exists
            })

        return {
            "recovery_point_id": rp.id,
            "source_client_id": rp.client.client_id if rp.client else f"PC-{rp.client_id:03d}",
            "destination_root": destination_root,
            "restore_mode": restore_mode,
            "conflict_mode": conflict_mode,
            "total_files": len(candidate_files),
            "logical_bytes": total_logical_bytes,
            "estimated_stored_read_bytes": estimated_stored_bytes,
            "actions": actions,
            "items": items_preview
        }
