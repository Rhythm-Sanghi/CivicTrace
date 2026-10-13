#!/usr/bin/env python3
"""
CivicTrace Operational Release Utility:
Atomic Backup, Atomic Restore, Upload Interruption Recovery, and Key Rotation.

Usage:
    python scripts/backup_restore.py backup --out backup_2026.tar.gz --db services/api/civictrace_dev.db
    python scripts/backup_restore.py restore --archive backup_2026.tar.gz --target-dir ./restored
    python scripts/backup_restore.py rotate-key --keyfile ./keys/signing_key.hex
    python scripts/backup_restore.py cleanup-interrupted --uploads services/api/storage/uploads --dry-run
"""

import os
import sys
import shutil
import tarfile
import hashlib
import json
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Ensure app path is resolvable
api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
sys.path.insert(0, api_dir)

from app.core.config import settings
from app.services.crypto_signer import SignerService


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_atomic_backup(
    output_tar: str,
    db_path: str = None,
    uploads_dir: str = None,
    keys_dir: str = None,
) -> str:
    """
    Creates an atomic backup bundle pairing the database snapshot and evidence storage.
    Uses sqlite3.backup() for consistent snapshots during application activity.
    Includes a cryptographic manifest of all assets to prevent partial restores.
    """
    db_file = os.path.abspath(db_path or os.path.join(api_dir, "civictrace_dev.db"))
    upload_path = os.path.abspath(uploads_dir or settings.UPLOAD_DIR)
    keys_path = os.path.abspath(keys_dir or os.path.join(api_dir, "storage", "keys"))

    if not os.path.exists(db_file):
        raise FileNotFoundError(f"Database file not found: {db_file}")

    print(f"[*] Initiating atomic SQLite snapshot of database: {db_file}")
    temp_snapshot_db = output_tar + ".snapshot.db"

    # Use SQLite online backup API for safe transactional snapshot
    src_conn = sqlite3.connect(db_file)
    dst_conn = sqlite3.connect(temp_snapshot_db)
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    try:
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_sha256": compute_file_sha256(temp_snapshot_db),
            "files": {},
            "keys": {},
        }

        if os.path.exists(upload_path):
            for root, _, files in os.walk(upload_path):
                for file in files:
                    if file == ".gitkeep":
                        continue
                    fpath = os.path.join(root, file)
                    relpath = os.path.relpath(fpath, upload_path).replace("\\", "/")
                    manifest["files"][relpath] = {
                        "sha256": compute_file_sha256(fpath),
                        "size_bytes": os.path.getsize(fpath),
                    }

        if os.path.exists(keys_path):
            for root, _, files in os.walk(keys_path):
                for file in files:
                    fpath = os.path.join(root, file)
                    relpath = os.path.relpath(fpath, keys_path).replace("\\", "/")
                    manifest["keys"][relpath] = {
                        "sha256": compute_file_sha256(fpath),
                        "size_bytes": os.path.getsize(fpath),
                    }

        temp_manifest = output_tar + ".manifest.json"
        with open(temp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        print(f"[*] Packaging into tar archive: {output_tar}")
        with tarfile.open(output_tar, "w:gz") as tar:
            tar.add(temp_snapshot_db, arcname="database.db")
            tar.add(temp_manifest, arcname="manifest.json")
            if os.path.exists(upload_path):
                for root, _, files in os.walk(upload_path):
                    for file in files:
                        if file == ".gitkeep":
                            continue
                        fpath = os.path.join(root, file)
                        relpath = os.path.relpath(fpath, upload_path).replace("\\", "/")
                        tar.add(fpath, arcname=f"uploads/{relpath}")
            if os.path.exists(keys_path):
                for root, _, files in os.walk(keys_path):
                    for file in files:
                        fpath = os.path.join(root, file)
                        relpath = os.path.relpath(fpath, keys_path).replace("\\", "/")
                        tar.add(fpath, arcname=f"keys/{relpath}")

        if os.path.exists(temp_manifest):
            os.remove(temp_manifest)
    finally:
        if os.path.exists(temp_snapshot_db):
            os.remove(temp_snapshot_db)

    print(f"[OK] Atomic backup archive created: {output_tar} ({os.path.getsize(output_tar)} bytes)")
    return output_tar


def _safe_extract(tar: tarfile.TarFile, path: str):
    """
    Extracts tar members while strictly preventing path traversal vulnerabilities.
    """
    dest_path = os.path.abspath(path)
    for member in tar.getmembers():
        member_path = os.path.abspath(os.path.join(dest_path, member.name))
        if not member_path.startswith(dest_path + os.sep) and member_path != dest_path:
            raise SecurityError(f"Attempted Path Traversal in Tar File: {member.name}")
    tar.extractall(path=dest_path)


class SecurityError(Exception):
    pass


def restore_atomic_backup(backup_tar: str, restore_dir: str) -> bool:
    """
    Restores database and evidence assets while strictly verifying manifest integrity.
    Prevents path traversal and archive tampering.
    """
    if not os.path.exists(backup_tar):
        raise FileNotFoundError(f"Backup archive not found: {backup_tar}")

    print(f"[*] Extracting and verifying backup: {backup_tar}")
    restore_dir = os.path.abspath(restore_dir)
    temp_extract = os.path.join(restore_dir, "_temp_restore_verify")
    os.makedirs(temp_extract, exist_ok=True)

    try:
        with tarfile.open(backup_tar, "r:gz") as tar:
            _safe_extract(tar, temp_extract)

        manifest_path = os.path.join(temp_extract, "manifest.json")
        if not os.path.exists(manifest_path):
            raise ValueError("Corrupt backup: manifest.json missing!")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        db_restored = os.path.join(temp_extract, "database.db")
        actual_db_hash = compute_file_sha256(db_restored)
        if actual_db_hash != manifest["database_sha256"]:
            raise ValueError("Database checksum mismatch! Potential archive tampering.")

        uploads_restored = os.path.join(temp_extract, "uploads")
        if os.path.exists(uploads_restored):
            for relpath, meta in manifest.get("files", {}).items():
                fpath = os.path.join(uploads_restored, relpath)
                if not os.path.exists(fpath):
                    raise ValueError(f"Evidence file missing from restore: {relpath}")
                if compute_file_sha256(fpath) != meta["sha256"]:
                    raise ValueError(f"Evidence file digest mismatch: {relpath}")

        # Deploy restored files to target directory
        final_db = os.path.join(restore_dir, "civictrace_dev.db")
        final_uploads = os.path.join(restore_dir, "uploads")
        shutil.copy2(db_restored, final_db)
        if os.path.exists(uploads_restored):
            if os.path.exists(final_uploads):
                shutil.rmtree(final_uploads)
            shutil.copytree(uploads_restored, final_uploads)

        keys_restored = os.path.join(temp_extract, "keys")
        if os.path.exists(keys_restored):
            final_keys = os.path.join(restore_dir, "keys")
            if os.path.exists(final_keys):
                shutil.rmtree(final_keys)
            shutil.copytree(keys_restored, final_keys)

        print(f"[OK] Backup restored and verified successfully into: {restore_dir}")
        return True
    finally:
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)


def cleanup_interrupted_uploads(
    uploads_dir: str = None,
    db_path: str = None,
    dry_run: bool = False,
) -> int:
    """
    Scans uploads folder and purges dangling temporary upload fragments (.tmp, .part).
    If database is available, cross-references active EvidenceAsset paths so active
    uploads are never deleted.
    """
    target_dir = os.path.abspath(uploads_dir or settings.UPLOAD_DIR)
    if not os.path.exists(target_dir):
        return 0

    # Collect known active files from database if accessible
    active_files = set()
    db_file = os.path.abspath(db_path or os.path.join(api_dir, "civictrace_dev.db"))
    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(db_file)
            cur = conn.cursor()
            cur.execute("SELECT file_path FROM evidence_assets")
            for row in cur.fetchall():
                if row[0]:
                    active_files.add(os.path.basename(row[0]))
            conn.close()
        except Exception:
            pass

    removed = 0
    for root, _, files in os.walk(target_dir):
        for f in files:
            is_fragment = f.endswith(".tmp") or f.endswith(".part")
            fpath = os.path.join(root, f)
            if is_fragment and f not in active_files:
                if dry_run:
                    print(f"[*] [DRY RUN] Would remove fragment: {fpath}")
                    removed += 1
                else:
                    try:
                        os.remove(fpath)
                        removed += 1
                    except Exception as e:
                        print(f"[!] Warning: could not remove {fpath}: {e}")

    mode_str = "[DRY RUN] Identified" if dry_run else "Cleaned up"
    print(f"[OK] {mode_str} {removed} interrupted upload fragment(s).")
    return removed


def rotate_signing_key(key_file: str) -> tuple[str, str]:
    """
    Generates a fresh Ed25519 signing keypair, writes private key to secure key file,
    and updates trusted_anchors_history.json so older evidence packages remain verifiable.
    """
    key_file = os.path.abspath(key_file)
    priv_hex, pub_b64 = SignerService.generate_keypair()
    keys_dir = os.path.dirname(key_file)
    os.makedirs(keys_dir, exist_ok=True)

    history_file = os.path.join(keys_dir, "trusted_anchors_history.json")
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    # Archive old key if present
    if os.path.exists(key_file):
        old_priv_hex = ""
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                old_priv_hex = f.read().strip()
        except Exception:
            pass

        if old_priv_hex:
            try:
                old_pub_b64 = SignerService.get_public_key_b64(old_priv_hex)
                now_iso = datetime.now(timezone.utc).isoformat()
                history.append({
                    "public_key_b64": old_pub_b64,
                    "archived_at": now_iso,
                    "status": "ROTATED_ARCHIVED",
                })
            except Exception:
                pass

        archive_name = f"{key_file}.{int(datetime.now(timezone.utc).timestamp())}.old"
        shutil.move(key_file, archive_name)
        print(f"[*] Archived previous signing key to: {archive_name}")

    # Write new active key
    with open(key_file, "w", encoding="utf-8") as f:
        f.write(priv_hex.strip() + "\n")

    history.append({
        "public_key_b64": pub_b64,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACTIVE",
    })

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    print(f"[OK] New Ed25519 signing key written to: {key_file}")
    print(f"[*] New Public Key (Base64 External Trust Anchor): {pub_b64}")
    print(f"[*] Historical trust anchors maintained in: {history_file}")
    return priv_hex, pub_b64


def main():
    parser = argparse.ArgumentParser(description="CivicTrace Operational Release Utility")
    subparsers = parser.add_subparsers(dest="command")

    # backup
    p_backup = subparsers.add_parser("backup")
    p_backup.add_argument("--out", "--out-dir", dest="out", default="civictrace_backup.tar.gz")
    p_backup.add_argument("--db", "--db-path", dest="db", default=None)
    p_backup.add_argument("--uploads", "--uploads-dir", dest="uploads", default=None)
    p_backup.add_argument("--keys", "--keys-dir", dest="keys", default=None)

    # restore
    p_restore = subparsers.add_parser("restore")
    p_restore.add_argument("--archive", "--in", dest="input_tar", required=True)
    p_restore.add_argument("--target-dir", "--db-target", dest="target_dir", required=True)

    # rotate-key
    p_rotate = subparsers.add_parser("rotate-key")
    p_rotate.add_argument("--keyfile", "--keys-dir", dest="keyfile", default="./keys/signing_key.hex")

    # cleanup
    p_clean = subparsers.add_parser("cleanup-interrupted")
    p_clean.add_argument("--uploads", "--uploads-dir", dest="uploads", default=None)
    p_clean.add_argument("--db", "--db-path", dest="db", default=None)
    p_clean.add_argument("--dry-run", action="store_true", default=False)

    args = parser.parse_args()
    if args.command == "backup":
        create_atomic_backup(args.out, args.db, args.uploads, getattr(args, "keys", None))
    elif args.command == "restore":
        restore_atomic_backup(args.input_tar, args.target_dir)
    elif args.command == "rotate-key":
        rotate_signing_key(args.keyfile)
    elif args.command == "cleanup-interrupted":
        cleanup_interrupted_uploads(args.uploads, getattr(args, "db", None), args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
