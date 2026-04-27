"""Unit tests for backend/services/certificate_pdf.py.

Strategy: extract text + images from generated PDF using pymupdf, then assert
the cert fields appear correctly. This catches both "PDF is corrupt" and
"text rendered wrong" without resorting to byte-level comparisons.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO

import fitz  # pymupdf
import pytest

from services.certificate_pdf import (
    CertificateData,
    compute_cert_hash,
    generate_pdf,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_cert() -> CertificateData:
    return CertificateData(
        cert_number="HALAL-2026-0042",
        business_name="Công ty TNHH Thực phẩm An Phú",
        provider_name="Halal Certification Center Vietnam",
        issue_date=date(2026, 4, 25),
        expiry_date=date(2027, 4, 25),
        notes="Cấp cho 5 sản phẩm thịt bò khô",
        verify_url="https://aminra.vn/verify/HALAL-2026-0042",
    )


def _extract_text(pdf_bytes: bytes) -> str:
    """Read all text from a PDF using pymupdf."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _extract_images(pdf_bytes: bytes) -> list[bytes]:
    """Return raw bytes of every embedded image."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[bytes] = []
    try:
        for page in doc:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                images.append(doc.extract_image(xref)["image"])
    finally:
        doc.close()
    return images


# ── PDF generation ──────────────────────────────────────────────────────────

class TestGeneratePdf:
    def test_returns_non_empty_pdf_bytes(self, sample_cert: CertificateData):
        pdf = generate_pdf(sample_cert)
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000  # real PDFs are at least a few KB
        assert pdf.startswith(b"%PDF-")  # valid PDF header

    def test_contains_cert_number_in_text(self, sample_cert: CertificateData):
        text = _extract_text(generate_pdf(sample_cert))
        assert "HALAL-2026-0042" in text

    def test_contains_business_and_provider_names(self, sample_cert: CertificateData):
        text = _extract_text(generate_pdf(sample_cert))
        assert "An Phú" in text
        assert "Halal Certification Center Vietnam" in text

    def test_contains_issue_and_expiry_dates(self, sample_cert: CertificateData):
        text = _extract_text(generate_pdf(sample_cert))
        assert "25/04/2026" in text
        assert "25/04/2027" in text

    def test_contains_notes_when_provided(self, sample_cert: CertificateData):
        text = _extract_text(generate_pdf(sample_cert))
        assert "thịt bò khô" in text

    def test_omits_notes_row_when_empty(self):
        cert = CertificateData(
            cert_number="HALAL-2026-0001",
            business_name="X Co",
            provider_name="Y CB",
            issue_date=date(2026, 1, 1),
            expiry_date=date(2027, 1, 1),
            notes="",
            verify_url="https://aminra.vn/verify/HALAL-2026-0001",
        )
        text = _extract_text(generate_pdf(cert))
        assert "Ghi chú" not in text

    def test_renders_vietnamese_diacritics_correctly(self, sample_cert: CertificateData):
        # "Yêu cầu" — characters with diacritics must render via embedded TTF font
        text = _extract_text(generate_pdf(sample_cert))
        assert "CHỨNG NHẬN HALAL" in text

    def test_embeds_qr_code_image(self, sample_cert: CertificateData):
        images = _extract_images(generate_pdf(sample_cert))
        assert len(images) >= 1, "expected at least one embedded image (QR code)"

    def test_qr_code_encodes_verify_url(self, sample_cert: CertificateData):
        # No QR decoder available in container. Instead: regenerate the QR PNG
        # from verify_url using the same lib settings, then compare the pixel
        # matrix (1-bit, downsampled to module grid) against each embedded
        # image. ReportLab may re-encode PNGs, so byte-level compare is fragile,
        # but pixel content is identical.
        from PIL import Image
        from services.certificate_pdf import _build_qr_png

        def to_grid(png_bytes: bytes) -> tuple:
            img = Image.open(BytesIO(png_bytes)).convert("1")
            # Normalize size — embedded QR may be scaled differently
            img = img.resize((25, 25), Image.NEAREST)
            return tuple(img.getdata())

        expected_grid = to_grid(_build_qr_png(sample_cert.verify_url))
        embedded = _extract_images(generate_pdf(sample_cert))
        assert any(to_grid(img) == expected_grid for img in embedded), (
            "no embedded image matches the QR pattern of verify_url — "
            "PDF either omits the QR or uses non-deterministic settings"
        )

    def test_cert_hash_appears_in_pdf_for_tamper_detection(self, sample_cert: CertificateData):
        text = _extract_text(generate_pdf(sample_cert))
        h = compute_cert_hash(sample_cert)
        # Hash is shown in the footer (first 16 chars enough — full hash is too long)
        assert h[:16] in text


# ── Tamper-detection hash ───────────────────────────────────────────────────

class TestComputeCertHash:
    def test_returns_64_char_hex_string(self, sample_cert: CertificateData):
        h = compute_cert_hash(sample_cert)
        assert len(h) == 64
        int(h, 16)  # raises ValueError if not hex

    def test_same_input_produces_same_hash(self, sample_cert: CertificateData):
        a = compute_cert_hash(sample_cert)
        b = compute_cert_hash(sample_cert)
        assert a == b

    def test_changing_any_field_changes_hash(self, sample_cert: CertificateData):
        baseline = compute_cert_hash(sample_cert)
        for field, new_value in [
            ("cert_number", "HALAL-2026-9999"),
            ("business_name", "Different Co"),
            ("provider_name", "Different CB"),
            ("issue_date", date(2026, 5, 1)),
            ("expiry_date", date(2028, 1, 1)),
            ("notes", "different notes"),
            ("verify_url", "https://other.example/verify/x"),
        ]:
            mutated = CertificateData(
                **{**sample_cert.__dict__, field: new_value}
            )
            assert compute_cert_hash(mutated) != baseline, f"hash unchanged when {field} changed"

    def test_hash_is_deterministic_across_field_order(self, sample_cert: CertificateData):
        # Construct via different keyword orders — hash must match
        a = compute_cert_hash(sample_cert)
        b = compute_cert_hash(CertificateData(
            verify_url=sample_cert.verify_url,
            expiry_date=sample_cert.expiry_date,
            notes=sample_cert.notes,
            issue_date=sample_cert.issue_date,
            provider_name=sample_cert.provider_name,
            business_name=sample_cert.business_name,
            cert_number=sample_cert.cert_number,
        ))
        assert a == b


# ── Validation ──────────────────────────────────────────────────────────────

class TestValidation:
    def test_raises_when_expiry_before_issue(self):
        with pytest.raises(ValueError, match="expiry_date"):
            generate_pdf(CertificateData(
                cert_number="HALAL-2026-0001",
                business_name="X",
                provider_name="Y",
                issue_date=date(2026, 1, 1),
                expiry_date=date(2025, 12, 31),
                verify_url="https://aminra.vn/verify/HALAL-2026-0001",
            ))

    def test_raises_when_cert_number_empty(self):
        with pytest.raises(ValueError, match="cert_number"):
            generate_pdf(CertificateData(
                cert_number="",
                business_name="X",
                provider_name="Y",
                issue_date=date(2026, 1, 1),
                expiry_date=date(2027, 1, 1),
                verify_url="https://aminra.vn/verify/x",
            ))

    def test_raises_when_verify_url_empty(self):
        with pytest.raises(ValueError, match="verify_url"):
            generate_pdf(CertificateData(
                cert_number="HALAL-2026-0001",
                business_name="X",
                provider_name="Y",
                issue_date=date(2026, 1, 1),
                expiry_date=date(2027, 1, 1),
                verify_url="",
            ))
