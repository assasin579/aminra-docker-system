"""Curated placeholder content for PDF templates when user data is incomplete.

Real data from DB / payload always wins. This module is a fallback layer
that the FilterPipeline consults via PlaceholderFillerFilter so PDFs render
with meaningful Halal-domain content instead of "—" everywhere when a
tenant hasn't yet populated their profile or the admin hasn't uploaded
template config.

Decoupled from tests/fixtures/ on purpose:
- tests/fixtures/ may change to optimise visual regression baselines
  (e.g. trimmed for faster snapshot runs).
- This file is what PRODUCTION renders fall back to — should be reviewed
  by Halal Lead before any change since it's user-visible.

Discipline:
- Identity fields (business_name, *_date) NEVER appear here — those must
  always come from the actual user/tenant.
- Long free-text fields hold realistic, audit-ready Halal language (drawn
  from MS 1500:2019, MPPHM 2020 patterns).
- Lists hold 3-6 representative items so a 4-page PDF doesn't look starved.
- All content is in Vietnamese (lang='vi'); when an 'en' equivalent ships
  it'll go in a parallel module.

Update cadence: review every 90 days alongside the brain review.
"""

from __future__ import annotations

# ── Common short scalar placeholder for identity-style fields ──────────────

UNSET_TEXT = "[Chưa cập nhật]"


# ── Per-doc_type fallback content ──────────────────────────────────────────

PLACEHOLDER_DATA: dict[str, dict] = {

    # ── company_profile ────────────────────────────────────────────────────
    "company_profile": {
        "tax_code": UNSET_TEXT,
        "address": UNSET_TEXT,
        "factory_address": UNSET_TEXT,
        "phone": UNSET_TEXT,
        "email": UNSET_TEXT,
        "website": UNSET_TEXT,
        "representative": UNSET_TEXT,
        "founded_year": None,
        "employee_count": None,
        "charter_capital": UNSET_TEXT,
        "halal_commitment": (
            "Doanh nghiệp cam kết tuân thủ đầy đủ tiêu chuẩn Halal MS 1500:2019 "
            "trong toàn bộ chu trình sản xuất — từ lựa chọn nguồn nguyên liệu, "
            "quy trình chế biến, lưu kho, đóng gói đến phân phối thành phẩm cuối cùng. "
            "Mọi hoạt động được giám sát bởi Ban Halal nội bộ và tuân thủ MPPHM 2020."
        ),
        "business_activities": [
            "Sản xuất và chế biến thực phẩm Halal",
            "Đóng gói và phân phối sản phẩm tới thị trường trong nước và xuất khẩu",
            "Đào tạo nhân sự và đối tác chuỗi cung ứng về tiêu chuẩn Halal",
        ],
        "products": [
            {
                "name": "Sản phẩm Halal mẫu",
                "description": "Mô tả chi tiết sản phẩm đáp ứng tiêu chuẩn MS 1500:2019.",
                "annual_output": UNSET_TEXT,
            },
        ],
    },

    # ── halal_policy ──────────────────────────────────────────────────────
    "halal_policy": {
        "policy_id": "POL-HAL-001",
        "version": "1.0",
        "mission_statement": (
            "Trở thành doanh nghiệp tin cậy trong cộng đồng Hồi giáo — cung cấp "
            "sản phẩm tuân thủ tuyệt đối tiêu chuẩn Halal, được sản xuất minh bạch, "
            "có truy xuất nguồn gốc đầy đủ và đảm bảo an toàn cho người tiêu dùng."
        ),
        "vision_statement": (
            "Đến năm 2030, sản phẩm của doanh nghiệp được tin dùng tại các thị trường "
            "Halal trọng điểm — góp phần phát triển ngành Halal Việt Nam và hội nhập "
            "vào nền kinh tế Hồi giáo toàn cầu."
        ),
        "halal_commitment": (
            "Chúng tôi cam kết trước Allah SWT, người tiêu dùng Hồi giáo và các Tổ chức "
            "Chứng nhận Halal rằng mọi sản phẩm mang thương hiệu doanh nghiệp tuyệt đối "
            "tuân thủ luật Sharia về Halal — không chứa nguyên liệu Haram, không tiếp xúc "
            "với Najis, được chế biến trong cơ sở đã được vệ sinh và phân tách Halal đúng "
            "quy định MPPHM 2020. Cam kết này không thể thương lượng và không có ngoại lệ."
        ),
        "scope_of_application": (
            "Chính sách này áp dụng cho 100% sản phẩm, dịch vụ, cơ sở sản xuất và toàn bộ "
            "nhân sự của doanh nghiệp. Áp dụng cho mọi nhà thầu phụ và đối tác chuỗi cung "
            "ứng đã ký NDA Halal."
        ),
        "commitment_clauses": [
            {"clause_no": 1, "title": "Nguyên liệu đầu vào chỉ Halal",
             "content": "Toàn bộ nguyên liệu thô, phụ gia, bao bì tiếp xúc thực phẩm phải có chứng nhận Halal còn hiệu lực từ tổ chức được công nhận."},
            {"clause_no": 2, "title": "Phân tách vật lý hoàn toàn",
             "content": "Cơ sở sản xuất duy trì phân tách vật lý 100% — không sản xuất sản phẩm non-Halal trong cùng nhà máy."},
            {"clause_no": 3, "title": "Vệ sinh và Sertu đúng Sharia",
             "content": "Mọi thiết bị, dụng cụ được vệ sinh đúng quy trình. Sertu áp dụng khi tiếp xúc Najis Mughallazah theo MPPHM 2020 §7.2."},
            {"clause_no": 4, "title": "Truy xuất nguồn gốc đầy đủ",
             "content": "Mọi lô sản phẩm có Batch ID duy nhất, lưu vĩnh viễn. Truy xuất xuôi/ngược hoàn thành trong ≤ 4 giờ."},
            {"clause_no": 5, "title": "Đào tạo Halal bắt buộc",
             "content": "100% nhân sự liên quan trực tiếp Halal hoàn thành đào tạo 8 giờ trước khi bắt đầu công việc; đào tạo lại 4 giờ/năm."},
            {"clause_no": 6, "title": "Halal Committee giám sát độc lập",
             "content": "Ban Halal nội bộ (IHC) báo cáo trực tiếp Tổng giám đốc và có quyền dừng dây chuyền nếu phát hiện vi phạm."},
            {"clause_no": 7, "title": "Cải tiến liên tục",
             "content": "Hệ thống Đảm bảo Halal được rà soát mỗi 12 tháng. KPI Halal báo cáo Hội đồng quản trị mỗi quý."},
        ],
        "halal_committee": [
            {"role": "Chủ tịch Ban (Chairperson)", "name": UNSET_TEXT, "department": "Đảm bảo chất lượng"},
            {"role": "Thư ký Ban (Secretary)", "name": UNSET_TEXT, "department": "Halal Compliance"},
            {"role": "Sharia Advisor (Hồi giáo)", "name": UNSET_TEXT, "department": "Cố vấn độc lập"},
        ],
        "references": [
            "MS 1500:2019 — Halal Food: General Requirements",
            "MS 2424:2012 — Halal Pharmaceuticals: General Guidelines",
            "TCVN 12944:2020 — Thực phẩm Halal — Yêu cầu chung",
            "JAKIM Manual Prosedur Pensijilan Halal Malaysia (MPPHM 2020)",
            "HCA-VN — Quy định cấp giấy chứng nhận Halal Việt Nam",
            "Codex Alimentarius CAC/GL 24-1997",
        ],
        "signatories": [
            {"name": UNSET_TEXT, "title": "Tổng giám đốc"},
            {"name": UNSET_TEXT, "title": "Halal Lead — Chủ tịch IHC"},
        ],
    },

    # ── has_manual / halal_manual (alias share placeholder) ───────────────
    "has_manual": {
        "manual_id": "MAN-HAS-001",
        "version": "1.0",
        "introduction": (
            "Sổ tay này mô tả Hệ thống Đảm bảo Halal (Halal Assurance System — HAS) "
            "tại doanh nghiệp, được thiết lập theo MS 1500:2019, MPPHM 2020 và TCVN "
            "12944:2020. Tài liệu là cấu trúc cốt lõi cho hệ thống quản lý Halal — định "
            "nghĩa chính sách, vai trò, quy trình kiểm soát và cơ chế cải tiến liên tục."
        ),
        "abbreviations": [
            {"abbr": "HAS", "meaning": "Halal Assurance System — Hệ thống Đảm bảo Halal"},
            {"abbr": "IHC", "meaning": "Internal Halal Committee — Ban Halal nội bộ"},
            {"abbr": "SOP", "meaning": "Standard Operating Procedure — Quy trình vận hành chuẩn"},
            {"abbr": "CCP", "meaning": "Critical Control Point — Điểm tới hạn (HACCP)"},
            {"abbr": "NCR", "meaning": "Non-Conformance Report — Phiếu báo cáo không phù hợp"},
            {"abbr": "JAKIM", "meaning": "Department of Islamic Development Malaysia"},
            {"abbr": "HCA-VN", "meaning": "Halal Certification Authority Vietnam"},
            {"abbr": "Najis", "meaning": "Vật ô uế theo Sharia (3 cấp: Mughallazah, Mutawassitah, Mukhaffafah)"},
            {"abbr": "Sertu", "meaning": "Quy trình tẩy uế đặc biệt theo Sharia (rửa 7 lần với 1 lần dùng đất sạch)"},
        ],
        "halal_policy_summary": (
            "Doanh nghiệp cam kết trước cộng đồng Hồi giáo và các Tổ chức Chứng nhận "
            "Halal rằng mọi sản phẩm tuyệt đối tuân thủ luật Sharia — không Haram, không "
            "Najis, được chế biến trong cơ sở phân tách đúng MPPHM 2020."
        ),
        "halal_committee": [
            {"role": "Chủ tịch IHC", "name": UNSET_TEXT, "department": "Đảm bảo chất lượng"},
            {"role": "Thư ký IHC", "name": UNSET_TEXT, "department": "Halal Compliance"},
            {"role": "Sharia Advisor", "name": UNSET_TEXT, "department": "Cố vấn độc lập"},
        ],
        "chapters": [
            {"chapter_no": 1, "title": "Phạm vi và mục đích Hệ thống Đảm bảo Halal",
             "content": "HAS bao quát toàn bộ chu trình từ thu mua nguyên liệu đến giao hàng — đảm bảo mọi sản phẩm đạt tiêu chuẩn Halal MS 1500:2019.",
             "cross_refs": ["POL-HAL-001", "MS 1500:2019 §4"]},
            {"chapter_no": 2, "title": "Cấu trúc tổ chức và phân quyền",
             "content": "Halal Lead báo cáo trực tiếp Tổng giám đốc, không trực thuộc phòng ban vận hành — đảm bảo độc lập trong quyết định.",
             "cross_refs": ["POL-HAL-001 §6"]},
            {"chapter_no": 3, "title": "Quy trình kiểm soát Halal — kiến trúc tổng thể",
             "content": "HAS triển khai 6 SOP cốt lõi: tiếp nhận nguyên liệu, lưu trữ phân tách, vận hành sản xuất, vệ sinh & Sertu, xử lý không phù hợp, khiếu nại & thu hồi.",
             "cross_refs": ["SOP-RAW-001", "SOP-STO-001", "SOP-PRO-001", "SOP-CLN-001", "SOP-NCR-001", "SOP-RCL-001"]},
            {"chapter_no": 4, "title": "Audit nội bộ và rà soát của lãnh đạo",
             "content": "Audit nội bộ 6 tháng/lần. Rà soát của lãnh đạo (Management Review) 12 tháng/lần với đầu vào: NCR, KPI Halal, kết quả audit.",
             "cross_refs": []},
            {"chapter_no": 5, "title": "Quản lý tài liệu (Document Control)",
             "content": "Mọi tài liệu HAS được kiểm soát tập trung. Mỗi tài liệu có mã định danh, phiên bản, ngày hiệu lực, owner, người phê duyệt.",
             "cross_refs": []},
        ],
        "governing_documents": [
            "MS 1500:2019 — Halal Food: General Requirements",
            "TCVN 12944:2020 — Thực phẩm Halal — Yêu cầu chung",
            "JAKIM Manual Prosedur Pensijilan Halal Malaysia (MPPHM 2020)",
            "HCA-VN — Quy định cấp giấy chứng nhận Halal Việt Nam",
            "ISO 22000:2018 — Food Safety Management Systems",
        ],
        "referenced_sops": [
            "SOP-RAW-001 — Tiếp nhận và kiểm tra nguyên liệu Halal",
            "SOP-STO-001 — Lưu trữ và phân tách Halal",
            "SOP-PRO-001 — Vận hành dây chuyền sản xuất Halal",
            "SOP-CLN-001 — Vệ sinh, làm sạch và Sertu",
            "SOP-NCR-001 — Xử lý không phù hợp",
            "SOP-RCL-001 — Khiếu nại và thu hồi sản phẩm",
        ],
        "signatories": [
            {"name": UNSET_TEXT, "title": "Tổng giám đốc"},
            {"name": UNSET_TEXT, "title": "Halal Lead"},
        ],
    },
}

# halal_manual aliases has_manual fallback — different doc_type, same content
PLACEHOLDER_DATA["halal_manual"] = PLACEHOLDER_DATA["has_manual"]


# ── SOP variants — all share the structural fallback, content varies by purpose ─

_SOP_COMMON_RESPONSIBILITIES = [
    {"role": "Quản đốc / Trưởng bộ phận", "duties": "Phê duyệt việc thực thi quy trình; giám sát tuân thủ; báo cáo Halal Lead khi có sự cố."},
    {"role": "Vận hành viên / Nhân viên", "duties": "Thực hiện đúng quy trình theo SOP; ghi chép thông số; báo cáo bất thường ngay cho cấp trên."},
    {"role": "QC ca", "duties": "Kiểm tra điểm tới hạn theo lịch; lấy mẫu; ký xác nhận hồ sơ; có quyền dừng quy trình nếu phát hiện vi phạm Halal."},
    {"role": "Halal Lead / IHC Officer", "duties": "Audit định kỳ tuân thủ Halal; xử lý sự cố tạp nhiễm; phê duyệt mọi thay đổi quy trình."},
    {"role": "Tổ vệ sinh", "duties": "Vệ sinh trước/sau ca theo SOP-CLN-001; bàn giao xác nhận cho QC trước khi sản xuất tiếp."},
]

_SOP_COMMON_REFERENCES = [
    "MS 1500:2019 — Halal Food: General Requirements",
    "TCVN 12944:2020 — Thực phẩm Halal — Yêu cầu chung",
    "JAKIM Manual Prosedur Pensijilan Halal Malaysia (MPPHM 2020)",
    "Quy định nội bộ về truy xuất nguồn gốc",
    "SOP-NCR-001 — Xử lý không phù hợp (cross-reference)",
    "SOP-CLN-001 — Vệ sinh và Sertu (cross-reference)",
]

_SOP_COMMON_DEFINITIONS = [
    {"term": "Halal", "definition": "Cho phép theo luật Hồi giáo (Sharia) — áp dụng cho thực phẩm, đồ uống, dược phẩm và mọi vật phẩm tiêu dùng tuân thủ Sharia."},
    {"term": "Haram", "definition": "Bị cấm tuyệt đối — gồm thịt heo, rượu, máu, xác động vật chết tự nhiên, thịt động vật ăn thịt."},
    {"term": "Najis", "definition": "Vật ô uế theo Sharia, 3 cấp: Mughallazah (nặng — vd thịt heo), Mutawassitah (trung), Mukhaffafah (nhẹ)."},
    {"term": "Sertu", "definition": "Quy trình vệ sinh tẩy uế theo Sharia — rửa 7 lần, 1 lần với nước pha đất sạch khi tiếp xúc Najis Mughallazah."},
]

_SOP_COMMON_RECORDS_BASE = [
    "Phiếu thực hiện quy trình (lưu 5 năm)",
    "Báo cáo kiểm tra điểm tới hạn (lưu 5 năm)",
    "Biên bản không phù hợp nếu có (lưu 7 năm)",
    "Báo cáo audit nội bộ (lưu 7 năm)",
]

# Per-SOP purpose & scope (specific to operation)
_SOP_PURPOSES = {
    "sop_raw_material_receiving": "Quy định trình tự kiểm tra, tiếp nhận, lấy mẫu và lưu kho nguyên liệu thô — đảm bảo mọi nguyên liệu đầu vào tuân thủ tiêu chuẩn Halal MS 1500:2019.",
    "sop_storage_segregation": "Đảm bảo nguyên liệu, bán thành phẩm và thành phẩm Halal được lưu trữ tách biệt với mọi vật phẩm non-Halal hoặc Najis, ngăn ngừa nhiễm chéo.",
    "sop_production_operation": "Quy định trình tự vận hành dây chuyền chế biến — đảm bảo sản phẩm cuối tuân thủ Halal, không lẫn Haram, không nhiễm chéo trong sản xuất.",
    "sop_cleaning_sanitation": "Đảm bảo thiết bị, dụng cụ, mặt bằng được vệ sinh đúng cách (bao gồm Sertu khi cần) khi chuyển đổi giữa Halal và non-Halal hoặc theo lịch định kỳ.",
    "sop_handling_nonconformances": "Quy định cách phát hiện, ghi nhận, cách ly, điều tra nguyên nhân gốc và xử lý sản phẩm/quy trình không phù hợp tiêu chuẩn Halal.",
    "sop_complaint_recall": "Đảm bảo tiếp nhận, xử lý khiếu nại từ khách hàng kịp thời và thực hiện thu hồi sản phẩm khi phát hiện rủi ro Halal hoặc an toàn.",
}

_SOP_SCOPES = {
    "sop_raw_material_receiving": "Áp dụng cho 100% lô nguyên liệu thô và vật tư bao bì nhập về cơ sở sản xuất.",
    "sop_storage_segregation": "Áp dụng tại tất cả khu vực kho, container vận chuyển và thiết bị lưu trữ tạm trong cơ sở sản xuất.",
    "sop_production_operation": "Áp dụng cho dây chuyền chế biến và đóng gói — từ khi xuất nguyên liệu khỏi kho đến khi nhập kho thành phẩm.",
    "sop_cleaning_sanitation": "Áp dụng cho toàn bộ thiết bị tiếp xúc thực phẩm, bề mặt thao tác, dụng cụ vệ sinh tại cơ sở sản xuất.",
    "sop_handling_nonconformances": "Áp dụng cho mọi sản phẩm hoặc quy trình không phù hợp tiêu chuẩn Halal hoặc tiêu chí chất lượng nội bộ.",
    "sop_complaint_recall": "Áp dụng cho mọi khiếu nại về Halal hoặc chất lượng sản phẩm từ khách hàng B2B, người tiêu dùng cuối, cơ quan quản lý.",
}

# Build SOP placeholder for each variant
for _sop_type in _SOP_PURPOSES.keys():
    PLACEHOLDER_DATA[_sop_type] = {
        "sop_id": f"SOP-{_sop_type.split('_', 1)[1].upper().replace('_', '-')}-001"[:40],
        "version": "1.0",
        "purpose": _SOP_PURPOSES[_sop_type],
        "scope": _SOP_SCOPES[_sop_type],
        "responsibilities": list(_SOP_COMMON_RESPONSIBILITIES),
        "references": list(_SOP_COMMON_REFERENCES),
        "definitions": list(_SOP_COMMON_DEFINITIONS),
        "records": list(_SOP_COMMON_RECORDS_BASE),
        "approved_by": UNSET_TEXT,
    }


def get_for(doc_type: str) -> dict:
    """Return placeholder dict for the doc_type, or empty dict if none defined."""
    return PLACEHOLDER_DATA.get(doc_type, {})
