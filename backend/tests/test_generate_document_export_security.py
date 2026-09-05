"""Security regression tests for generated document export endpoints."""


def test_export_docx_requires_authentication(client):
    """DOCX export is a branded/compliance artifact path and must not be public.

    Regression: /generate-document/export-docx used to omit get_current_user even
    though /generate-document itself requires auth + rate limiting.
    """
    resp = client.post(
        "/generate-document/export-docx",
        json={
            "content": "1. QA smoke document",
            "filename": "qa-export-auth-boundary.docx",
            "title": "QA Export Auth Boundary",
            "doc_type": "generic",
        },
    )

    assert resp.status_code in (401, 403)
