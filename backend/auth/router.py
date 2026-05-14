import logging
import magic
from uuid import UUID as _UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.responses import FileResponse
from asyncpg import Connection, UniqueViolationError

from .db import get_db
# Phase 4b: keep `password.hash_password` for invite/member-create flows
# (auditor invite, business member invite) — those still use email link with
# initial password. TODO Phase 4c: migrate to Keycloak invitation flow.
from .password import hash_password
from .jwt_utils import (
    get_current_user,
    require_business_owner,
)
from . import keycloak_admin
from .rate_limit import rate_limit_api
from .models import (
    BusinessRegisterRequest,
    ProviderRegisterRequest,
    InviteMemberRequest,
    UpdateMemberRequest,
    RegisterBusinessResponse,
    RegisterProviderResponse,
    UserProfile,
    MembersResponse,
    MemberItem,
    InviteAuditorRequest,
    AuditorItem,
    AuditorsResponse,
    CompanyProfileUpdate,
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


def _row_to_profile(row, member_count: int | None = None, industry_code: str | None = None) -> UserProfile:
    from auth.permissions import get_user_permissions

    perms = get_user_permissions(dict(row))
    return UserProfile(
        id=str(row["id"]),
        email=row["email"],
        role=row["role"],
        status=row["status"],
        company_name=row["company_name"],
        company_code=row.get("company_code"),
        is_owner=row["is_owner"],
        tenant_id=str(row["tenant_id"]) if row["tenant_id"] else None,
        member_count=member_count,
        address=row.get("address"),
        phone=row.get("phone"),
        representative_name=row.get("representative_name"),
        permissions=perms,
        industry_schema_id=str(row["industry_schema_id"]) if row.get("industry_schema_id") else None,
        industry_schema_code=industry_code,
    )


# ── Register business ──────────────────────────────────────────────────────────


@router.post("/business/register", response_model=RegisterBusinessResponse, status_code=201)
async def register_business(
    req: BusinessRegisterRequest, _: None = Depends(rate_limit_api)
):
    """Create business user in Keycloak (Phase 4b cutover — ADR-005).

    Post-creation, user logs in via Keycloak SSO. PG profile row is JIT
    auto-provisioned on first /auth/me call (see keycloak_validator.enrich_keycloak_claims).
    """
    try:
        keycloak_user_id = keycloak_admin.create_user(
            email=req.email,
            password=req.password,
            role="business",
            tenant_id=None,  # business owner = own tenant — set by JIT provisioning post-login
            is_owner=True,
            user_status="active",
            company_name=req.company_name,
        )
    except keycloak_admin.KeycloakAdminError as e:
        if "409" in str(e.detail) or "exists" in str(e.detail).lower():
            raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký cho tài khoản doanh nghiệp khác")
        raise

    log.info(f"[auth] Business registered in Keycloak: {req.email} (sub={keycloak_user_id})")
    return RegisterBusinessResponse(
        user_id=keycloak_user_id,
        email=req.email,
        status="active",
        message="Đăng ký thành công. Vui lòng đăng nhập qua Keycloak SSO.",
    )


# ── Register provider ──────────────────────────────────────────────────────────


@router.post("/provider/register", response_model=RegisterProviderResponse, status_code=201)
async def register_provider(
    req: ProviderRegisterRequest, _: None = Depends(rate_limit_api)
):
    """Create provider user in Keycloak with status=pending (admin approval required)."""
    try:
        keycloak_user_id = keycloak_admin.create_user(
            email=req.email,
            password=req.password,
            role="provider",
            tenant_id=None,
            is_owner=True,
            user_status="pending",
            company_name=req.company_name,
        )
    except keycloak_admin.KeycloakAdminError as e:
        if "409" in str(e.detail) or "exists" in str(e.detail).lower():
            raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký cho tổ chức khác")
        raise

    log.info(f"[auth] Provider registered in Keycloak (pending): {req.email} (sub={keycloak_user_id})")
    return RegisterProviderResponse(
        user_id=keycloak_user_id,
        email=req.email,
        status="pending",
        message="Tài khoản của bạn đang chờ xét duyệt. Admin sẽ xem xét và thông báo kết quả.",
    )


# ── Login + Refresh: REMOVED in Phase 4b (ADR-005 cutover 2026-05-14) ──────
# All authentication now goes through Keycloak SSO. FE redirects to
# auth.silvergem.org for login; backend validates Keycloak JWT via
# `get_current_user` in jwt_utils.py. Token refresh is handled by Keycloak's
# /token endpoint (RFC 6749) directly from FE.


# ── Get current user ───────────────────────────────────────────────────────────


@router.get("/me", response_model=UserProfile)
async def get_me(user: dict = Depends(get_current_user), db: Connection = Depends(get_db)):
    # Keycloak-issued tokens carry Keycloak's UUID as `sub`, not AMINRA DB
    # user id. Look up by email instead when user came from Keycloak.
    if user.get("_keycloak"):
        import uuid

        # Link by keycloak_sub (JWT `sub` = Keycloak user UUID) — durable link.
        # Email fallback for accounts created pre-Phase 4b (before keycloak_sub column existed).
        kc_sub = None
        try:
            kc_sub = uuid.UUID(str(user.get("sub", "")))
        except (ValueError, TypeError):
            kc_sub = None

        row = None
        if kc_sub:
            row = await db.fetchrow("SELECT * FROM users WHERE keycloak_sub = $1", kc_sub)
        if not row:
            row = await db.fetchrow("SELECT * FROM users WHERE email = $1", user["email"])
            # Backfill keycloak_sub on legacy row (linked by email).
            if row and kc_sub and row.get("keycloak_sub") != kc_sub:
                await db.execute("UPDATE users SET keycloak_sub = $1 WHERE id = $2", kc_sub, row["id"])

        if not row:
            # JIT auto-provision: Trust JWT claims (signed by Keycloak).
            # tenant_id from JWT may be a non-UUID slug — only persist if valid UUID;
            # for owners, post-INSERT UPDATE tenant_id = id (owner = own tenant root).
            tenant_uuid = None
            raw_tenant = user.get("tenant_id")
            if raw_tenant:
                try:
                    tenant_uuid = uuid.UUID(str(raw_tenant))
                except (ValueError, TypeError):
                    tenant_uuid = None

            kc_role = user.get("role") or "business"
            db_role = "business" if kc_role == "business" else "provider"
            is_owner = bool(user.get("is_owner", True))

            # Read industry_schema_code from Keycloak user attribute (set via
            # admin REST when seeding demo accounts or onboarding).
            industry_uuid = None
            industry_code = user.get("industry_schema_code")
            if industry_code:
                industry_uuid = await db.fetchval(
                    "SELECT id FROM industry_schemas WHERE code = $1", industry_code
                )

            row = await db.fetchrow(
                """
                INSERT INTO users (email, keycloak_sub, password_hash, role, company_name,
                                   status, is_owner, tenant_id, industry_schema_id)
                VALUES ($1, $2, NULL, $3::user_role, $4, $5::user_status, $6, $7, $8)
                ON CONFLICT (email) DO UPDATE SET keycloak_sub = EXCLUDED.keycloak_sub
                RETURNING *
                """,
                user["email"],
                kc_sub,
                db_role,
                user.get("company_name") or user["email"].split("@")[0],
                user.get("status") or "active",
                is_owner,
                tenant_uuid,
                industry_uuid,
            )
            # Owner without explicit tenant_id → set tenant_id = own id (own tenant root)
            if is_owner and row["tenant_id"] is None:
                await db.execute("UPDATE users SET tenant_id = id WHERE id = $1", row["id"])
                row = await db.fetchrow("SELECT * FROM users WHERE id = $1", row["id"])
    else:
        row = await db.fetchrow("SELECT * FROM users WHERE id = $1", user["sub"])
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    member_count = None
    if row["role"] == "business" and row["is_owner"]:
        member_count = await db.fetchval(
            "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false",
            row["id"],
        )
    industry_code = None
    if row.get("industry_schema_id"):
        industry_code = await db.fetchval(
            "SELECT code FROM industry_schemas WHERE id = $1",
            row["industry_schema_id"],
        )
    return _row_to_profile(row, member_count=member_count, industry_code=industry_code)


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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Tenant đã đạt giới hạn {MAX_MEMBERS} thành viên")

    pw_hash = hash_password(req.password)
    try:
        row = await db.fetchrow(
            """
            INSERT INTO users (email, password_hash, role, company_name,
                               status, is_owner, tenant_id, invited_by, ihc_role, department)
            VALUES ($1, $2, 'business', $3, 'active', false, $4, $5, $6, $7)
            RETURNING id, email, company_name, status, created_at
            """,
            req.email,
            pw_hash,
            req.display_name,
            tenant_id,
            owner["sub"],
            req.ihc_role or None,
            req.department or None,
        )
    except UniqueViolationError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email đã được đăng ký")

    log.info(f"[auth] Member invited: {req.email} → tenant {tenant_id}")
    return {
        "member_id": str(row["id"]),
        "email": row["email"],
        "display_name": row["company_name"],
        "tenant_id": tenant_id,
    }


# ── Invite link (no password required) ────────────────────────────────────────

from pydantic import BaseModel as _BM


class InviteLinkRequest(_BM):
    email: str
    display_name: str = ""
    ihc_role: str = ""
    department: str = ""


@router.post("/business/invite-link")
async def create_invite_link(
    req: InviteLinkRequest,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Create invite link — member sets their own password when accepting."""
    tenant_id = owner["tenant_id"]
    current_count = await db.fetchval("SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false", tenant_id)
    if current_count >= MAX_MEMBERS:
        raise HTTPException(422, f"Đã đạt giới hạn {MAX_MEMBERS} thành viên")

    # Check email not already registered
    existing = await db.fetchval("SELECT COUNT(*) FROM users WHERE email = $1", req.email)
    if existing:
        raise HTTPException(409, "Email đã được đăng ký")

    from uuid import uuid4 as _uuid4
    from datetime import timezone

    token = str(_uuid4()).replace("-", "")
    expires = datetime.now(timezone.utc) + timedelta(days=7)

    await db.execute(
        """
        INSERT INTO member_invites (tenant_id, email, invite_token, role, department, expires_at)
        VALUES ($1, $2, $3, $4, $5, $6)
    """,
        tenant_id,
        req.email,
        token,
        req.ihc_role or None,
        req.department or None,
        expires,
    )

    log.info(f"[auth] Invite link created for {req.email} → tenant {tenant_id}")
    return {
        "invite_token": token,
        "portal_url": f"/invite/{token}",
        "expires_at": expires.isoformat(),
        "email": req.email,
        "message": "Link mời đã tạo (hết hạn sau 7 ngày)",
    }


@router.get("/invite/{token}")
async def get_invite_info(token: str, db: Connection = Depends(get_db)):
    """Public: view invite info (no auth needed)."""
    row = await db.fetchrow(
        """
        SELECT i.*, u.company_name AS business_name
        FROM member_invites i
        JOIN users u ON u.id = i.tenant_id AND u.is_owner = true
        WHERE i.invite_token = $1
    """,
        token,
    )
    if not row:
        raise HTTPException(404, "Link không hợp lệ")
    if row["accepted_at"]:
        raise HTTPException(410, "Link đã được sử dụng")
    if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(410, "Link đã hết hạn")

    return {
        "email": row["email"],
        "business_name": row["business_name"],
        "role": row["role"],
        "department": row["department"],
    }


@router.post("/invite/{token}/accept")
async def accept_invite(token: str, request: Request, db: Connection = Depends(get_db)):
    """Public: member accepts invite and sets password."""
    body = await request.json()
    password = body.get("password", "")
    display_name = body.get("display_name", "")

    if len(password) < 10:
        raise HTTPException(400, "Mật khẩu phải có ít nhất 10 ký tự")

    row = await db.fetchrow("SELECT * FROM member_invites WHERE invite_token = $1", token)
    if not row:
        raise HTTPException(404, "Link không hợp lệ")
    if row["accepted_at"]:
        raise HTTPException(410, "Link đã được sử dụng")
    if row["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(410, "Link đã hết hạn")

    pw_hash = hash_password(password)
    try:
        user_row = await db.fetchrow(
            """
            INSERT INTO users (email, password_hash, role, company_name,
                               status, is_owner, tenant_id, ihc_role, department)
            VALUES ($1, $2, 'business', $3, 'active', false, $4, $5, $6)
            RETURNING id
        """,
            row["email"],
            pw_hash,
            display_name or row["email"],
            row["tenant_id"],
            row["role"],
            row["department"],
        )
    except UniqueViolationError:
        raise HTTPException(409, "Email đã được đăng ký")

    await db.execute("UPDATE member_invites SET accepted_at = NOW() WHERE id = $1", row["id"])

    log.info(f"[auth] Invite accepted: {row['email']} → tenant {row['tenant_id']}")
    return {"message": "Đã tham gia thành công! Bạn có thể đăng nhập ngay.", "email": row["email"]}


# ── Member permissions ─────────────────────────────────────────────────────────


@router.get("/business/members/{member_id}/permissions")
async def get_member_permissions(
    member_id: str,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    _validate_uuid(member_id)
    row = await db.fetchrow(
        "SELECT permissions FROM users WHERE id=$1 AND tenant_id=$2 AND is_owner=false", member_id, owner["tenant_id"]
    )
    if not row:
        raise HTTPException(404, "Thành viên không tồn tại")

    from auth.permissions import DEFAULT_PERMISSIONS, PERMISSION_LABELS
    import json

    perms = row["permissions"]
    if isinstance(perms, str):
        perms = json.loads(perms)
    perms = {**DEFAULT_PERMISSIONS, **(perms or {})}
    return {
        "permissions": perms,
        "labels": PERMISSION_LABELS,
    }


@router.put("/business/members/{member_id}/permissions")
async def update_member_permissions(
    member_id: str,
    request: Request,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Owner sets permissions for a member."""
    _validate_uuid(member_id)
    row = await db.fetchrow(
        "SELECT id FROM users WHERE id=$1 AND tenant_id=$2 AND is_owner=false", member_id, owner["tenant_id"]
    )
    if not row:
        raise HTTPException(404, "Thành viên không tồn tại")

    body = await request.json()
    import json
    from auth.permissions import DEFAULT_PERMISSIONS

    new_perms = {}
    for key in DEFAULT_PERMISSIONS:
        if key in body:
            new_perms[key] = bool(body[key])

    await db.execute("UPDATE users SET permissions = $1::jsonb WHERE id = $2", json.dumps(new_perms), member_id)

    log.info(f"[auth] Permissions updated for {member_id}: {new_perms}")
    return {"message": "Đã cập nhật quyền", "permissions": new_perms}


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
        members=[
            MemberItem(
                id=str(r["id"]),
                email=r["email"],
                display_name=r["company_name"],
                status=r["status"],
                ihc_role=r.get("ihc_role"),
                department=r.get("department"),
                created_at=r["created_at"],
            )
            for r in rows
        ],
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
        updates.append(f"ihc_role = ${idx}")
        params.append(req.ihc_role or None)
        idx += 1
    if req.department is not None:
        updates.append(f"department = ${idx}")
        params.append(req.department or None)
        idx += 1
    if req.display_name is not None:
        updates.append(f"company_name = ${idx}")
        params.append(req.display_name)
        idx += 1
    if not updates:
        return {"message": "Không có thay đổi"}
    params.extend([member_id, owner["tenant_id"]])
    result = await db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx} AND tenant_id = ${idx + 1} AND is_owner = false",
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
    lines.append("1. THÔNG TIN TỔ CHỨC")
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
        lines.append(f"3.{list(role_map.keys()).index(role) + 1} {role}")
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
        headers={"Content-Disposition": f'attachment; filename="IHC_{company_name.replace(" ", "_")}.docx"'},
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
        member_id,
        owner["tenant_id"],
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
        "SELECT COUNT(*) FROM users WHERE tenant_id = $1 AND is_owner = false",
        tenant_id,
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
            req.email,
            pw_hash,
            req.display_name,
            tenant_id,
            owner["sub"],
            req.specialty or None,
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
        auditors=[
            AuditorItem(
                id=str(r["id"]),
                email=r["email"],
                display_name=r["company_name"],
                specialty=r.get("department"),
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ],
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
        updates.append(f"company_name = ${idx}")
        params.append(req["display_name"])
        idx += 1
    if "specialty" in req:
        updates.append(f"department = ${idx}")
        params.append(req["specialty"] or None)
        idx += 1
    if "email" in req and req["email"]:
        # Validate email not taken by another provider user
        existing = await db.fetchrow(
            "SELECT id FROM users WHERE email=$1 AND role='provider' AND id != $2", req["email"], auditor_id
        )
        if existing:
            raise HTTPException(409, "Email đã được sử dụng bởi tài khoản khác")
        updates.append(f"email = ${idx}")
        params.append(req["email"])
        idx += 1
    if "password" in req and req["password"]:
        if len(req["password"]) < 8:
            raise HTTPException(400, "Mật khẩu tối thiểu 8 ký tự")
        updates.append(f"password_hash = ${idx}")
        params.append(hash_password(req["password"]))
        idx += 1

    if not updates:
        return {"message": "Không có thay đổi"}
    params.extend([auditor_id, tenant_id])
    result = await db.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id = ${idx} AND tenant_id = ${idx + 1} AND is_owner = false AND role = 'provider'",
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
        auditor_id,
        owner["tenant_id"] or owner["sub"],
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Auditor not found")


# ── Auditor Certificates ──────────────────────────────────────────────────────


@router.get("/provider/auditors/{auditor_id}/certificates")
async def list_auditor_certificates(
    auditor_id: str,
    owner: dict = Depends(require_provider_owner),
    db: Connection = Depends(get_db),
):
    """List certificate files for an auditor."""
    _validate_uuid(auditor_id)
    # Verify auditor belongs to this provider
    row = await db.fetchrow(
        "SELECT id FROM users WHERE id = $1 AND tenant_id = $2 AND role = 'provider'",
        auditor_id,
        owner["tenant_id"] or owner["sub"],
    )
    if not row:
        raise HTTPException(404, "Auditor không tồn tại")

    from pathlib import Path as _P

    cert_dir = _P("docs") / (owner["tenant_id"] or owner["sub"]) / "certificates" / auditor_id
    if not cert_dir.exists():
        return {"certificates": []}

    certs = []
    for f in sorted(cert_dir.iterdir()):
        if f.is_file():
            file_id = f.name.split("_", 1)[0]
            display_name = f.name.split("_", 1)[-1] if "_" in f.name else f.name
            certs.append(
                {
                    "id": file_id,
                    "filename": display_name,
                    "size": f.stat().st_size,
                    "uploaded_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
                }
            )
    return {"certificates": certs}


@router.post("/provider/auditors/{auditor_id}/certificates")
async def upload_auditor_certificate(
    auditor_id: str,
    file: UploadFile = File(...),
    owner: dict = Depends(require_provider_owner),
    db: Connection = Depends(get_db),
):
    """Upload a certificate file (PDF, DOCX, JPG, PNG) for an auditor."""
    _validate_uuid(auditor_id)
    row = await db.fetchrow(
        "SELECT id FROM users WHERE id = $1 AND tenant_id = $2 AND role = 'provider'",
        auditor_id,
        owner["tenant_id"] or owner["sub"],
    )
    if not row:
        raise HTTPException(404, "Auditor không tồn tại")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File quá lớn (tối đa 10MB)")

    import magic

    detected = magic.from_buffer(content, mime=True)
    allowed = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if detected not in allowed:
        raise HTTPException(400, f"Loại file không hợp lệ: {detected}")

    from pathlib import Path as _P
    import uuid as _uuid

    cert_dir = _P("docs") / (owner["tenant_id"] or owner["sub"]) / "certificates" / auditor_id
    cert_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(_uuid.uuid4())[:8]
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in (file.filename or "cert")).strip()
    save_path = cert_dir / f"{file_id}_{safe_name}"
    save_path.write_bytes(content)

    log.info(f"[certificates] Uploaded {save_path.name} for auditor {auditor_id}")
    return {"id": file_id, "filename": safe_name, "size": len(content)}


@router.get("/provider/auditors/{auditor_id}/certificates/{cert_id}/view")
async def view_auditor_certificate(
    auditor_id: str,
    cert_id: str,
    request: Request,
    token: str | None = None,
):
    """View certificate as PDF (convert if needed). Supports ?token= for window.open."""
    from auth.jwt_utils import decode_token as _decode

    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user = _decode(auth[7:])
    elif token:
        user = _decode(token)
    else:
        raise HTTPException(401, "Not authenticated")

    if user.get("role") != "provider":
        raise HTTPException(403)

    tenant_id = user.get("tenant_id") or user.get("sub")
    from pathlib import Path as _P

    cert_dir = _P("docs") / tenant_id / "certificates" / auditor_id

    target = None
    if cert_dir.exists():
        for f in cert_dir.iterdir():
            if f.name.startswith(cert_id):
                target = f
                break
    if not target:
        raise HTTPException(404, "Chứng chỉ không tồn tại")

    mime = magic.from_buffer(target.read_bytes()[:2048], mime=True)

    # PDF — serve directly
    if mime == "application/pdf":
        return FileResponse(path=str(target), media_type="application/pdf")

    # Images — serve directly with correct MIME
    if mime.startswith("image/"):
        return FileResponse(path=str(target), media_type=mime)

    # DOCX — convert to PDF
    import subprocess

    cache_dir = _P("data/preview_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_pdf = cache_dir / f"cert_{cert_id}.pdf"

    if cache_pdf.exists() and cache_pdf.stat().st_size > 0:
        return FileResponse(path=str(cache_pdf), media_type="application/pdf")

    import tempfile
    import shutil
    from starlette.concurrency import run_in_threadpool

    def _convert():
        pid_profile = tempfile.mkdtemp(prefix="lo_profile_")
        try:
            subprocess.run(
                [
                    "/usr/bin/libreoffice",
                    "--headless",
                    "--norestore",
                    "--nolockcheck",
                    f"-env:UserInstallation=file://{pid_profile}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(cache_dir.resolve()),
                    str(target.resolve()),
                ],
                capture_output=True,
                timeout=60,
                cwd=pid_profile,
                env={
                    "HOME": pid_profile,
                    "PATH": "/usr/bin:/usr/local/bin:/bin",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
            )
            lo_output = cache_dir / (target.stem + ".pdf")
            if lo_output.exists():
                lo_output.rename(cache_pdf)
        finally:
            shutil.rmtree(pid_profile, ignore_errors=True)

    await run_in_threadpool(_convert)
    if not cache_pdf.exists():
        raise HTTPException(500, "Chuyển đổi PDF thất bại")
    return FileResponse(path=str(cache_pdf), media_type="application/pdf")


@router.delete("/provider/auditors/{auditor_id}/certificates/{cert_id}")
async def delete_auditor_certificate(
    auditor_id: str,
    cert_id: str,
    owner: dict = Depends(require_provider_owner),
):
    """Delete a certificate file."""
    from pathlib import Path as _P

    cert_dir = _P("docs") / (owner["tenant_id"] or owner["sub"]) / "certificates" / auditor_id
    if cert_dir.exists():
        for f in cert_dir.iterdir():
            if f.name.startswith(cert_id):
                f.unlink()
                return {"message": "Đã xoá"}
    raise HTTPException(404, "Chứng chỉ không tồn tại")


# ── Meeting Minutes ───────────────────────────────────────────────────────────

from pathlib import Path as _Path
import uuid as _uuid
import shutil as _shutil
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
            files.append(
                {
                    "id": parts[0] if len(parts) > 1 else f.stem,
                    "filename": f.name,
                    "original_filename": original,
                    "file_size": stat.st_size,
                    "mime_type": _guess_mime(original),
                    "uploaded_at": _dt.utcfromtimestamp(stat.st_mtime).isoformat(),
                }
            )
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
    request: Request,
    token: str | None = None,
    db: Connection = Depends(get_db),
):
    """Serve a minutes file for viewing."""
    from auth.jwt_utils import decode_token as _decode

    # Support both Authorization header and ?token= query param (for window.open)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        owner = _decode(auth[7:])
    elif token:
        owner = _decode(token)
    else:
        raise HTTPException(401, "Not authenticated")
    if owner.get("role") != "business" or not owner.get("is_owner"):
        raise HTTPException(403, "Business owner access required")
    minutes_dir = DOCS_DIR / owner["tenant_id"] / "minutes"
    if not minutes_dir.exists():
        raise HTTPException(404, "Không tìm thấy biên bản")

    target = None
    for f in minutes_dir.iterdir():
        if f.name.startswith(file_id):
            target = f
            break
    if not target:
        raise HTTPException(404, "Không tìm thấy biên bản")

    mime = _guess_mime(target.name)

    # If already PDF, serve directly
    if mime == "application/pdf" or target.suffix.lower() == ".pdf":
        return FileResponse(path=str(target), media_type="application/pdf")

    # Convert to PDF for inline viewing (same approach as document preview)
    import subprocess

    cache_dir = _Path("data/preview_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_pdf = cache_dir / f"minutes_{file_id}.pdf"

    if cache_pdf.exists() and cache_pdf.stat().st_size > 0 and cache_pdf.stat().st_mtime >= target.stat().st_mtime:
        return FileResponse(path=str(cache_pdf), media_type="application/pdf")

    abs_cache = str(cache_dir.resolve())
    abs_file = str(target.resolve())

    import tempfile
    import shutil
    from starlette.concurrency import run_in_threadpool

    def _convert():
        pid_profile = tempfile.mkdtemp(prefix="lo_profile_")
        try:
            subprocess.run(
                [
                    "/usr/bin/libreoffice",
                    "--headless",
                    "--norestore",
                    "--nolockcheck",
                    f"-env:UserInstallation=file://{pid_profile}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    abs_cache,
                    abs_file,
                ],
                capture_output=True,
                timeout=60,
                cwd=pid_profile,
                env={
                    "HOME": pid_profile,
                    "PATH": "/usr/bin:/usr/local/bin:/bin",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8",
                },
            )
            lo_output = _Path(abs_cache) / (_Path(abs_file).stem + ".pdf")
            if lo_output.exists():
                lo_output.rename(cache_pdf.resolve())
        finally:
            shutil.rmtree(pid_profile, ignore_errors=True)

    await run_in_threadpool(_convert)

    if not cache_pdf.exists():
        raise HTTPException(500, "Chuyển đổi PDF thất bại")

    return FileResponse(path=str(cache_pdf), media_type="application/pdf")


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


# ── Company profile ───────────────────────────────────────────────────────────


@router.get("/company-profile")
async def get_company_profile(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    """Get company profile (from tenant owner) for template placeholder data."""
    if user["role"] != "business":
        raise HTTPException(403, "Chỉ dành cho tài khoản doanh nghiệp")

    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(400, "Tenant không xác định")

    row = await db.fetchrow(
        """SELECT company_name, email, address, phone, representative_name, manager_name
           FROM users WHERE id = $1 AND is_owner = true""",
        tenant_id,
    )
    if not row:
        raise HTTPException(404, "Không tìm thấy thông tin công ty")

    return {
        "company_name": row["company_name"],
        "email": row["email"],
        "address": row["address"],
        "phone": row["phone"],
        "representative_name": row["representative_name"],
        "manager_name": row["manager_name"],
    }


@router.put("/company-profile")
async def update_company_profile(
    req: CompanyProfileUpdate,
    owner: dict = Depends(require_business_owner),
    db: Connection = Depends(get_db),
):
    """Update company profile fields (owner only)."""
    # Resolve canonical AMINRA user.id. JWT sub may be Keycloak UUID (not
    # AMINRA DB id) when token comes via Keycloak SSO. Look up by email
    # when sub is not a valid AMINRA user row.
    import uuid as _uuid
    target_id = None
    raw_sub = owner.get("sub")
    if raw_sub:
        try:
            _uuid.UUID(str(raw_sub))
            exists = await db.fetchval(
                "SELECT 1 FROM users WHERE id = $1::uuid", raw_sub,
            )
            if exists:
                target_id = raw_sub
        except (ValueError, TypeError):
            pass
    if not target_id:
        row = await db.fetchrow(
            "SELECT id FROM users WHERE email = $1", owner["email"],
        )
        if not row:
            raise HTTPException(404, "User row not found. Call /auth/me first.")
        target_id = str(row["id"])

    await db.execute(
        """UPDATE users
           SET company_name = COALESCE(NULLIF($1, ''), company_name),
               representative_name = COALESCE(NULLIF($2, ''), representative_name),
               address = COALESCE(NULLIF($3, ''), address),
               phone = COALESCE(NULLIF($4, ''), phone),
               email = COALESCE(NULLIF($5, ''), email),
               manager_name = COALESCE(NULLIF($6, ''), manager_name)
           WHERE id = $7::uuid""",
        req.company_name,
        req.representative_name,
        req.address,
        req.phone,
        req.email,
        req.manager_name,
        target_id,
    )
    log.info(f"[auth] Company profile updated by {owner['sub']}")
    return {"message": "Đã cập nhật thông tin công ty"}


# ── Change password: REMOVED in Phase 4b (Keycloak owns passwords) ──────────
# User changes password via Keycloak account console at:
# https://auth.silvergem.org/realms/aminra/account/#/security/signing-in


# ── Upload company logo ──────────────────────────────────────────────────────

LOGO_DIR = _Path("docs/logos")
LOGO_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/company-logo")
async def upload_company_logo(
    file: UploadFile = File(...),
    owner: dict = Depends(require_business_owner),
):
    """Upload company logo (owner only). Max 2MB, PNG/JPG only."""
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Logo quá lớn (tối đa 2MB)")

    import magic

    detected = magic.from_buffer(content, mime=True)
    if detected not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(400, f"Chỉ chấp nhận PNG, JPG, hoặc WebP (phát hiện: {detected})")

    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[detected]
    logo_path = LOGO_DIR / f"{owner['tenant_id']}{suffix}"

    # Remove old logo with different extension
    for ext in (".png", ".jpg", ".webp"):
        old = LOGO_DIR / f"{owner['tenant_id']}{ext}"
        if old.exists() and old != logo_path:
            old.unlink()

    logo_path.write_bytes(content)
    log.info(f"[auth] Logo uploaded for tenant {owner['tenant_id']}")
    return {"message": "Đã upload logo", "url": f"/api/auth/company-logo/{owner['tenant_id']}"}


@router.get("/company-logo/{tenant_id}")
async def get_company_logo(tenant_id: str):
    """Serve company logo (public for display)."""
    for ext in (".png", ".jpg", ".webp"):
        path = LOGO_DIR / f"{tenant_id}{ext}"
        if path.exists():
            mime = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[ext[1:]]
            return FileResponse(path=str(path), media_type=mime)
    raise HTTPException(404, "Logo chưa được upload")


# ── Notification preferences ─────────────────────────────────────────────────


@router.get("/notification-preferences")
async def get_notification_preferences(
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    row = await db.fetchrow(
        "SELECT notify_eval_done, notify_submission_reply FROM users WHERE id = $1",
        user["sub"],
    )
    if not row:
        raise HTTPException(404)
    return {
        "notify_eval_done": row["notify_eval_done"] if row["notify_eval_done"] is not None else True,
        "notify_submission_reply": row["notify_submission_reply"]
        if row["notify_submission_reply"] is not None
        else True,
    }


@router.put("/notification-preferences")
async def update_notification_preferences(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Connection = Depends(get_db),
):
    body = await request.json()
    await db.execute(
        """UPDATE users SET notify_eval_done = $1, notify_submission_reply = $2 WHERE id = $3""",
        body.get("notify_eval_done", True),
        body.get("notify_submission_reply", True),
        user["sub"],
    )
    return {"message": "Đã cập nhật cài đặt thông báo"}


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
