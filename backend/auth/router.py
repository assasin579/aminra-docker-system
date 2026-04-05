import logging
from uuid import UUID as _UUID

from fastapi import APIRouter, Depends, HTTPException, status
from asyncpg import Connection, UniqueViolationError

from .db import get_db
from .password import hash_password, verify_password
from .jwt_utils import create_access_token, create_refresh_token, decode_refresh_token, get_current_user, require_business_owner
from .rate_limit import rate_limit_api
from .models import (
    BusinessRegisterRequest, ProviderRegisterRequest, LoginRequest,
    InviteMemberRequest, UpdateMemberRequest, LoginResponse, RegisterBusinessResponse,
    RegisterProviderResponse, UserProfile, MembersResponse, MemberItem,
    InviteAuditorRequest, AuditorItem, AuditorsResponse,
    RefreshRequest,
    MAX_MEMBERS,
)


def _validate_uuid(value: str) -> str:
    try:
        _UUID(value)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid ID format")
    return value

log = logging.getLogger("aminra.auth")
router = APIRouter()


def _row_to_profile(row, member_count: int | None = None) -> UserProfile:
    return UserProfile(
        id           = str(row["id"]),
        email        = row["email"],
        role         = row["role"],
        status       = row["status"],
        company_name = row["company_name"],
        company_code = row["company_code"],
        is_owner     = row["is_owner"],
        tenant_id    = str(row["tenant_id"]) if row["tenant_id"] else None,
        member_count = member_count,
    )


# ── Register business ──────────────────────────────────────────────────────────

@router.post("/business/register", response_model=RegisterBusinessResponse, status_code=201)
async def register_business(req: BusinessRegisterRequest, db: Connection = Depends(get_db), _: None = Depends(rate_limit_api)):
    pw_hash = hash_password(req.password)
    try:
        row = await db.fetchrow(
            """
            INSERT INTO users (email, password_hash, role, company_name, company_code,
                               status, is_owner, tenant_id)
            VALUES ($1, $2, 'business', $3, $4, 'active', true, NULL)
            RETURNING *
            """,
            req.email, pw_hash, req.company_name, req.company_code,
        )
    except UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    # Set tenant_id = own id (owner is their own tenant root)
    await db.execute("UPDATE users SET tenant_id = id WHERE id = $1", row["id"])
    row = await db.fetchrow("SELECT * FROM users WHERE id = $1", row["id"])

    profile = _row_to_profile(row, member_count=0)
    token_data = {
        "sub": str(row["id"]), "email": row["email"],
        "role": "business", "status": "active",
        "is_owner": True, "tenant_id": str(row["id"]),
    }
    token = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    log.info(f"[auth] Business registered: {req.email}")
    return RegisterBusinessResponse(access_token=token, refresh_token=refresh, user=profile)


# ── Register provider ──────────────────────────────────────────────────────────

@router.post("/provider/register", response_model=RegisterProviderResponse, status_code=201)
async def register_provider(req: ProviderRegisterRequest, db: Connection = Depends(get_db), _: None = Depends(rate_limit_api)):
    pw_hash = hash_password(req.password)
    try:
        row = await db.fetchrow(
            """
            INSERT INTO users (email, password_hash, role, company_name, company_code,
                               status, is_owner)
            VALUES ($1, $2, 'provider', $3, $4, 'pending', true)
            RETURNING id, email, status
            """,
            req.email, pw_hash, req.company_name, req.company_code,
        )
    except UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    log.info(f"[auth] Provider registered (pending): {req.email}")
    return RegisterProviderResponse(
        user_id = str(row["id"]),
        email   = row["email"],
        status  = row["status"],
        message = "Tài khoản của bạn đang chờ xét duyệt. Admin sẽ xem xét và thông báo kết quả.",
    )


# ── Login ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: Connection = Depends(get_db), _: None = Depends(rate_limit_api)):
    row = await db.fetchrow("SELECT * FROM users WHERE email = $1", req.email)
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email hoặc mật khẩu không đúng")

    if row["status"] == "pending":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tài khoản đang chờ xét duyệt")
    if row["status"] == "suspended":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tài khoản đã bị tạm khoá")

    # Auto-set tenant_id for provider owners (migration for existing accounts)
    if row["role"] == "provider" and row["is_owner"] and not row["tenant_id"]:
        await db.execute("UPDATE users SET tenant_id = id WHERE id = $1", row["id"])
        row = await db.fetchrow("SELECT * FROM users WHERE id = $1", row["id"])

    # Count members for owners
    member_count = None
    if row["is_owner"] and row["tenant_id"]:
        member_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false",
            row["id"],
        )

    profile = _row_to_profile(row, member_count=member_count)
    token_data = {
        "sub":       str(row["id"]),
        "email":     row["email"],
        "role":      row["role"],
        "status":    row["status"],
        "is_owner":  row["is_owner"],
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
    }
    token = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    return LoginResponse(access_token=token, refresh_token=refresh, user=profile)


# ── Refresh token ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(req: RefreshRequest, db: Connection = Depends(get_db), _: None = Depends(rate_limit_api)):
    payload = decode_refresh_token(req.refresh_token)

    row = await db.fetchrow("SELECT * FROM users WHERE id = $1", payload["sub"])
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if row["status"] != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User account is not active")

    member_count = None
    if row["is_owner"] and row["tenant_id"]:
        member_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false",
            row["id"],
        )

    profile = _row_to_profile(row, member_count=member_count)
    token_data = {
        "sub":       str(row["id"]),
        "email":     row["email"],
        "role":      row["role"],
        "status":    row["status"],
        "is_owner":  row["is_owner"],
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] else None,
    }
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)
    return LoginResponse(access_token=new_access, refresh_token=new_refresh, user=profile)


# ── Get current user ───────────────────────────────────────────────────────────

@router.get("/me", response_model=UserProfile)
async def get_me(user: dict = Depends(get_current_user), db: Connection = Depends(get_db)):
    row = await db.fetchrow("SELECT * FROM users WHERE id = $1", user["sub"])
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    member_count = None
    if row["role"] == "business" and row["is_owner"]:
        member_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false",
            row["id"],
        )
    return _row_to_profile(row, member_count=member_count)


# ── Invite member (business owner, max 7) ──────────────────────────────────────

@router.post("/business/invite", status_code=201)
async def invite_member(
    req: InviteMemberRequest,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    tenant_id = owner["tenant_id"]
    current_count = await db.fetchval(
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false",
        tenant_id,
    )
    if current_count >= MAX_MEMBERS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Tenant đã đạt giới hạn {MAX_MEMBERS} thành viên")

    pw_hash = hash_password(req.password)
    try:
        row = await db.fetchrow(
            """
            INSERT INTO users (email, password_hash, role, company_name,
                               status, is_owner, tenant_id, invited_by, ihc_role, department)
            VALUES ($1, $2, 'business', $3, 'active', false, $4, $5, $6, $7)
            RETURNING id, email, company_name, status, created_at
            """,
            req.email, pw_hash, req.display_name,
            tenant_id, owner["sub"], req.ihc_role or None, req.department or None,
        )
    except UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký")

    log.info(f"[auth] Member invited: {req.email} → tenant {tenant_id}")
    return {
        "member_id":    str(row["id"]),
        "email":        row["email"],
        "display_name": row["company_name"],
        "tenant_id":    tenant_id,
    }


# ── List members ───────────────────────────────────────────────────────────────

@router.get("/business/members", response_model=MembersResponse)
async def list_members(
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    rows = await db.fetch(
        """
        SELECT id, email, company_name, status, created_at, ihc_role, department
        FROM users WHERE tenant_id = $1 AND is_owner = false
        ORDER BY created_at
        """,
        owner["tenant_id"],
    )
    return MembersResponse(
        members=[MemberItem(
            id=str(r["id"]), email=r["email"],
            display_name=r["company_name"], status=r["status"],
            ihc_role=r.get("ihc_role"), department=r.get("department"),
            created_at=r["created_at"],
        ) for r in rows],
        count=len(rows),
    )


# ── Update member role/department ──────────────────────────────────────────────

@router.put("/business/members/{member_id}")
async def update_member(
    member_id: str,
    req: UpdateMemberRequest,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    _validate_uuid(member_id)
    updates = []
    params = []
    idx = 1
    if req.ihc_role is not None:
        updates.append(f"ihc_role = ${idx}"); params.append(req.ihc_role or None); idx += 1
    if req.department is not None:
        updates.append(f"department = ${idx}"); params.append(req.department or None); idx += 1
    if req.display_name is not None:
        updates.append(f"company_name = ${idx}"); params.append(req.display_name); idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    params.extend([member_id, owner["tenant_id"]])
    result = await db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx} AND tenant_id = ${idx+1} AND is_owner = false",
        *params,
    )
    if result == "UPDATE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return {"message": "Đã cập nhật thành viên"}


# ── Export IHC document ───────────────────────────────────────────────────────

@router.post("/business/export-ihc")
async def export_ihc(
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Export Internal Halal Committee document as DOCX."""
    tenant_id = owner["tenant_id"]

    # Get owner info
    owner_row = await db.fetchrow("SELECT company_name, email FROM users WHERE id = $1", owner["sub"])
    company_name = owner_row["company_name"] if owner_row else "N/A"

    # Get all members
    rows = await db.fetch(
        """SELECT company_name, email, ihc_role, department, created_at
           FROM users WHERE tenant_id = $1 AND is_owner = false
           ORDER BY created_at""",
        tenant_id,
    )

    from templates_docx._registry import build_docx
    from datetime import datetime
    import io

    # Build IHC content
    lines = []
    lines.append(f"1. THÔNG TIN TỔ CHỨC")
    lines.append(f"Tên tổ chức: {company_name}")
    lines.append(f"Ngày ban hành: {datetime.now().strftime('%d/%m/%Y')}")
    lines.append(f"Tổng số thành viên IHC: {len(rows)}")
    lines.append("")
    lines.append("2. CƠ CẤU BAN QUẢN LÝ HALAL NỘI BỘ (INTERNAL HALAL COMMITTEE)")
    lines.append("")

    # Table header
    lines.append("STT | Họ tên | Chức vụ IHC | Bộ phận | Email")
    for i, r in enumerate(rows, 1):
        name = r["company_name"] or "—"
        role = r["ihc_role"] or "Thành viên"
        dept = r["department"] or "—"
        email = r["email"] or "—"
        lines.append(f"{i} | {name} | {role} | {dept} | {email}")

    lines.append("")
    lines.append("3. TRÁCH NHIỆM VÀ QUYỀN HẠN")
    lines.append("")

    # Role-specific responsibilities
    role_map = {}
    for r in rows:
        role = r["ihc_role"] or "Thành viên"
        if role not in role_map:
            role_map[role] = []
        role_map[role].append(r["company_name"] or r["email"])

    for role, names in role_map.items():
        lines.append(f"3.{list(role_map.keys()).index(role)+1} {role}")
        lines.append(f"Thành viên: {', '.join(names)}")
        if "chairman" in role.lower() or "chủ tịch" in role.lower():
            lines.append("- Chịu trách nhiệm tổng thể về hệ thống đảm bảo Halal")
            lines.append("- Phê duyệt các quyết định liên quan đến Halal")
            lines.append("- Đại diện tổ chức trong các vấn đề Halal")
        elif "executive" in role.lower() or "chuyên viên" in role.lower():
            lines.append("- Giám sát hoạt động hàng ngày của hệ thống Halal")
            lines.append("- Đào tạo nhân viên về quy trình Halal")
            lines.append("- Kiểm tra và báo cáo vi phạm")
        elif "trưởng phòng" in role.lower() or "head" in role.lower():
            lines.append("- Đảm bảo tuân thủ Halal tại bộ phận phụ trách")
            lines.append("- Báo cáo kết quả kiểm soát lên Ban Quản lý Halal")
        else:
            lines.append("- Thực hiện kiểm soát Halal tại vị trí công việc")
            lines.append("- Báo cáo các vấn đề phát hiện")
        lines.append("")

    lines.append("4. CHẾ ĐỘ HỌP VÀ BÁO CÁO")
    lines.append("- Họp định kỳ: Hàng tháng hoặc khi có vấn đề phát sinh")
    lines.append("- Báo cáo: Hàng quý gửi Ban Giám đốc")
    lines.append("- Đào tạo: Tối thiểu 2 lần/năm cho toàn bộ thành viên IHC")

    content = "\n".join(lines)

    doc = build_docx(
        content,
        doc_type="internal_halal_committee",
        title=f"Internal Halal Committee — {company_name}",
        filename="IHC_Document",
    )

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    from fastapi.responses import Response
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="IHC_{company_name.replace(" ","_")}.docx"'},
    )


# ── Remove member ──────────────────────────────────────────────────────────────

@router.delete("/business/members/{member_id}", status_code=204)
async def remove_member(
    member_id: str,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    _validate_uuid(member_id)
    result = await db.execute(
        "DELETE FROM users WHERE id = $1 AND tenant_id = $2 AND is_owner = false",
        member_id, owner["tenant_id"],
    )
    if result == "DELETE 0":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")


# ── Provider Auditor Management ────────────────────────────────────────────────

from .jwt_utils import require_provider_owner

MAX_AUDITORS = 20

@router.post("/provider/auditors", status_code=201)
async def invite_auditor(
    req: InviteAuditorRequest,
    owner: dict = Depends(require_provider_owner),
    db: Connection = Depends(get_db),
):
    """Provider owner creates an auditor account."""
    tenant_id = owner["tenant_id"] or owner["sub"]
    # Auto-fix: set tenant_id on provider if missing
    if not owner["tenant_id"]:
        await db.execute("UPDATE users SET tenant_id = id WHERE id = $1", owner["sub"])

    current = await db.fetchval(
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false", tenant_id,
    )
    if current >= MAX_AUDITORS:
        raise HTTPException(422, f"Đã đạt giới hạn {MAX_AUDITORS} auditor")

    pw_hash = hash_password(req.password)
    try:
        row = await db.fetchrow(
            """INSERT INTO users (email, password_hash, role, company_name,
                                  status, is_owner, tenant_id, invited_by, department)
               VALUES ($1, $2, 'provider', $3, 'active', false, $4, $5, $6)
               RETURNING id, email, company_name, status, created_at""",
            req.email, pw_hash, req.display_name,
            tenant_id, owner["sub"], req.specialty or None,
        )
    except UniqueViolationError:
        raise HTTPException(409, "Email đã được đăng ký")

    log.info(f"[auth] Auditor invited: {req.email} → provider {tenant_id}")
    return {"auditor_id": str(row["id"]), "email": row["email"], "message": "Đã tạo auditor"}


@router.get("/provider/auditors", response_model=AuditorsResponse)
async def list_auditors(
    owner: dict = Depends(require_provider_owner),
    db: Connection = Depends(get_db),
):
    tenant_id = owner["tenant_id"] or owner["sub"]
    rows = await db.fetch(
        """SELECT id, email, company_name, status, created_at, department
           FROM users WHERE tenant_id = $1 AND is_owner = false AND role = 'provider'
           ORDER BY created_at""",
        tenant_id,
    )
    return AuditorsResponse(
        auditors=[AuditorItem(
            id=str(r["id"]), email=r["email"],
            display_name=r["company_name"], specialty=r.get("department"),
            status=r["status"], created_at=r["created_at"],
        ) for r in rows],
        count=len(rows),
    )


@router.put("/provider/auditors/{auditor_id}")
async def update_auditor(
    auditor_id: str,
    req: dict,
    owner: dict = Depends(require_provider_owner),
    db: Connection = Depends(get_db),
):
    _validate_uuid(auditor_id)
    tenant_id = owner["tenant_id"] or owner["sub"]
    updates, params, idx = [], [], 1
    if "display_name" in req and req["display_name"]:
        updates.append(f"company_name = ${idx}"); params.append(req["display_name"]); idx += 1
    if "specialty" in req:
        updates.append(f"department = ${idx}"); params.append(req["specialty"] or None); idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    params.extend([auditor_id, tenant_id])
    result = await db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx} AND tenant_id = ${idx+1} AND is_owner = false AND role = 'provider'",
        *params,
    )
    if result == "UPDATE 0":
        raise HTTPException(404, "Auditor not found")
    return {"message": "Đã cập nhật auditor"}


@router.delete("/provider/auditors/{auditor_id}", status_code=204)
async def remove_auditor(
    auditor_id: str,
    owner: dict = Depends(require_provider_owner),
    db: Connection = Depends(get_db),
):
    _validate_uuid(auditor_id)
    result = await db.execute(
        "DELETE FROM users WHERE id = $1 AND tenant_id = $2 AND is_owner = false AND role = 'provider'",
        auditor_id, owner["tenant_id"] or owner["sub"],
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Auditor not found")


# ── Meeting Minutes ───────────────────────────────────────────────────────────

from fastapi import UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path as _Path
import uuid as _uuid, shutil as _shutil
from datetime import datetime as _dt

DOCS_DIR = _Path("docs")


@router.get("/business/minutes")
async def list_minutes(
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """List all meeting minutes for the tenant."""
    minutes_dir = DOCS_DIR / owner["tenant_id"] / "minutes"
    if not minutes_dir.exists():
        return {"minutes": []}

    files = []
    for f in sorted(minutes_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            stat = f.stat()
            # Filename format: {uuid}_{original_name}
            parts = f.name.split("_", 1)
            original = parts[1] if len(parts) > 1 else f.name
            files.append({
                "id": parts[0] if len(parts) > 1 else f.stem,
                "filename": f.name,
                "original_filename": original,
                "file_size": stat.st_size,
                "mime_type": _guess_mime(original),
                "uploaded_at": _dt.utcfromtimestamp(stat.st_mtime).isoformat(),
            })
    return {"minutes": files}


@router.post("/business/minutes")
async def upload_minutes(
    owner: dict = Depends(require_business_owner),
    file: UploadFile = File(...),
):
    """Upload a meeting minutes file."""
    minutes_dir = DOCS_DIR / owner["tenant_id"] / "minutes"
    minutes_dir.mkdir(parents=True, exist_ok=True)

    doc_uuid = str(_uuid.uuid4())[:8]
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (file.filename or "minutes")).strip()
    save_path = minutes_dir / f"{doc_uuid}_{safe_name}"

    if not save_path.resolve().is_relative_to(minutes_dir.resolve()):
        raise HTTPException(400, "Invalid file path")

    with open(save_path, "wb") as f:
        _shutil.copyfileobj(file.file, f)

    log.info(f"[minutes] Uploaded {safe_name} for tenant {owner['tenant_id']}")
    return {
        "id": doc_uuid,
        "filename": save_path.name,
        "original_filename": safe_name,
        "message": "Đã upload biên bản họp",
    }


@router.get("/business/minutes/{file_id}/view")
async def view_minutes(
    file_id: str,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Serve a minutes file for viewing."""
    minutes_dir = DOCS_DIR / owner["tenant_id"] / "minutes"
    if not minutes_dir.exists():
        raise HTTPException(404, "Không tìm thấy biên bản")

    for f in minutes_dir.iterdir():
        if f.name.startswith(file_id):
            return FileResponse(path=str(f), filename=f.name.split("_", 1)[-1],
                                media_type=_guess_mime(f.name))

    raise HTTPException(404, "Không tìm thấy biên bản")


@router.delete("/business/minutes/{file_id}")
async def delete_minutes(
    file_id: str,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Delete a minutes file."""
    minutes_dir = DOCS_DIR / owner["tenant_id"] / "minutes"
    if not minutes_dir.exists():
        raise HTTPException(404, "Không tìm thấy biên bản")

    for f in minutes_dir.iterdir():
        if f.name.startswith(file_id):
            f.unlink()
            log.info(f"[minutes] Deleted {f.name} for tenant {owner['tenant_id']}")
            return {"message": "Đã xoá biên bản"}

    raise HTTPException(404, "Không tìm thấy biên bản")


def _guess_mime(filename: str) -> str:
    ext = _Path(filename).suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }.get(ext, "application/octet-stream")
