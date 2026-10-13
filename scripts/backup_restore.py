#!/usr/bin/env python3
"""
CivicTrace Operational Release Utility:
Atomic Backup, Atomic Restore, Upload Interruption Recovery, and Key Lifecycle Management.

Security Policy:
- Application backups contain ONLY the transactional database snapshot and committed evidence assets.
- Private signing keys (Ed25519) and JWT credentials are NEVER included in application backup archives.
- Dedicated, encrypted key backup procedures use PBKDF2-HMAC-SHA256 and AES-256-GCM.
- SHA-256 digests in manifests detect accidental disk corruption and truncation.
- Ed25519 digital signatures verified against external trust anchors detect malicious archive replacement.

Usage:
    python scripts/backup_restore.py backup --out backup_2026.tar.gz --db services/api/civictrace_dev.db
    python scripts/backup_restore.py restore --archive backup_2026.tar.gz --target-dir ./restored --expected-public-key <PUB_KEY_B64>
    python scripts/backup_restore.py backup-keys --out keys_backup.enc --passphrase <SECRET>
    python scripts/backup_restore.py restore-keys --archive keys_backup.enc --passphrase <SECRET> --target-dir ./keys
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
from typing import Optional, Tuple, Dict, Any

# Ensure app path is resolvable
api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api"))
sys.path.insert(0, api_dir)

from app.core.config import settings
from app.core.security import canonical_json
from app.services.crypto_signer import SignerService


class SecurityError(Exception):
    pass


def compute_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


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


def _find_committed_asset_path(upload_dir: str, file_path: Optional[str], file_name: Optional[str]) -> Optional[str]:
    """
    Resolves the physical on-disk location of a committed evidence asset.
    Checks candidate relative paths, absolute paths, and basename permutations.
    """
    candidates = []
    if file_path:
        norm_fp = file_path.replace("\\", "/")
        if os.path.isabs(norm_fp) and os.path.isfile(norm_fp):
            return norm_fp
        candidates.append(os.path.join(upload_dir, os.path.basename(norm_fp)))
        candidates.append(os.path.join(upload_dir, norm_fp.lstrip("/")))
        if norm_fp.startswith("uploads/"):
            candidates.append(os.path.join(upload_dir, norm_fp[8:].lstrip("/")))
        if norm_fp.startswith("storage/uploads/"):
            candidates.append(os.path.join(upload_dir, norm_fp[16:].lstrip("/")))
    if file_name:
        candidates.append(os.path.join(upload_dir, file_name))
        candidates.append(os.path.join(upload_dir, os.path.basename(file_name)))

    for cand in candidates:
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def create_atomic_backup(
    output_tar: str,
    db_path: Optional[str] = None,
    uploads_dir: Optional[str] = None,
    keys_dir: Optional[str] = None,  # Explicitly rejected or ignored for security
) -> str:
    """
    Creates an atomic backup bundle pairing the transactional database snapshot
    and committed evidence storage.
    Uses sqlite3.backup() for consistent snapshots during application activity.
    Cross-references database evidence_assets table so in-flight/uncommitted files
    or temporary upload fragments (.tmp, .part) are never packaged.
    Signs the manifest with Ed25519 to protect against malicious archive replacement.
    STRICTLY EXCLUDES private signing keys and credentials.
    Fails safely if any committed evidence asset is missing or has been modified.
    """
    if keys_dir:
        print("[!] SECURITY WARNING: Private key directory argument was provided to application backup. "
              "Private keys are strictly excluded from application backups to prevent credential leakage. "
              "Use 'backup-keys' for controlled, encrypted key backups.")

    db_file = os.path.abspath(db_path or os.path.join(api_dir, "civictrace_dev.db"))
    upload_path = os.path.abspath(uploads_dir or settings.UPLOAD_DIR)

    if not os.path.exists(db_file):
        raise FileNotFoundError(f"Database file not found: {db_file}")

    print(f"[*] Initiating atomic SQLite snapshot of database: {db_file}")
    temp_snapshot_db = output_tar + ".snapshot.db"
    temp_manifest = output_tar + ".manifest.json"

    # 1. Atomic database snapshot via SQLite Online Backup API
    src_conn = sqlite3.connect(db_file)
    dst_conn = sqlite3.connect(temp_snapshot_db)
    src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    try:
        # 2. Inspect snapshot database for committed evidence assets to prevent race conditions
        committed_asset_records: list[Dict[str, Any]] = []
        snap_conn = None
        try:
            snap_conn = sqlite3.connect(temp_snapshot_db)
            snap_cur = snap_conn.cursor()
            table_check = snap_cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_assets'"
            ).fetchone()
            if table_check:
                col_rows = snap_cur.execute("PRAGMA table_info(evidence_assets)").fetchall()
                col_names = [r[1] for r in col_rows]
                hash_col = "sha256_hash" if "sha256_hash" in col_names else ("file_hash" if "file_hash" in col_names else None)
                query = f"SELECT id, file_name, file_path{f', {hash_col}' if hash_col else ''} FROM evidence_assets"
                snap_cur.execute(query)
                for row in snap_cur.fetchall():
                    asset_id = row[0]
                    file_name = row[1]
                    file_rel_path = row[2]
                    expected_hash = row[3] if hash_col else None
                    committed_asset_records.append({
                        "id": asset_id,
                        "file_name": file_name,
                        "file_path": file_rel_path,
                        "expected_hash": expected_hash,
                    })
        except Exception as e:
            print(f"[!] Note: Could not query evidence_assets from snapshot ({e}); falling back to verified file scan.")
        finally:
            if snap_conn:
                snap_conn.close()

        # 3. Collect and verify evidence assets matching committed state
        files_manifest: Dict[str, Dict[str, Any]] = {}
        files_to_pack: list[Tuple[str, str]] = []

        if committed_asset_records:
            # Safe fail: When committed assets exist in snapshot, every one must exist on disk and match digest
            for rec in committed_asset_records:
                asset_id = rec["id"]
                file_name = rec["file_name"]
                file_rel_path = rec["file_path"]
                expected_hash = rec["expected_hash"]

                fpath = _find_committed_asset_path(upload_path, file_rel_path, file_name)
                if not fpath or not os.path.exists(fpath):
                    identifier = file_name or file_rel_path or asset_id
                    raise RuntimeError(
                        f"BACKUP INTEGRITY FAILURE: Committed evidence asset '{identifier}' (ID: {asset_id}) "
                        f"is missing from disk storage. Cannot produce a valid recoverable backup."
                    )

                try:
                    file_hash = compute_file_sha256(fpath)
                    file_size = os.path.getsize(fpath)
                except (FileNotFoundError, PermissionError) as e:
                    raise RuntimeError(
                        f"BACKUP INTEGRITY FAILURE: Committed evidence asset '{fpath}' could not be read: {e}. "
                        f"Cannot produce a valid recoverable backup."
                    )

                if expected_hash and file_hash != expected_hash:
                    identifier = file_name or file_rel_path or asset_id
                    raise RuntimeError(
                        f"BACKUP INTEGRITY FAILURE: Committed evidence asset '{identifier}' (ID: {asset_id}) "
                        f"content digest mismatch! Expected {expected_hash}, got {file_hash}. "
                        f"File was modified or corrupted during backup execution."
                    )

                try:
                    relpath = os.path.relpath(fpath, upload_path).replace("\\", "/")
                except ValueError:
                    relpath = os.path.basename(fpath)

                files_manifest[relpath] = {
                    "sha256": file_hash,
                    "size_bytes": file_size,
                }
                files_to_pack.append((fpath, f"uploads/{relpath}"))
        elif os.path.exists(upload_path):
            # Fallback when database has no evidence_assets table or zero committed records
            for root, _, files in os.walk(upload_path):
                for file in files:
                    if file == ".gitkeep" or file.endswith(".tmp") or file.endswith(".part"):
                        continue
                    fpath = os.path.join(root, file)
                    relpath = os.path.relpath(fpath, upload_path).replace("\\", "/")
                    try:
                        file_hash = compute_file_sha256(fpath)
                        file_size = os.path.getsize(fpath)
                        files_manifest[relpath] = {
                            "sha256": file_hash,
                            "size_bytes": file_size,
                        }
                        files_to_pack.append((fpath, f"uploads/{relpath}"))
                    except (FileNotFoundError, PermissionError):
                        continue

        # 4. Construct cryptographic manifest
        db_hash = compute_file_sha256(temp_snapshot_db)
        manifest_body: Dict[str, Any] = {
            "format": "civictrace_backup_manifest",
            "version": "2.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_sha256": db_hash,
            "files": files_manifest,
            "security_policy": {
                "private_keys_included": False,
                "integrity_scope": "SHA-256 digests detect accidental corruption and transfer truncation.",
                "authenticity_scope": "Ed25519 digital signature binds manifest to authorized system authority.",
            },
        }

        # Sign manifest with system trust anchor if available
        try:
            canonical_manifest = canonical_json(manifest_body).encode("utf-8")
            sig_b64 = SignerService.sign_bytes(canonical_manifest)
            pub_key_b64 = SignerService.get_public_key_base64()
            manifest_body["signature"] = sig_b64
            manifest_body["signer_public_key"] = pub_key_b64
        except Exception:
            manifest_body["signature"] = None
            manifest_body["signer_public_key"] = None

        with open(temp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_body, f, indent=2)

        # 5. Pack into tar.gz archive
        print(f"[*] Packaging into archive: {output_tar}")
        with tarfile.open(output_tar, "w:gz") as tar:
            tar.add(temp_snapshot_db, arcname="database.db")
            tar.add(temp_manifest, arcname="manifest.json")
            for src_path, arc_name in files_to_pack:
                if os.path.exists(src_path):
                    tar.add(src_path, arcname=arc_name)

        if os.path.exists(temp_manifest):
            try:
                os.remove(temp_manifest)
            except Exception:
                pass
    except Exception:
        # Fail safe: Clean up partial archive so no corrupted/incomplete backup is left behind
        if os.path.exists(output_tar):
            try:
                os.remove(output_tar)
            except OSError:
                pass
        raise
    finally:
        import gc
        gc.collect()
        if os.path.exists(temp_manifest):
            try:
                os.remove(temp_manifest)
            except Exception:
                pass
        if os.path.exists(temp_snapshot_db):
            try:
                os.remove(temp_snapshot_db)
            except Exception:
                pass

    print(f"[OK] Atomic backup archive created: {output_tar} ({os.path.getsize(output_tar)} bytes)")
    return output_tar
    return output_tar


def restore_atomic_backup(
    backup_tar: str,
    restore_dir: str,
    expected_public_key: Optional[str] = None,
) -> bool:
    """
    Restores database and evidence assets while strictly verifying:
    1. Archive path safety (path traversal prevention).
    2. Digital signature authenticity against expected_public_key (if supplied).
    3. Transactional database SHA-256 digest integrity against manifest.
    4. Every individual evidence asset SHA-256 digest against manifest.
    5. Rejection of any unauthorized private keys found in the archive.
    """
    if not os.path.exists(backup_tar):
        raise FileNotFoundError(f"Backup archive not found: {backup_tar}")

    print(f"[*] Extracting and verifying backup: {backup_tar}")
    restore_dir = os.path.abspath(restore_dir)
    temp_extract = os.path.join(restore_dir, "_temp_restore_verify")
    os.makedirs(temp_extract, exist_ok=True)

    try:
        with tarfile.open(backup_tar, "r:gz") as tar:
            # Security: Path traversal validation
            _safe_extract(tar, temp_extract)

        manifest_path = os.path.join(temp_extract, "manifest.json")
        if not os.path.exists(manifest_path):
            raise ValueError("Corrupt backup: manifest.json missing from root!")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Authenticity check: Verify digital signature if trust anchor is provided
        if expected_public_key:
            sig = manifest.get("signature")
            signer_key = manifest.get("signer_public_key")
            if not sig or not signer_key:
                raise ValueError("TRUST ANCHOR ERROR: Backup manifest lacks digital signature for trusted verification.")
            if signer_key != expected_public_key:
                raise ValueError(
                    f"TRUST ANCHOR VIOLATION: Manifest signer key does not match expected trusted public key. "
                    f"Possible malicious archive replacement detected."
                )

            # Reconstruct content signed
            manifest_to_verify = dict(manifest)
            manifest_to_verify.pop("signature", None)
            manifest_to_verify.pop("signer_public_key", None)
            canonical_bytes = canonical_json(manifest_to_verify).encode("utf-8")
            if not SignerService.verify_signature(canonical_bytes, sig, expected_public_key):
                raise ValueError("AUTHENTICITY VIOLATION: Manifest digital signature invalid against trusted public key.")
            print("[OK] Manifest Ed25519 digital signature verified against external trust anchor.")

        # Database checksum integrity verification
        db_restored = os.path.join(temp_extract, "database.db")
        if not os.path.exists(db_restored):
            raise ValueError("Corrupt backup: database.db missing from archive.")
        actual_db_hash = compute_file_sha256(db_restored)
        if actual_db_hash != manifest["database_sha256"]:
            raise ValueError(
                f"CORRUPTION DETECTED: Database checksum mismatch! "
                f"Expected {manifest['database_sha256']}, got {actual_db_hash}."
            )

        # Evidence file integrity verification
        uploads_restored = os.path.join(temp_extract, "uploads")
        manifest_files = manifest.get("files", {})
        if manifest_files:
            if not os.path.exists(uploads_restored):
                raise ValueError("Corrupt backup: uploads declared in manifest but directory missing.")
            for relpath, meta in manifest_files.items():
                fpath = os.path.join(uploads_restored, relpath)
                if not os.path.exists(fpath):
                    raise ValueError(f"CORRUPTION DETECTED: Declared evidence file missing: {relpath}")
                actual_hash = compute_file_sha256(fpath)
                if actual_hash != meta["sha256"]:
                    raise ValueError(
                        f"CORRUPTION DETECTED: Evidence file {relpath} digest mismatch! "
                        f"Expected {meta['sha256']}, got {actual_hash}."
                    )

        # Security check: Ensure no rogue private keys are unpacked into application directory
        keys_restored = os.path.join(temp_extract, "keys")
        if os.path.exists(keys_restored):
            print("[!] SECURITY WARNING: Archive contained a 'keys/' directory. "
                  "Per security policy, private keys are strictly rejected and will NOT be deployed.")

        # Deploy restored verified files to target directory
        final_db = os.path.join(restore_dir, "civictrace_dev.db")
        final_uploads = os.path.join(restore_dir, "uploads")
        os.makedirs(restore_dir, exist_ok=True)
        shutil.copy2(db_restored, final_db)

        if os.path.exists(uploads_restored):
            if os.path.exists(final_uploads):
                shutil.rmtree(final_uploads)
            shutil.copytree(uploads_restored, final_uploads)

        print(f"[OK] Backup restored and verified successfully into: {restore_dir}")
        return True
    finally:
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)


def create_encrypted_key_backup(
    output_file: str,
    passphrase: str,
    keys_dir: Optional[str] = None,
) -> str:
    """
    Dedicated, controlled procedure for backing up Ed25519 signing keys.
    Encrypts the key store using PBKDF2-HMAC-SHA256 (100,000 iterations) and AES-256-GCM.
    Keeps signing credentials strictly isolated from standard application backups.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    source_dir = os.path.abspath(keys_dir or os.path.join(api_dir, "storage", "keys"))
    if not os.path.exists(source_dir):
        raise FileNotFoundError(f"Keys directory not found: {source_dir}")

    if len(passphrase) < 12:
        raise ValueError("Passphrase for key backup must be at least 12 characters.")

    # 1. Package key files into memory tar
    import io
    tar_bytes_io = io.BytesIO()
    with tarfile.open(fileobj=tar_bytes_io, mode="w:gz") as tar:
        for root, _, files in os.walk(source_dir):
            for f in files:
                fpath = os.path.join(root, f)
                relpath = os.path.relpath(fpath, source_dir)
                tar.add(fpath, arcname=relpath)

    tar_bytes = tar_bytes_io.getvalue()

    # 2. Derive key via PBKDF2
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    derived_key = kdf.derive(passphrase.encode("utf-8"))

    # 3. Encrypt via AES-GCM
    aesgcm = AESGCM(derived_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, tar_bytes, None)

    # 4. Write bundle: [SALT (16)] + [NONCE (12)] + [CIPHERTEXT]
    with open(output_file, "wb") as f:
        f.write(salt + nonce + ciphertext)

    print(f"[OK] Encrypted key backup created: {output_file} ({os.path.getsize(output_file)} bytes)")
    return output_file


def restore_encrypted_key_backup(
    input_file: str,
    passphrase: str,
    target_dir: Optional[str] = None,
) -> bool:
    """
    Restores Ed25519 signing keys from an encrypted key backup using passphrase.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Encrypted key backup not found: {input_file}")

    dest_dir = os.path.abspath(target_dir or os.path.join(api_dir, "storage", "keys"))
    os.makedirs(dest_dir, exist_ok=True)

    with open(input_file, "rb") as f:
        data = f.read()

    if len(data) < 28:
        raise ValueError("Invalid encrypted key backup: file too short.")

    salt = data[:16]
    nonce = data[16:28]
    ciphertext = data[28:]

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    derived_key = kdf.derive(passphrase.encode("utf-8"))

    aesgcm = AESGCM(derived_key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except Exception:
        raise ValueError("Decryption failed! Incorrect passphrase or corrupted key archive.")

    import io
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tar:
        _safe_extract(tar, dest_dir)

    print(f"[OK] Signing keys restored securely into: {dest_dir}")
    return True


def cleanup_interrupted_uploads(
    uploads_dir: Optional[str] = None,
    db_path: Optional[str] = None,
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


def rotate_signing_key(key_file: str) -> Tuple[str, str]:
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


def _resolve_passphrase(
    passphrase: Optional[str] = None,
    passphrase_env: Optional[str] = None,
    passphrase_file: Optional[str] = None,
    prompt_text: str = "Enter key backup passphrase: ",
) -> str:
    """
    Safely resolves the passphrase for key backup and restoration operations.
    Avoids exposing passphrases through command-line arguments, process listings (ps),
    or shell history.

    Resolution Priority:
    1. --passphrase-env: Environment variable specified on CLI
    2. KEY_BACKUP_PASSPHRASE: Standard environment variable fallback
    3. --passphrase-file: Secure local file containing passphrase
    4. --passphrase: CLI argument (supported with security warning)
    5. Interactive hidden prompt via getpass.getpass()
    """
    if passphrase_env:
        val = os.environ.get(passphrase_env)
        if not val:
            raise ValueError(f"Passphrase environment variable '{passphrase_env}' is not set or empty.")
        return val

    if passphrase_file:
        if not os.path.exists(passphrase_file):
            raise FileNotFoundError(f"Passphrase file '{passphrase_file}' does not exist.")
        with open(passphrase_file, "r", encoding="utf-8") as f:
            val = f.read().strip("\r\n")
        if not val:
            raise ValueError(f"Passphrase file '{passphrase_file}' is empty.")
        return val

    env_default = os.environ.get("KEY_BACKUP_PASSPHRASE")
    if env_default and not passphrase:
        return env_default

    if passphrase:
        print(
            "[!] SECURITY WARNING: Passing passphrases via CLI argument '--passphrase' exposes secrets "
            "to process listings (ps) and shell history. Prefer '--passphrase-env', '--passphrase-file', "
            "or interactive prompt."
        )
        return passphrase

    if sys.stdin and sys.stdin.isatty():
        import getpass
        val = getpass.getpass(prompt_text)
        if not val:
            raise ValueError("Passphrase entered via prompt cannot be empty.")
        return val
    else:
        raise ValueError(
            "Non-interactive environment detected without passphrase. "
            "Please provide passphrase via --passphrase-env, KEY_BACKUP_PASSPHRASE env var, or --passphrase-file."
        )


def main():
    parser = argparse.ArgumentParser(description="CivicTrace Operational Release Utility")
    subparsers = parser.add_subparsers(dest="command")

    # backup
    p_backup = subparsers.add_parser("backup", help="Create atomic database & evidence backup")
    p_backup.add_argument("--out", "--out-dir", dest="out", default="civictrace_backup.tar.gz")
    p_backup.add_argument("--db", "--db-path", dest="db", default=None)
    p_backup.add_argument("--uploads", "--uploads-dir", dest="uploads", default=None)

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore and verify atomic database & evidence backup")
    p_restore.add_argument("--archive", "--in", dest="input_tar", required=True)
    p_restore.add_argument("--target-dir", "--db-target", dest="target_dir", required=True)
    p_restore.add_argument("--expected-public-key", dest="expected_public_key", default=None)

    # backup-keys
    p_bkeys = subparsers.add_parser("backup-keys", help="Create encrypted backup of signing keys")
    p_bkeys.add_argument("--out", dest="out", required=True)
    p_bkeys.add_argument("--passphrase", dest="passphrase", default=None, help="Passphrase for key encryption (WARNING: may leak in process list)")
    p_bkeys.add_argument("--passphrase-env", dest="passphrase_env", default=None, help="Name of environment variable containing the passphrase")
    p_bkeys.add_argument("--passphrase-file", dest="passphrase_file", default=None, help="Path to secure file containing the passphrase")
    p_bkeys.add_argument("--keys-dir", dest="keys_dir", default=None)

    # restore-keys
    p_rkeys = subparsers.add_parser("restore-keys", help="Restore encrypted signing keys with passphrase")
    p_rkeys.add_argument("--archive", dest="input_file", required=True)
    p_rkeys.add_argument("--passphrase", dest="passphrase", default=None, help="Passphrase for key decryption (WARNING: may leak in process list)")
    p_rkeys.add_argument("--passphrase-env", dest="passphrase_env", default=None, help="Name of environment variable containing the passphrase")
    p_rkeys.add_argument("--passphrase-file", dest="passphrase_file", default=None, help="Path to secure file containing the passphrase")
    p_rkeys.add_argument("--target-dir", dest="target_dir", default=None)

    # rotate-key
    p_rotate = subparsers.add_parser("rotate-key", help="Rotate Ed25519 system signing key")
    p_rotate.add_argument("--keyfile", dest="keyfile", default="./keys/signing_key.hex")

    # cleanup
    p_clean = subparsers.add_parser("cleanup-interrupted", help="Clean up dangling upload fragments")
    p_clean.add_argument("--uploads", "--uploads-dir", dest="uploads", default=None)
    p_clean.add_argument("--db", "--db-path", dest="db", default=None)
    p_clean.add_argument("--dry-run", action="store_true", default=False)

    args = parser.parse_args()
    if args.command == "backup":
        create_atomic_backup(args.out, args.db, args.uploads)
    elif args.command == "restore":
        restore_atomic_backup(args.input_tar, args.target_dir, getattr(args, "expected_public_key", None))
    elif args.command == "backup-keys":
        passphrase = _resolve_passphrase(
            passphrase=args.passphrase,
            passphrase_env=args.passphrase_env,
            passphrase_file=args.passphrase_file,
            prompt_text="Enter key backup encryption passphrase: ",
        )
        create_encrypted_key_backup(args.out, passphrase, args.keys_dir)
    elif args.command == "restore-keys":
        passphrase = _resolve_passphrase(
            passphrase=args.passphrase,
            passphrase_env=args.passphrase_env,
            passphrase_file=args.passphrase_file,
            prompt_text="Enter key backup decryption passphrase: ",
        )
        restore_encrypted_key_backup(args.input_file, passphrase, args.target_dir)
    elif args.command == "rotate-key":
        rotate_signing_key(args.keyfile)
    elif args.command == "cleanup-interrupted":
        cleanup_interrupted_uploads(args.uploads, getattr(args, "db", None), args.dry_run)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
