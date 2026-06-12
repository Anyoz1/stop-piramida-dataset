#!/usr/bin/env python3
import argparse
from typing import Any
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIDEOS_DIR = ROOT / "outputs" / "videos"
RELEASE_DIR = ROOT / "release"
DEFAULT_FOLDER_NAME = "Stop-Piramida Video Dataset"
DEFAULT_CREDENTIALS = ROOT / "client_secrets.json"
TOKEN_PATH = ROOT / "token_drive.json"


def main() -> None:
    args = parse_args()
    drive = authenticate(args.credentials)
    root_folder = get_or_create_folder(drive, args.folder_name, parent_id=None)

    uploaded = 0
    skipped = 0
    for file_path in sorted(VIDEOS_DIR.glob("*/*.mp4")):
        category_folder = get_or_create_folder(drive, file_path.parent.name, parent_id=root_folder["id"])
        existing = find_existing_file(drive, file_path.name, category_folder["id"])
        if existing and args.skip_existing and int(existing.get("fileSize", 0) or 0) == file_path.stat().st_size:
            print(f"SKIP: {file_path.relative_to(ROOT)}")
            skipped += 1
            continue

        upload_file(drive, file_path, category_folder["id"], existing if existing and args.update_existing else None)
        print(f"UPLOAD: {file_path.relative_to(ROOT)}")
        uploaded += 1

    link = f"https://drive.google.com/drive/folders/{root_folder['id']}"
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    (RELEASE_DIR / "drive_link.txt").write_text(link + "\n", encoding="utf-8")
    print(f"Drive folder: {link}")
    print(f"Uploaded: {uploaded}")
    print(f"Skipped: {skipped}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload Stop-Piramida videos to Google Drive.")
    parser.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS), help="OAuth client secrets JSON")
    parser.add_argument("--folder-name", default=DEFAULT_FOLDER_NAME, help="Google Drive root folder name")
    parser.add_argument("--skip-existing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--update-existing", action="store_true", help="overwrite existing files when size differs")
    return parser.parse_args()


def authenticate(credentials_path: str) -> Any:
    try:
        from pydrive2.auth import GoogleAuth
        from pydrive2.drive import GoogleDrive
    except ModuleNotFoundError as exc:
        raise SystemExit("PyDrive2 is not installed. Run: python -m pip install -r requirements.txt") from exc

    credentials = Path(credentials_path)
    if not credentials.exists():
        raise FileNotFoundError(f"Credentials file not found: {credentials}")

    gauth = GoogleAuth()
    gauth.settings["client_config_file"] = str(credentials)
    gauth.settings["save_credentials"] = True
    gauth.settings["save_credentials_backend"] = "file"
    gauth.settings["save_credentials_file"] = str(TOKEN_PATH)
    gauth.settings["get_refresh_token"] = True

    if TOKEN_PATH.exists():
        gauth.LoadCredentialsFile(str(TOKEN_PATH))
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
    gauth.SaveCredentialsFile(str(TOKEN_PATH))
    return GoogleDrive(gauth)


def get_or_create_folder(drive: Any, title: str, parent_id: str | None) -> dict:
    query = [
        f"title = '{escape_query(title)}'",
        "mimeType = 'application/vnd.google-apps.folder'",
        "trashed = false",
    ]
    if parent_id:
        query.append(f"'{parent_id}' in parents")
    matches = drive.ListFile({"q": " and ".join(query)}).GetList()
    if matches:
        return matches[0]

    metadata = {
        "title": title,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [{"id": parent_id}]
    folder = drive.CreateFile(metadata)
    folder.Upload()
    return folder


def find_existing_file(drive: Any, title: str, parent_id: str) -> dict | None:
    query = " and ".join(
        [
            f"title = '{escape_query(title)}'",
            f"'{parent_id}' in parents",
            "trashed = false",
        ]
    )
    matches = drive.ListFile({"q": query}).GetList()
    return matches[0] if matches else None


def upload_file(drive: Any, file_path: Path, parent_id: str, existing: dict | None) -> None:
    file_obj = drive.CreateFile({"id": existing["id"]}) if existing else drive.CreateFile(
        {"title": file_path.name, "parents": [{"id": parent_id}]}
    )
    file_obj.SetContentFile(str(file_path))
    file_obj.Upload()


def escape_query(value: str) -> str:
    return value.replace("'", "\\'")


if __name__ == "__main__":
    main()
