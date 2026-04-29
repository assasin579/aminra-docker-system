"""Template: Company Profile."""

from docx import Document as DocxDocument
from . import _base as B


def build(doc: DocxDocument, content: str, title: str, filename: str, cfg: dict = {}):
    conf_label = cfg.get("confidential_label", "HỒ SƠ DOANH NGHIỆP")
    B.setup_page(doc, title, confidential_label=conf_label)
    raw_meta = cfg.get("cover_meta")
    extra_meta = (
        [(m["key"], m["value"]) for m in raw_meta if m.get("key")]
        if raw_meta
        else [
            ("Mục đích", "Đăng ký chứng nhận Halal"),
            ("Cơ quan tiếp nhận", "[JAKIM / HDC / Tổ chức chứng nhận]"),
        ]
    )
    B.add_cover(
        doc,
        doc_type_label="Company Profile",
        title=title,
        extra_meta=extra_meta,
        show_approval=cfg.get("show_approval_block", True),
    )
    for sec in cfg.get("custom_sections", []):
        if sec.get("title"):
            B.add_heading(doc, sec["title"], level=1)
        if sec.get("content"):
            for line in sec["content"].split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    B.add_bullet(doc, line[2:])
                elif line:
                    B.add_body(doc, line)
    B.parse_content(doc, content)
    B.add_ending(doc)
