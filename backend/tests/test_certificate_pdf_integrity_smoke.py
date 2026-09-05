"""P0 certificate/PDF integrity smoke tests.

Focus:
- Public certificate verification returns only importer-safe fields.
- Protected certificate PDF download rejects anonymous access.
- Protected document generation/export endpoints reject anonymous access.
"""

SENSITIVE_PUBLIC_CERT_FIELDS = {
    "id",
    "pdf_path",
    "business_tenant",
    "issued_by",
    "revoked_by",
    "notes",
    "created_at",
    "updated_at",
    "email",
    "phone",
    "address",
}


def test_public_certificate_verify_field_minimization(client):
    resp = client.get("/api/submissions/certificates/public/HALAL-2026-DEMO")
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()

    assert data["cert_number"] == "HALAL-2026-DEMO"
    assert data["valid"] is True
    assert data["status"] == "active"

    leaked = SENSITIVE_PUBLIC_CERT_FIELDS.intersection(data.keys())
    assert not leaked, f"public cert response leaked fields: {sorted(leaked)}"

    assert set(data.keys()).issubset(
        {
            "cert_number",
            "company_name",
            "provider_name",
            "issue_date",
            "expiry_date",
            "status",
            "valid",
            "revocation",
            "blockchain",
        }
    )


def test_public_certificate_verify_unknown_cert_404(client):
    resp = client.get("/api/submissions/certificates/public/HALAL-DOES-NOT-EXIST")
    assert resp.status_code == 404


def test_certificate_pdf_download_rejects_anonymous_before_file_access(client):
    resp = client.get("/api/submissions/certificates/00000000-0000-0000-0000-000000000000/pdf")
    assert resp.status_code in (401, 403), resp.text[:300]


def test_generate_document_rejects_anonymous(client):
    resp = client.post(
        "/generate-document",
        json={
            "doc_type": "halal_policy",
            "doc_type_label": "Halal Policy",
            "extracted_text": "",
            "issues": [],
            "recommendations": [],
        },
    )
    assert resp.status_code in (401, 403), resp.text[:300]


def test_generate_document_export_docx_rejects_anonymous(client):
    resp = client.post(
        "/generate-document/export-docx",
        json={"content": "test", "filename": "test.docx", "title": "Test", "doc_type": "halal_policy"},
    )
    assert resp.status_code in (401, 403), resp.text[:300]
