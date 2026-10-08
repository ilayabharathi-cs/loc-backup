import sys
sys.path.insert(0, '/home/xlr8/localbackup/server')

from app.schemas.restore import RestorePreviewResponse
from app.database.session import SessionLocal
from app.services.restore.planner import RestorePlanner

db = SessionLocal()
preview_data = RestorePlanner.calculate_preview(
    db=db,
    recovery_point_id=1,
    restore_mode="FULL_RECOVERY_POINT",
    destination_root="<ORIGINAL>",
    conflict_mode="OVERWRITE",
    selected_paths=None
)
print("Preview data keys:", preview_data.keys())

try:
    resp = RestorePreviewResponse(**preview_data)
    print("Validation successful!")
except Exception as e:
    print("Validation failed:")
    print(e)
