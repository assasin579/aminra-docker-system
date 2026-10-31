"""Canonical upload/reference-to-dossier transaction shared by both API entry points."""
from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from auth.upload_utils import validate_upload
from services.dossier_attachments import (
    validate_dossier_slot, find_idempotent_attachment, attach_document_reference,
)


log = logging.getLogger(__name__)

async def attach_dossier_document(
    db, *, dossier_id: UUID, tenant_id, actor_id, doc_type: str,
    idempotency_key: UUID, document_id: UUID | None = None, file: UploadFile | None = None,
):
    doc_type = doc_type.strip()
    if not doc_type or len(doc_type) > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Slot tài liệu không hợp lệ")
    if (document_id is None) == (file is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Chọn đúng một tài liệu có sẵn hoặc tệp mới")

    saved_path: Path | None = None
    try:
        async with db.transaction():
            dossier = await validate_dossier_slot(
                db, dossier_id=dossier_id, tenant_id=tenant_id, doc_type=doc_type,
            )
            content: bytes | None = None
            safe_name = ""
            mime_type = "application/octet-stream"
            if file is not None:
                content = await validate_upload(file)
                safe_name = "".join(
                    char if char.isalnum() or char in "._- " else "_"
                    for char in (file.filename or "file")
                ).strip() or "file"
                mime_type = file.content_type or mime_type
                content_digest = hashlib.sha256(content).hexdigest()
            else:
                content_digest = str(document_id)

            fingerprint_payload = {
                "action": "dossier-document-attachment-v1",
                "actor_id": str(actor_id),
                "tenant_id": str(tenant_id),
                "dossier_id": str(dossier_id),
                "requirements_version_id": str(dossier["requirements_version_id"]),
                "doc_type": doc_type,
                "document_id": str(document_id) if document_id else None,
                "content_sha256": content_digest,
                "filename": safe_name if file is not None else None,
                "mime_type": mime_type if file is not None else None,
            }
            request_sha256 = hashlib.sha256(
                json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            result = await find_idempotent_attachment(
                db, dossier=dossier, idempotency_key=idempotency_key,
                request_sha256=request_sha256, doc_type=doc_type, actor_id=actor_id,
            )
            if result is None and document_id is not None:
                result = await attach_document_reference(
                    db, dossier=dossier, document_id=document_id,
                    doc_type=doc_type, actor_id=actor_id,
                    idempotency_key=idempotency_key, request_sha256=request_sha256,
                )
            elif result is None:
                if file is None or content is None:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tệp tải lên không có")
                from auth.document_router import UPLOAD_DIR
                tenant_dir = UPLOAD_DIR / str(tenant_id)
                tenant_dir.mkdir(parents=True, exist_ok=True)
                doc_uuid = uuid4()
                saved_path = tenant_dir / f"{doc_uuid}_{safe_name}"
                if not saved_path.resolve().is_relative_to(tenant_dir.resolve()):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid file path")
                saved_path.write_bytes(content)
                inserted = await db.fetchrow(
                    """INSERT INTO documents
                              (id, filename, original_filename, file_path, file_size, mime_type,
                               user_id, tenant_id, doc_type)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                       RETURNING id, tenant_id, doc_type, filename, original_filename,
                                 status, compliance_score, version_number, uploaded_at""",
                    doc_uuid, saved_path.name, file.filename or safe_name, str(saved_path),
                    len(content), mime_type, actor_id, tenant_id, doc_type,
                )
                if not inserted:
                    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Không thể lưu metadata tài liệu")
                result = await attach_document_reference(
                    db, dossier=dossier, document_id=doc_uuid,
                    doc_type=doc_type, actor_id=actor_id,
                    idempotency_key=idempotency_key, request_sha256=request_sha256,
                )
        document = result["document"]
        return {
            "document_id": str(document["id"]),
            "doc_type": document["doc_type"],
            "attachment_state": "attached",
            "created_attachment": result["created"],
        }
    except Exception:
        if saved_path is not None:
            try:
                if saved_path.exists():
                    saved_path.unlink()
            except OSError:
                log.exception("Failed to remove uncommitted Dossier attachment file")
        raise



async def save_library_document(db, *, tenant_id, actor_id, filename, content,
                                mime_type, doc_type=None, evaluation_result=None):
    """Save one library file atomically; remove its bytes on DB/commit failure."""
    if not tenant_id or not actor_id:
        raise HTTPException(403, "Không xác định được doanh nghiệp hoặc người tải lên")
    from auth.document_router import UPLOAD_DIR
    tenant_dir = UPLOAD_DIR / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in filename).strip() or "file"
    document_id = uuid4()
    saved_path = tenant_dir / f"{document_id}_{safe_name}"
    try:
        async with db.transaction():
            saved_path.write_bytes(content)
            row = await db.fetchrow(
                """INSERT INTO documents
                   (id, filename, original_filename, file_path, file_size, mime_type,
                    user_id, tenant_id, doc_type, compliance_score, evaluation_result)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
                   RETURNING id, uploaded_at""",
                document_id, saved_path.name, filename, str(saved_path), len(content),
                mime_type, UUID(str(actor_id)), UUID(str(tenant_id)), doc_type,
                evaluation_result.get("compliance_score") if evaluation_result else None,
                json.dumps(evaluation_result, ensure_ascii=False) if evaluation_result else None,
            )
            if not row:
                raise HTTPException(500, "Không thể lưu metadata tài liệu")
        return {"id": str(row["id"]), "filename": filename, "doc_type": doc_type}
    except Exception:
        try:
            saved_path.unlink(missing_ok=True)
        except OSError:
            log.exception("Failed to clean uncommitted library upload")
        raise
