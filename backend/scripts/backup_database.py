#!/usr/bin/env python3
"""Create a permission-restricted PostgreSQL custom-format backup."""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import PROJECT_ROOT, settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=settings.postgres_db)
    parser.add_argument("--host", default=settings.postgres_host)
    parser.add_argument("--port", type=int, default=settings.postgres_port)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "backups")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", args.database):
        parser.error("Database name must contain only letters, numbers, underscores, or hyphens")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = args.output_dir / f"{args.database}_{timestamp}.dump"
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    if destination.exists() or checksum_path.exists():
        parser.error(f"Backup destination already exists: {destination}")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{args.database}_{timestamp}_",
        suffix=".partial",
        dir=args.output_dir,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    os.chmod(temporary_path, 0o600)

    env = os.environ.copy()
    env["PGPASSWORD"] = settings.postgres_password.get_secret_value()
    command = [
        "pg_dump",
        "--format=custom",
        "--no-owner",
        "--no-acl",
        f"--file={temporary_path}",
        f"--host={args.host}",
        f"--port={args.port}",
        f"--username={settings.postgres_user}",
        args.database,
    ]

    try:
        subprocess.run(command, check=True, env=env)
        hasher = hashlib.sha256()
        with temporary_path.open("rb") as backup_file:
            for chunk in iter(lambda: backup_file.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
        os.replace(temporary_path, destination)
        checksum_path.write_text(f"{digest}  {destination.name}\n", encoding="ascii")
        os.chmod(checksum_path, 0o600)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(f"Backup created: {destination}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
