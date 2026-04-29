"""
Signature & Stamp Detection for PDF/DOCX documents.

Detects:
1. Digital signatures (PDF signature fields/widgets)
2. Physical signatures/stamps (images in signature zones)
3. Signature-related text patterns ("Ký tên", "Đóng dấu", etc.)
"""

import logging
from pathlib import Path
from typing import Dict

log = logging.getLogger("aminra.signature")

# Text patterns that indicate signature/stamp areas
SIGNATURE_PATTERNS = [
    # Vietnamese
    "ký tên",
    "chữ ký",
    "đóng dấu",
    "con dấu",
    "người ký",
    "người phê duyệt",
    "phê duyệt",
    "người soạn thảo",
    "người xem xét",
    "đại diện",
    "giám đốc",
    "tổng giám đốc",
    "trưởng ban",
    "ký và đóng dấu",
    "ký, đóng dấu",
    # English
    "signature",
    "signed by",
    "approved by",
    "authorized by",
    "seal",
    "stamp",
    "sign here",
    "date and sign",
    # Malay
    "tandatangan",
    "cop",
    "meterai",
]


def detect_signatures(file_path: Path) -> Dict:
    """
    Detect signatures in a document.
    Returns dict with detection results.
    """
    suffix = file_path.suffix.lower()

    result = {
        "has_digital_signature": False,  # confirmed: crypto sig field in PDF
        "has_signature_image": False,  # likely: image in signature zone
        "has_signature_text": False,  # placeholder only: text like "Signed by"
        "signature_status": "none",  # none | placeholder | likely | confirmed
        "signature_zones": [],
        "digital_signatures": [],
        "summary": "",
    }

    if suffix == ".pdf":
        _detect_pdf(file_path, result)
    elif suffix in (".docx", ".doc"):
        _detect_docx(file_path, result)
    elif suffix in (".pptx", ".ppt"):
        _detect_pptx(file_path, result)
    else:
        result["summary"] = "Định dạng file không hỗ trợ quét chữ ký"
        return result

    # Determine signature_status (hierarchical)
    if result["has_digital_signature"]:
        result["signature_status"] = "confirmed"
        count = len(result["digital_signatures"])
        result["summary"] = f"Đã ký số — {count} chữ ký số được xác nhận"
    elif result["has_signature_image"]:
        result["signature_status"] = "likely"
        img_count = sum(1 for z in result["signature_zones"] if z["type"] == "image")
        result["summary"] = f"Có thể đã ký — phát hiện {img_count} hình ảnh chữ ký/con dấu (cần xác nhận thủ công)"
    elif result["has_signature_text"]:
        result["signature_status"] = "placeholder"
        result["summary"] = (
            'Chưa có chữ ký thật — chỉ có text placeholder ("Ký tên", "Signed by"...), chưa phát hiện chữ ký số hoặc hình ảnh con dấu'
        )
    else:
        result["signature_status"] = "none"
        result["summary"] = "Không phát hiện chữ ký hoặc con dấu"

    return result


def _detect_pdf(file_path: Path, result: Dict):
    """Detect signatures in PDF using pymupdf."""
    try:
        import fitz
    except ImportError:
        log.warning("pymupdf not installed, skipping PDF signature detection")
        return

    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        log.warning(f"Cannot open PDF for signature detection: {e}")
        return

    total_pages = len(doc)

    for page_num, page in enumerate(doc):
        page_height = page.rect.height

        # 1. Check digital signature widgets
        try:
            for widget in page.widgets():
                if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                    result["has_digital_signature"] = True
                    sig_info = {
                        "page": page_num + 1,
                        "field_name": widget.field_name or "unknown",
                    }
                    # Try to get signer info
                    try:
                        if widget.field_value:
                            sig_info["value"] = str(widget.field_value)[:200]
                    except:
                        pass
                    result["digital_signatures"].append(sig_info)
        except Exception:
            pass

        # 2. Check for images in signature zone (bottom 30% of page)
        try:
            image_list = page.get_images(full=True)
            for img in image_list:
                try:
                    img_rects = page.get_image_rects(img[0])
                    for rect in img_rects:
                        # Image in bottom 30% of page — likely signature/stamp
                        if rect.y0 > page_height * 0.7:
                            result["has_signature_image"] = True
                            result["signature_zones"].append(
                                {
                                    "type": "image",
                                    "page": page_num + 1,
                                    "position": "bottom",
                                    "description": f"Hình ảnh tại trang {page_num + 1} (vùng chữ ký)",
                                }
                            )
                        # Small-medium image anywhere — could be stamp/seal
                        elif 30 < rect.width < 300 and 30 < rect.height < 300:
                            ratio = rect.width / max(rect.height, 1)
                            # Roughly square → likely stamp
                            if 0.5 < ratio < 2.0:
                                result["has_signature_image"] = True
                                result["signature_zones"].append(
                                    {
                                        "type": "image",
                                        "page": page_num + 1,
                                        "position": "middle",
                                        "description": f"Hình ảnh con dấu/chữ ký tại trang {page_num + 1}",
                                    }
                                )
                except Exception:
                    continue
        except Exception:
            pass

        # 3. Check for signature text patterns
        try:
            text = page.get_text().lower()
            for pattern in SIGNATURE_PATTERNS:
                if pattern in text:
                    result["has_signature_text"] = True
                    result["signature_zones"].append(
                        {
                            "type": "text_pattern",
                            "page": page_num + 1,
                            "pattern": pattern,
                            "description": f'Tìm thấy "{pattern}" tại trang {page_num + 1}',
                        }
                    )
                    break  # one pattern per page is enough
        except Exception:
            pass

    doc.close()

    # Deduplicate signature zones
    seen = set()
    unique = []
    for z in result["signature_zones"]:
        key = (z["type"], z["page"], z.get("position", z.get("pattern", "")))
        if key not in seen:
            seen.add(key)
            unique.append(z)
    result["signature_zones"] = unique


def _detect_docx(file_path: Path, result: Dict):
    """Detect signatures in DOCX."""
    try:
        from docx import Document
    except ImportError:
        return

    try:
        doc = Document(str(file_path))
    except Exception as e:
        log.warning(f"Cannot open DOCX for signature detection: {e}")
        return

    full_text = ""
    has_images = False

    for para in doc.paragraphs:
        full_text += para.text.lower() + "\n"
        # Check for inline images
        for run in para.runs:
            if run._element.findall(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"):
                has_images = True

    # Check text patterns
    for pattern in SIGNATURE_PATTERNS:
        if pattern in full_text:
            result["has_signature_text"] = True
            result["signature_zones"].append(
                {
                    "type": "text_pattern",
                    "page": None,
                    "pattern": pattern,
                    "description": f'Tìm thấy "{pattern}" trong tài liệu',
                }
            )

    # Check images (potential stamps/signatures)
    try:
        rels = doc.part.rels
        image_count = sum(1 for r in rels.values() if "image" in r.reltype)
        if image_count > 0:
            result["has_signature_image"] = True
            result["signature_zones"].append(
                {
                    "type": "image",
                    "page": None,
                    "position": "document",
                    "description": f"{image_count} hình ảnh trong tài liệu (có thể chứa chữ ký/con dấu)",
                }
            )
    except Exception:
        if has_images:
            result["has_signature_image"] = True
            result["signature_zones"].append(
                {
                    "type": "image",
                    "page": None,
                    "position": "document",
                    "description": "Phát hiện hình ảnh inline (có thể chứa chữ ký/con dấu)",
                }
            )


def _detect_pptx(file_path: Path, result: Dict):
    """Basic signature detection for PPTX — mostly text patterns."""
    try:
        from pptx import Presentation

        prs = Presentation(str(file_path))
        full_text = ""
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    full_text += shape.text_frame.text.lower() + "\n"
        for pattern in SIGNATURE_PATTERNS:
            if pattern in full_text:
                result["has_signature_text"] = True
                result["signature_zones"].append(
                    {
                        "type": "text_pattern",
                        "page": None,
                        "pattern": pattern,
                        "description": f'Tìm thấy "{pattern}" trong bài thuyết trình',
                    }
                )
    except Exception:
        pass
