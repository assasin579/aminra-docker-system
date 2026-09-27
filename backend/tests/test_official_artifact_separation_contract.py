from pathlib import Path

import pytest


def test_official_artifacts_migration_contract():
    migration = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "051_official_artifacts.py"
    text = migration.read_text()

    assert "CREATE TABLE IF NOT EXISTS official_artifacts" in text
    assert "source_document_id UUID NOT NULL REFERENCES documents(id)" in text
    assert "storage_path TEXT NOT NULL" in text
    assert "sha256 TEXT NOT NULL" in text
    assert "artifact_kind TEXT NOT NULL" in text
    assert "CREATE UNIQUE INDEX IF NOT EXISTS idx_official_artifacts_source_kind" in text
    assert "CREATE TRIGGER documents_block_delete_with_official_artifacts" in text
    assert "block_document_delete_with_official_artifacts" in text
    assert "official immutable artifact" in text.lower()


def test_official_artifact_service_contract():
    service = Path(__file__).resolve().parents[1] / "services" / "official_artifacts.py"
    text = service.read_text()

    assert "OFFICIAL_ARTIFACTS_DIR" in text
    assert "UPLOAD_DIR" in text
    assert "is_relative_to(upload_root" in text
    assert "raise ValueError" in text
    assert "hashlib.sha256" in text
    assert "INSERT INTO official_artifacts" in text
    assert "ON CONFLICT" in text
    assert "source_document_id" in text


def test_documents_router_official_artifact_contract():
    router = Path(__file__).resolve().parents[1] / "auth" / "document_router.py"
    text = router.read_text()

    assert "create_official_artifact_for_document" in text
    assert "@router.get(\"/official-artifacts\"" in text
    assert "@router.get(\"/official-artifacts/{artifact_id}/file\"" in text
    assert "FROM official_artifacts" in text
    assert "Không thể xoá tài liệu đã có bản chính thức" in text
    delete_guard_pos = text.index("Không thể xoá tài liệu đã có bản chính thức")
    unlink_pos = text.index("resolved_file.unlink")
    assert delete_guard_pos < unlink_pos


def test_documents_ui_official_artifacts_read_only_contract():
    page = Path(__file__).resolve().parents[2] / "frontend" / "aminra-web" / "app" / "documents" / "page.tsx"
    if not page.exists():
        pytest.skip("frontend source is not included in this backend-only runtime image")
    text = page.read_text()

    assert "OfficialArtifactItem" in text
    assert "/api/api/official-artifacts" in text
    assert "Bản chính thức" in text
    assert "read-only" in text.lower()
    official_section = text[
        text.index("official-artifacts-read-only-start") : text.index("official-artifacts-read-only-end")
    ]
    assert "handleDelete" not in official_section
    assert "setEvalLangModal" not in official_section
    assert "ApprovalActions" not in official_section
