import requests

try:
    resp = requests.post("http://localhost:8000/api/v1/restore/preview", json={
        "recovery_point_id": 1,
        "restore_mode": "FULL_RECOVERY_POINT",
        "destination_root": "<ORIGINAL>",
        "conflict_mode": "OVERWRITE"
    })
    print(resp.status_code)
    print(resp.json())
except Exception as e:
    print(e)
