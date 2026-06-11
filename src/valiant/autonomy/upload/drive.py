"""Google Drive upload stub - migrated from old-codebase gdrive_stub.py."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


class DriveUploader:
    """Stub uploader - copies locally until real GDrive is implemented (Track D10)."""

    def __init__(self, cfg: dict):
        upload_cfg = cfg.get("upload", {})
        self.config_path = upload_cfg.get("config_path", "")
        if self.config_path and os.path.isfile(self.config_path):
            print(f"[UPLOAD STUB] Config at {self.config_path} - real upload not implemented")
        else:
            print("[UPLOAD STUB] No credentials file - local copy only")

    def upload_task2_photo(self, local_path: str, target_number: int) -> bool:
        dest_name = f"Task2ValiantAerotechTarget{target_number}.jpg"
        dest_dir = Path(local_path).parent / "uploaded"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / dest_name
        shutil.copy2(local_path, dest_path)
        print(f"[UPLOAD STUB] Copied to {dest_path}")
        return True
