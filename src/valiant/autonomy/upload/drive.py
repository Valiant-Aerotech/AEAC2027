"""Task 2 photo upload - local fallback or Google Drive service account."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from valiant.autonomy.conops import task2_photo_filename


class DriveUploader:
    """Upload Task 2 confirmation photos with retry and local fallback."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        upload_cfg = cfg.get("upload", {})
        self.method = upload_cfg.get("method", "local_copy")
        self.config_path = upload_cfg.get("config_path", "")
        self.folder_id = upload_cfg.get("folder_id", "")
        self.timeout_s = upload_cfg.get("timeout_s", 15)
        self.retry_count = upload_cfg.get("retry_count", 3)
        self.retry_delay_s = upload_cfg.get("retry_delay_s", 2.0)
        self._drive_ready = self._can_use_gdrive()

        if self._drive_ready:
            print("[UPLOAD] Google Drive service account configured")
        else:
            print("[UPLOAD] Local copy mode (no Drive credentials or optional deps)")

    def _can_use_gdrive(self) -> bool:
        if self.method != "gdrive_service_account":
            return False
        if not self.config_path or not os.path.isfile(self.config_path):
            return False
        if not self.folder_id:
            return False
        try:
            import google.oauth2.service_account  # noqa: F401
            import googleapiclient.discovery  # noqa: F401
        except ImportError:
            return False
        return True

    def upload_task2_photo(self, local_path: str, target_number: int) -> bool:
        dest_name = task2_photo_filename(self.cfg, target_number)
        for attempt in range(1, self.retry_count + 1):
            try:
                if self._drive_ready:
                    ok = self._upload_gdrive(local_path, dest_name)
                else:
                    ok = self._copy_local(local_path, dest_name)
                if ok:
                    return True
            except Exception as exc:
                print(f"[UPLOAD] Attempt {attempt}/{self.retry_count} failed: {exc}")
            if attempt < self.retry_count:
                time.sleep(self.retry_delay_s)
        print(f"[UPLOAD] Failed after {self.retry_count} attempts: {local_path}")
        return False

    def _copy_local(self, local_path: str, dest_name: str) -> bool:
        dest_dir = Path(local_path).parent / "uploaded"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / dest_name
        shutil.copy2(local_path, dest_path)
        print(f"[UPLOAD] Copied to {dest_path}")
        return True

    def _upload_gdrive(self, local_path: str, dest_name: str) -> bool:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        scopes = ["https://www.googleapis.com/auth/drive.file"]
        credentials = service_account.Credentials.from_service_account_file(
            self.config_path,
            scopes=scopes,
        )
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        metadata = {"name": dest_name, "parents": [self.folder_id]}
        media = MediaFileUpload(local_path, mimetype="image/jpeg", resumable=False)
        request = service.files().create(body=metadata, media_body=media, fields="id")
        result = request.execute(num_retries=0)
        file_id = result.get("id", "")
        print(f"[UPLOAD] Drive file id={file_id} name={dest_name}")
        self._copy_local(local_path, dest_name)
        return True
