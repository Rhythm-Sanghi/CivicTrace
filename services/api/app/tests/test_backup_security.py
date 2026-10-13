import os
import sys
import io
import json
import tarfile
import hashlib
import sqlite3
import pytest

# Ensure root repo directory is resolvable for scripts
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from scripts.backup_restore import (  # noqa: E402
    create_atomic_backup,
    restore_atomic_backup,
    create_encrypted_key_backup,
    restore_encrypted_key_backup,
    compute_file_sha256,
)
from app.services.crypto_signer import SignerService  # noqa: E402


def test_backup_strictly_excludes_private_keys(tmp_path):
    """
    Security Guarantee:
    Application backups MUST strictly exclude private keys, secrets, and credentials.
    Even if a keys/ folder exists in the source environment, it must NEVER be packed.
    """
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (id INT, val TEXT)")
    conn.execute("INSERT INTO t VALUES (1, 'civic')")
    conn.commit()
    conn.close()

    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "evidence1.jpg").write_bytes(b"JPEG_MOCK_DATA")

    # Simulate keys directory containing private Ed25519 key
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    (keys_dir / "signing_key.hex").write_text("0123456789abcdef" * 4)

    backup_tar = str(tmp_path / "backup_app.tar.gz")
    create_atomic_backup(
        output_tar=backup_tar,
        db_path=str(db_file),
        uploads_dir=str(uploads_dir),
        keys_dir=str(keys_dir),  # Should be ignored/rejected
    )

    with tarfile.open(backup_tar, "r:gz") as tar:
        names = tar.getnames()
        for name in names:
            assert "signing_key" not in name, f"Private key leaked into backup: {name}"
            assert not name.startswith("keys"), f"Keys directory leaked into backup: {name}"

        # Confirm manifest does NOT track keys
        manifest_member = tar.extractfile("manifest.json")
        assert manifest_member is not None
        manifest = json.loads(manifest_member.read().decode("utf-8"))
        assert "keys" not in manifest or not manifest["keys"]
        assert manifest.get("security_policy", {}).get("private_keys_included") is False


def test_backup_consistent_pair_during_concurrent_upload_and_deletion(db_session, tmp_path):
    """
    Concurrency and Point-in-Time Consistency:
    During backup creation, concurrent uploads might be writing temporary fragments (.tmp, .part)
    or uncommitted files.
    The backup utility must:
    1. Only package committed evidence assets recorded in the snapshot database.
    2. Exclude in-flight fragments.
    3. Successfully restore and verify every single restored evidence hash.
    """
    db_file = str(tmp_path / "concurrency_test.db")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()

    # Create SQLite database with real evidence_assets table
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        CREATE TABLE evidence_assets (
            id TEXT PRIMARY KEY,
            file_name TEXT,
            file_path TEXT,
            file_hash TEXT
        )
        """
    )
    # 2 committed assets
    asset1_data = b"REAL_COMMITTED_EVIDENCE_1"
    asset2_data = b"REAL_COMMITTED_EVIDENCE_2"
    hash1 = hashlib.sha256(asset1_data).hexdigest()
    hash2 = hashlib.sha256(asset2_data).hexdigest()

    file1_path = uploads_dir / "asset_01.jpg"
    file2_path = uploads_dir / "asset_02.png"
    file1_path.write_bytes(asset1_data)
    file2_path.write_bytes(asset2_data)

    conn.execute(
        "INSERT INTO evidence_assets VALUES (?, ?, ?, ?)",
        ("id-1", "asset_01.jpg", "asset_01.jpg", hash1),
    )
    conn.execute(
        "INSERT INTO evidence_assets VALUES (?, ?, ?, ?)",
        ("id-2", "asset_02.png", "asset_02.png", hash2),
    )
    conn.commit()
    conn.close()

    # Simulate concurrent upload races:
    # A. In-flight upload temporary fragment (.tmp)
    (uploads_dir / "upload_stream.tmp").write_bytes(b"PARTIAL_UNCOMMITTED_BYTES")
    # B. In-flight upload part file (.part)
    (uploads_dir / "upload_partial.part").write_bytes(b"ANOTHER_PART")
    # C. Uncommitted file in uploads that is NOT in database
    (uploads_dir / "uncommitted_orphan.png").write_bytes(b"ORPHAN_UNCOMMITTED")

    backup_tar = str(tmp_path / "concurrent_backup.tar.gz")
    create_atomic_backup(
        output_tar=backup_tar,
        db_path=db_file,
        uploads_dir=str(uploads_dir),
    )

    # Verify backup contents
    with tarfile.open(backup_tar, "r:gz") as tar:
        names = tar.getnames()
        assert "uploads/asset_01.jpg" in names
        assert "uploads/asset_02.png" in names
        assert "uploads/upload_stream.tmp" not in names
        assert "uploads/upload_partial.part" not in names
        assert "uploads/uncommitted_orphan.png" not in names

    # Perform actual restore into fresh target directory
    restore_target = tmp_path / "restored_site"
    restore_target.mkdir()
    success = restore_atomic_backup(
        backup_tar=backup_tar,
        restore_dir=str(restore_target),
    )
    assert success is True

    # Verify every restored evidence file hash matches expected digest
    restored_asset1 = restore_target / "uploads" / "asset_01.jpg"
    restored_asset2 = restore_target / "uploads" / "asset_02.png"
    assert restored_asset1.exists()
    assert restored_asset2.exists()
    assert compute_file_sha256(str(restored_asset1)) == hash1
    assert compute_file_sha256(str(restored_asset2)) == hash2


def test_backup_distinguishes_accidental_corruption_from_malicious_replacement(tmp_path):
    """
    Security Guarantee:
    1. Accidental corruption (bit rot, truncated tar) is detected by SHA-256 digest mismatch.
    2. Malicious archive replacement (recomputed hashes signed by attacker key) is detected
       by digital signature verification against expected_public_key.
    """
    db_file = tmp_path / "auth_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE t (id INT)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "doc.txt").write_bytes(b"CIVIC_EVIDENCE_DOC")

    backup_tar = str(tmp_path / "genuine_backup.tar.gz")
    create_atomic_backup(
        output_tar=backup_tar,
        db_path=str(db_file),
        uploads_dir=str(uploads_dir),
    )
    trusted_public_key = SignerService.get_public_key_base64()

    # 1. Successful authentic restore with trusted public key
    restore_valid = tmp_path / "restore_valid"
    restore_valid.mkdir()
    assert restore_atomic_backup(
        backup_tar=backup_tar,
        restore_dir=str(restore_valid),
        expected_public_key=trusted_public_key,
    ) is True

    # 2. Accidental corruption: Corrupt database bytes inside archive
    corrupt_tar = str(tmp_path / "corrupted_archive.tar.gz")
    with tarfile.open(backup_tar, "r:gz") as z_in, tarfile.open(corrupt_tar, "w:gz") as z_out:
        for member in z_in.getmembers():
            content = z_in.extractfile(member).read()
            if member.name == "database.db":
                content = content + b"\x00\x01\x02CORRUPTED_BYTES"
            tinfo = tarfile.TarInfo(member.name)
            tinfo.size = len(content)
            z_out.addfile(tinfo, io.BytesIO(content))

    restore_corrupt = tmp_path / "restore_corrupt"
    restore_corrupt.mkdir()
    with pytest.raises(ValueError, match="CORRUPTION DETECTED: Database checksum mismatch"):
        restore_atomic_backup(
            backup_tar=corrupt_tar,
            restore_dir=str(restore_corrupt),
        )

    # 3. Malicious replacement: Attacker modifies database, updates manifest SHA-256,
    # and signs with an attacker-controlled key
    rogue_priv, rogue_pub = SignerService.generate_keypair()
    rogue_tar = str(tmp_path / "rogue_replacement.tar.gz")

    with tarfile.open(backup_tar, "r:gz") as z_in:
        manifest_raw = json.loads(z_in.extractfile("manifest.json").read().decode("utf-8"))
        doc_bytes = z_in.extractfile("uploads/doc.txt").read()

    rogue_db_bytes = b"COMPROMISED_DATABASE_CONTENT"
    rogue_db_hash = hashlib.sha256(rogue_db_bytes).hexdigest()

    manifest_raw["database_sha256"] = rogue_db_hash
    manifest_raw.pop("signature", None)
    manifest_raw.pop("signer_public_key", None)

    from app.core.security import canonical_json
    rogue_canonical = canonical_json(manifest_raw).encode("utf-8")
    rogue_sig = SignerService.sign_bytes(rogue_canonical, private_key_hex=rogue_priv)
    manifest_raw["signature"] = rogue_sig
    manifest_raw["signer_public_key"] = rogue_pub

    rogue_manifest_bytes = json.dumps(manifest_raw).encode("utf-8")

    with tarfile.open(rogue_tar, "w:gz") as z_out:
        t_db = tarfile.TarInfo("database.db")
        t_db.size = len(rogue_db_bytes)
        z_out.addfile(t_db, io.BytesIO(rogue_db_bytes))

        t_man = tarfile.TarInfo("manifest.json")
        t_man.size = len(rogue_manifest_bytes)
        z_out.addfile(t_man, io.BytesIO(rogue_manifest_bytes))

        t_doc = tarfile.TarInfo("uploads/doc.txt")
        t_doc.size = len(doc_bytes)
        z_out.addfile(t_doc, io.BytesIO(doc_bytes))

    # Without trusted key (checksum-only check): would pass hashes
    restore_rogue_noanchor = tmp_path / "restore_rogue_noanchor"
    restore_rogue_noanchor.mkdir()
    assert restore_atomic_backup(
        backup_tar=rogue_tar,
        restore_dir=str(restore_rogue_noanchor),
        expected_public_key=None,
    ) is True

    # With trusted public key anchor: REJECTS malicious archive replacement!
    restore_rogue_anchor = tmp_path / "restore_rogue_anchor"
    restore_rogue_anchor.mkdir()
    with pytest.raises(ValueError, match="TRUST ANCHOR VIOLATION: Manifest signer key does not match"):
        restore_atomic_backup(
            backup_tar=rogue_tar,
            restore_dir=str(restore_rogue_anchor),
            expected_public_key=trusted_public_key,
        )


def test_encrypted_key_backup_and_restore_cycle(tmp_path):
    """
    Ensures that signing keys can be securely backed up with PBKDF2/AES-GCM encryption,
    rejects incorrect passphrases, and successfully restores with correct passphrase.
    """
    keys_dir = tmp_path / "keys_source"
    keys_dir.mkdir()
    (keys_dir / "signing_key.hex").write_text("abcd" * 16)
    (keys_dir / "trusted_anchors_history.json").write_text(json.dumps([{"key": "test"}]))

    encrypted_file = str(tmp_path / "keys.enc")
    passphrase = "SecretPassphrase2026!Strong"

    # Create encrypted backup
    create_encrypted_key_backup(
        output_file=encrypted_file,
        passphrase=passphrase,
        keys_dir=str(keys_dir),
    )
    assert os.path.exists(encrypted_file)

    # Attempt restore with wrong passphrase -> Fails
    restore_dir = tmp_path / "keys_restored"
    with pytest.raises(ValueError, match="Decryption failed"):
        restore_encrypted_key_backup(
            input_file=encrypted_file,
            passphrase="WrongPassword!",
            target_dir=str(restore_dir),
        )

    # Restore with correct passphrase -> Succeeds
    restore_dir.mkdir(exist_ok=True)
    assert restore_encrypted_key_backup(
        input_file=encrypted_file,
        passphrase=passphrase,
        target_dir=str(restore_dir),
    ) is True

    assert (restore_dir / "signing_key.hex").read_text() == "abcd" * 16
    assert (restore_dir / "trusted_anchors_history.json").exists()
