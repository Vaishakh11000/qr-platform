#!/usr/bin/env python3
"""Restore a PostgreSQL custom-format backup to an explicitly confirmed non-production DB."""

import argparse
import hashlib
import hmac
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target-database", required=True)
    parser.add_argument("--host", default=settings.postgres_host)
    parser.add_argument("--port", type=int, default=settings.postgres_port)
    parser.add_argument(
        "--confirm-target",
        required=True,
        help="Must exactly match --target-database. The target will be overwritten.",
    )
    parser.add_argument(
        "--allow-nonempty-target",
        action="store_true",
        help="Allow pg_restore to clean existing objects in the confirmed target database.",
    )
    args = parser.parse_args()

    if args.target_database != args.confirm_target:
        parser.error("--confirm-target must exactly match --target-database")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,63}", args.target_database):
        parser.error("Target database name must contain only letters, numbers, underscores, or hyphens")
    if args.target_database in {settings.postgres_db, settings.test_postgres_db}:
        parser.error("Refusing to restore over the configured application or test database")
    if not args.backup.is_file():
        parser.error(f"Backup file does not exist: {args.backup}")
    checksum_path = args.backup.with_suffix(args.backup.suffix + ".sha256")
    if not checksum_path.is_file():
        parser.error(f"Backup checksum file does not exist: {checksum_path}")
    try:
        expected_digest = checksum_path.read_text(encoding="ascii").split()[0]
    except (OSError, IndexError, UnicodeDecodeError):
        parser.error("Backup checksum file is invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        parser.error("Backup checksum file is invalid")
    hasher = hashlib.sha256()
    with args.backup.open("rb") as backup_file:
        for chunk in iter(lambda: backup_file.read(1024 * 1024), b""):
            hasher.update(chunk)
    if not hmac.compare_digest(hasher.hexdigest(), expected_digest):
        parser.error("Backup checksum does not match; refusing to restore")

    try:
        with psycopg.connect(
            host=args.host,
            port=args.port,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
            dbname=args.target_database,
            connect_timeout=5,
        ) as connection:
            relation_count = connection.execute(
                """
                SELECT count(*)
                FROM pg_class AS relation
                JOIN pg_namespace AS schema ON schema.oid = relation.relnamespace
                WHERE schema.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND schema.nspname NOT LIKE 'pg_toast%'
                  AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM pg_depend AS dependency
                      WHERE dependency.classid = 'pg_class'::regclass
                        AND dependency.objid = relation.oid
                        AND dependency.deptype = 'e'
                  )
                """
            ).fetchone()[0]
    except psycopg.Error as exc:
        parser.error(f"Could not inspect the restore target database: {exc}")

    if relation_count and not args.allow_nonempty_target:
        parser.error(
            f"Target database contains {relation_count} non-extension relations. "
            "Restore refused. Use --allow-nonempty-target only when you intend "
            "to replace existing objects in this confirmed target."
        )

    env = os.environ.copy()
    env["PGPASSWORD"] = settings.postgres_password.get_secret_value()
    common = [
        f"--host={args.host}",
        f"--port={args.port}",
        f"--username={settings.postgres_user}",
    ]
    subprocess.run(["pg_restore", "--list", str(args.backup)], check=True, env=env, capture_output=True)
    subprocess.run(
        [
            "pg_restore",
            "--exit-on-error",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--single-transaction",
            *common,
            f"--dbname={args.target_database}",
            str(args.backup),
        ],
        check=True,
        env=env,
    )
    print(f"Restore completed in database: {args.target_database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
