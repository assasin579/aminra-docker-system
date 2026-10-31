"""Required evidence coverage is a prerequisite for sending a bound dossier."""
from fastapi import HTTPException


async def validate_submission_requirements(db, *, tenant_id, requirements_version_id, document_ids):
    profile = await db.fetchrow(
        "SELECT state FROM standard_requirement_versions WHERE id=$1", requirements_version_id,
    )
    if not profile or profile['state'] != 'published':
        raise HTTPException(409, "Bộ hồ sơ chưa gắn bộ yêu cầu đã công bố của tiêu chuẩn")
    slots = await db.fetch(
        "SELECT doc_type,required FROM standard_requirement_version_slots WHERE requirements_version_id=$1 ORDER BY display_order,doc_type",
        requirements_version_id,
    )
    required = [slot for slot in slots if slot['required']]
    if not required:
        raise HTTPException(409, "Tiêu chuẩn chưa có danh sách tài liệu bắt buộc hợp lệ")
    documents = await db.fetch(
        "SELECT id,doc_type FROM documents WHERE tenant_id=$1 AND id=ANY($2::uuid[])", tenant_id, document_ids,
    )
    types = [row['doc_type'] for row in documents]
    allowed = {slot['doc_type'] for slot in slots}
    if any(doc_type not in allowed for doc_type in types):
        raise HTTPException(400, "Tài liệu không thuộc bộ yêu cầu đã công bố của tiêu chuẩn")
    typed = [doc_type for doc_type in types if doc_type is not None]
    if len(set(typed)) != len(typed):
        raise HTTPException(400, "Mỗi loại tài liệu chỉ được gửi một tài liệu đại diện")
    missing = [row['doc_type'] for row in required if row['doc_type'] not in types]
    if missing:
        raise HTTPException(400, "Bộ hồ sơ còn thiếu loại tài liệu bắt buộc: " + ", ".join(missing))

    # Keep eligibility stable until the surrounding submission transaction commits.
    for doc_type in sorted(set(typed)):
        await db.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))",f"document-current-type:{tenant_id}:{doc_type}")
    selected = await db.fetch(
        """SELECT DISTINCT ON (d.doc_type) d.id,d.doc_type
           FROM documents d JOIN document_current_versions cv ON cv.current_document_id=d.id AND cv.tenant_id=d.tenant_id
           WHERE d.tenant_id=$1 AND d.doc_type=ANY($2::text[])
           ORDER BY d.doc_type,cv.selected_at DESC,d.uploaded_at DESC,d.id""",tenant_id,typed,
    )
    official = {row['doc_type']:row['id'] for row in selected}
    if any(official.get(row['doc_type']) != row['id'] for row in documents):
        raise HTTPException(409, "Chủ tài khoản doanh nghiệp cần chọn đúng bản chính của từng loại tài liệu trước khi gửi")
