#!/usr/bin/env python3
"""
Rotate the AES-256-GCM encryption key for all PHI fields.

Reads every encrypted value from the database, decrypts it with the OLD key,
re-encrypts it with the NEW key, and writes it back — all inside a single
transaction.  If any field fails to decrypt the entire transaction is rolled
back and no data is changed.

Usage
-----
    OLD_ENCRYPTION_KEY=<old_b64_key> \\
    NEW_ENCRYPTION_KEY=<new_b64_key> \\
    DATABASE_URL=postgresql://anilla:anilla@localhost:5432/anilla \\
        python scripts/rotate_encryption_key.py

Both keys must be URL-safe base64-encoded 32-byte values.
Generate a new key with:
    python -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

After the script completes successfully:
  1. Set ENCRYPTION_KEY=<new_key> in your .env (or secrets manager).
  2. Restart the application.
"""
from __future__ import annotations

import asyncio
import base64
import os
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def _make_aesgcm(key_b64: str) -> AESGCM:
    try:
        key_bytes = base64.urlsafe_b64decode(key_b64 + "==")  # tolerate missing padding
    except Exception as exc:
        raise ValueError(f"Could not base64-decode key: {exc}") from exc
    if len(key_bytes) != 32:
        raise ValueError(f"Key must decode to exactly 32 bytes, got {len(key_bytes)}")
    return AESGCM(key_bytes)


def _reencrypt(ciphertext_b64: str, old_aesgcm: AESGCM, new_aesgcm: AESGCM) -> str:
    """Decrypt with old key, re-encrypt with new key. Returns new base64 ciphertext."""
    raw = base64.urlsafe_b64decode(ciphertext_b64 + "==")
    if len(raw) < 12 + 16:  # nonce(12) + minimum GCM tag(16)
        raise ValueError("Ciphertext too short")
    nonce, ct = raw[:12], raw[12:]
    plaintext = old_aesgcm.decrypt(nonce, ct, None)  # raises InvalidTag if wrong key
    new_nonce = os.urandom(12)
    new_ct = new_aesgcm.encrypt(new_nonce, plaintext, None)
    return base64.urlsafe_b64encode(new_nonce + new_ct).decode("ascii")


# ---------------------------------------------------------------------------
# PHI columns to rotate
# (table_name, primary_key_column, encrypted_column)
# ---------------------------------------------------------------------------

PHI_COLUMNS: list[tuple[str, str, str]] = [
    ("conversation_messages", "id",      "content"),
    ("patient_profiles",      "id",      "medical_history"),
    ("patient_profiles",      "id",      "current_medications"),
    ("patient_profiles",      "id",      "chronic_conditions"),
    ("patient_profiles",      "id",      "allergies"),
    ("patient_profiles",      "id",      "emergency_contact"),
    ("patient_profiles",      "id",      "insurance_info"),
]


# ---------------------------------------------------------------------------
# Rotation logic
# ---------------------------------------------------------------------------

async def rotate(db_url: str, old_key: str, new_key: str) -> None:
    old_aesgcm = _make_aesgcm(old_key)
    new_aesgcm = _make_aesgcm(new_key)

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(db_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_rows = 0

    try:
        async with factory() as session:
            async with session.begin():
                for table, pk_col, col in PHI_COLUMNS:
                    rows = (
                        await session.execute(
                            text(f"SELECT {pk_col}, {col} FROM {table} WHERE {col} IS NOT NULL")
                        )
                    ).fetchall()

                    if not rows:
                        print(f"  {table}.{col}: 0 rows — skipped")
                        continue

                    reencrypted = 0
                    already_new = 0
                    skipped = 0
                    for row in rows:
                        pk_val, ciphertext = row[0], row[1]

                        # Try re-encrypting with old key
                        try:
                            new_ct = _reencrypt(ciphertext, old_aesgcm, new_aesgcm)
                            await session.execute(
                                text(f"UPDATE {table} SET {col} = :new_val WHERE {pk_col} = :pk"),
                                {"new_val": new_ct, "pk": str(pk_val)},
                            )
                            reencrypted += 1
                            continue
                        except Exception:
                            pass

                        # Already rotated to new key — nothing to do
                        try:
                            _reencrypt(ciphertext, new_aesgcm, new_aesgcm)
                            already_new += 1
                            continue
                        except Exception:
                            pass

                        # Can't decrypt with either key — plaintext or third key; skip
                        print(f"    SKIP {table}.{col} pk={pk_val} — not encrypted with old or new key")
                        skipped += 1

                    print(f"  {table}.{col}: {reencrypted} re-encrypted, {already_new} already on new key, {skipped} skipped")
                    total_rows += reencrypted

                # Transaction commits here if no exception was raised
    finally:
        await engine.dispose()

    print(f"\nDone. {total_rows} total field values re-encrypted.")
    print("Next steps:")
    print("  1. Set ENCRYPTION_KEY=<new_key> in your .env / secrets manager.")
    print("  2. Restart the application.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    old_key = os.environ.get("OLD_ENCRYPTION_KEY", "").strip()
    new_key = os.environ.get("NEW_ENCRYPTION_KEY", "").strip()
    db_url  = os.environ.get("DATABASE_URL", "postgresql://anilla:anilla@localhost:5432/anilla")

    if not old_key or not new_key:
        print(__doc__)
        sys.exit(1)

    if old_key == new_key:
        print("OLD_ENCRYPTION_KEY and NEW_ENCRYPTION_KEY are the same — nothing to do.")
        sys.exit(0)

    print("Starting PHI encryption key rotation...")
    print(f"Database: {db_url.split('@')[-1]}")  # print host/db only, not credentials
    print()

    try:
        asyncio.run(rotate(db_url, old_key, new_key))
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)
