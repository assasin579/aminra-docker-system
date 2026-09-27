"""Immutable official artifact storage for approved business documents.

This service intentionally separates business-uploaded `documents` from the
read-only official artifacts created after approval. It copies bytes out of the
upload tree, computes a content hash, and records immutable metadata in
`official_artifacts`.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./docs"))
OFFICIAL_ARTIFACTS_DIR = Path(os.getenv("OFFICIAL_ARTIFACTS_DIR", "./official_artifacts"))


def _safe_filename(name: str | None) -> str:
    cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in (name or "artifact")).strip()
    return cleaned or "artifact"


def _ensure_official_storage_outside_upload_dir() -> tuple[Path, Path]:
    upload_root = UPLOAD_DIR.resolve()
    official_root = OFFICIAL_ARTIFACTS_DIR.resolve()
    if official_root == upload_root or official_root.is_relative_to(upload_root):
        raise ValueError("OFFICIAL_ARTIFACTS_DIR must not be inside UPLOAD_DIR")
    official_root.mkdir(parents=True, exist_ok=True)
    return upload_root, official_root


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def create_official_artifact_for_document(db, *, document_id: str, approved_by_user_id: str | None) -> dict:
    """Copy an approved document to official storage and upsert metadata.

    The source must remain a normal business-uploaded document under UPLOAD_DIR;
    the copied artifact is stored under OFFICIAL_ARTIFACTS_DIR and exposed only
    through official-artifact APIs.
    """
    row = await db.fetchrow(
        """
        SELECT id, tenant_id, original_filename, file_path, file_size, mime_type,
               effective_date, next_review_date, retention_expires_at
          FROM documents
         WHERE id = $1 AND approval_status = 'approved'
        """,
        document_id,
    )
    if not row:
        raise ValueError("approved source document not found")

    upload_root, official_root = _ensure_official_storage_outside_upload_dir()
    existing = await db.fetchrow(
        """
        SELECT id, tenant_id, source_document_id, artifact_kind,
               original_filename, storage_path, file_size, mime_type, sha256,
               approved_by_user_id, approved_at, effective_date,
               next_review_date, retention_expires_at, created_at
          FROM official_artifacts
         WHERE source_document_id = $1 AND artifact_kind = 'approved_document'
        """,
        document_id,
    )
    if existing:
        existing_path = Path(existing["storage_path"]).resolve()
        if not existing_path.is_relative_to(official_root):
            raise ValueError("existing official artifact path is outside OFFICIAL_ARTIFACTS_DIR")
        if not existing_path.exists() or not existing_path.is_file():
            raise ValueError("existing official artifact file is missing")
        return dict(existing)

    source = Path(row["file_path"]).resolve()
    if not source.is_relative_to(upload_root):
        raise ValueError("source document path is outside UPLOAD_DIR")
    if not source.exists() or not source.is_file():
        raise ValueError("source document file is missing")

    tenant_dir = official_root / str(row["tenant_id"])
    tenant_dir.mkdir(parents=True, exist_ok=True)
    destination = tenant_dir / f"{document_id}_{uuid4().hex}_{_safe_filename(row['original_filename'])}"
    if not destination.resolve().is_relative_to(official_root):
        raise ValueError("official artifact destination is unsafe")

    shutil.copy2(source, destination)
    digest = _sha256_file(destination)
    artifact_row = await db.fetchrow(
        """
        INSERT INTO official_artifacts
            (tenant_id, source_document_id, artifact_kind, original_filename,
             storage_path, file_size, mime_type, sha256, approved_by_user_id,
             effective_date, next_review_date, retention_expires_at)
        VALUES ($1,$2,'approved_document',$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT (source_document_id, artifact_kind) DO UPDATE SET
             storage_path = official_artifacts.storage_path
        RETURNING id, tenant_id, source_document_id, artifact_kind,
                  original_filename, storage_path, file_size, mime_type, sha256,
                  approved_by_user_id, approved_at, effective_date,
                  next_review_date, retention_expires_at, created_at
        """,
        row["tenant_id"],
        row["id"],
        row["original_filename"],
        str(destination),
        destination.stat().st_size,
        row["mime_type"] or "application/octet-stream",
        digest,
        approved_by_user_id,
        row["effective_date"],
        row["next_review_date"],
        row["retention_expires_at"],
    )
    return dict(artifact_row)
