import asyncio
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class FakeDb:
    def __init__(self, row):
        self.row = row
        self.insert_args = None

    async def fetchrow(self, query, *args):
        if "FROM documents" in query:
            return self.row
        if "FROM official_artifacts" in query and "source_document_id" in query:
            return None
        if "INSERT INTO official_artifacts" in query:
            self.insert_args = args
            return {
                "id": "00000000-0000-0000-0000-0000000000aa",
                "tenant_id": args[0],
                "source_document_id": args[1],
                "artifact_kind": "approved_document",
                "original_filename": args[2],
                "storage_path": args[3],
                "file_size": args[4],
                "mime_type": args[5],
                "sha256": args[6],
                "approved_by_user_id": args[7],
                "approved_at": None,
                "effective_date": args[8],
                "next_review_date": args[9],
                "retention_expires_at": args[10],
                "created_at": None,
            }
        raise AssertionError(query)


class FakeDbWithExistingArtifact(FakeDb):
    def __init__(self, row, existing):
        super().__init__(row)
        self.existing = existing

    async def fetchrow(self, query, *args):
        if "FROM official_artifacts" in query and "source_document_id" in query:
            return self.existing
        return await super().fetchrow(query, *args)


def test_create_official_artifact_copies_outside_upload_and_hashes(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    official_root = tmp_path / "official-artifacts"
    source_dir = upload_root / "tenant-1"
    source_dir.mkdir(parents=True)
    source = source_dir / "doc.pdf"
    source.write_bytes(b"official bytes")

    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))
    monkeypatch.setenv("OFFICIAL_ARTIFACTS_DIR", str(official_root))
    import services.official_artifacts as official_artifacts

    official_artifacts = importlib.reload(official_artifacts)
    db = FakeDb(
        {
            "id": "doc-1",
            "tenant_id": "tenant-1",
            "original_filename": "Approved.pdf",
            "file_path": str(source),
            "file_size": source.stat().st_size,
            "mime_type": "application/pdf",
            "effective_date": None,
            "next_review_date": None,
            "retention_expires_at": None,
        }
    )

    artifact = asyncio.run(
        official_artifacts.create_official_artifact_for_document(
            db, document_id="doc-1", approved_by_user_id="user-1"
        )
    )

    saved = Path(artifact["storage_path"])
    assert saved.exists()
    assert saved.read_bytes() == b"official bytes"
    assert saved.resolve().is_relative_to(official_root.resolve())
    assert not saved.resolve().is_relative_to(upload_root.resolve())
    assert artifact["sha256"] == "62dbe6d8f9a2196315f659ab2e1776b2f1283428daba85f89cdd22a950c6dc5a"


def test_create_official_artifact_rejects_official_storage_inside_upload(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    source_dir = upload_root / "tenant-1"
    source_dir.mkdir(parents=True)
    source = source_dir / "doc.pdf"
    source.write_bytes(b"official bytes")

    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))
    monkeypatch.setenv("OFFICIAL_ARTIFACTS_DIR", str(upload_root / "official"))
    import services.official_artifacts as official_artifacts

    official_artifacts = importlib.reload(official_artifacts)
    db = FakeDb(
        {
            "id": "doc-1",
            "tenant_id": "tenant-1",
            "original_filename": "Approved.pdf",
            "file_path": str(source),
            "file_size": source.stat().st_size,
            "mime_type": "application/pdf",
            "effective_date": None,
            "next_review_date": None,
            "retention_expires_at": None,
        }
    )

    with pytest.raises(ValueError, match="must not be inside UPLOAD_DIR"):
        asyncio.run(
            official_artifacts.create_official_artifact_for_document(
                db, document_id="doc-1", approved_by_user_id="user-1"
            )
        )


def test_create_official_artifact_returns_existing_without_second_copy(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    official_root = tmp_path / "official-artifacts"
    source_dir = upload_root / "tenant-1"
    source_dir.mkdir(parents=True)
    source = source_dir / "doc.pdf"
    source.write_bytes(b"official bytes")
    existing_path = official_root / "tenant-1" / "existing.pdf"
    existing_path.parent.mkdir(parents=True)
    existing_path.write_bytes(b"first immutable copy")

    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))
    monkeypatch.setenv("OFFICIAL_ARTIFACTS_DIR", str(official_root))
    import services.official_artifacts as official_artifacts

    official_artifacts = importlib.reload(official_artifacts)
    existing = {
        "id": "00000000-0000-0000-0000-0000000000aa",
        "tenant_id": "tenant-1",
        "source_document_id": "doc-1",
        "artifact_kind": "approved_document",
        "original_filename": "Approved.pdf",
        "storage_path": str(existing_path),
        "file_size": existing_path.stat().st_size,
        "mime_type": "application/pdf",
        "sha256": "b" * 64,
        "approved_by_user_id": "user-1",
        "approved_at": None,
        "effective_date": None,
        "next_review_date": None,
        "retention_expires_at": None,
        "created_at": None,
    }
    db = FakeDbWithExistingArtifact(
        {
            "id": "doc-1",
            "tenant_id": "tenant-1",
            "original_filename": "Approved.pdf",
            "file_path": str(source),
            "file_size": source.stat().st_size,
            "mime_type": "application/pdf",
            "effective_date": None,
            "next_review_date": None,
            "retention_expires_at": None,
        },
        existing,
    )

    artifact = asyncio.run(
        official_artifacts.create_official_artifact_for_document(
            db, document_id="doc-1", approved_by_user_id="user-1"
        )
    )

    assert artifact["storage_path"] == str(existing_path)
    assert db.insert_args is None
    assert list((official_root / "tenant-1").iterdir()) == [existing_path]


class FakeMetricChild:
    def __init__(self):
        self.count = 0

    def inc(self):
        self.count += 1


class FakeMetric:
    def __init__(self):
        self.calls = []
        self.child = FakeMetricChild()

    def labels(self, **labels):
        self.calls.append(labels)
        return self.child


def test_create_official_artifact_failure_logs_and_counts_metric(monkeypatch, tmp_path, caplog):
    upload_root = tmp_path / "uploads"
    official_root = tmp_path / "official-artifacts"
    upload_root.mkdir(parents=True)
    missing_source = upload_root / "tenant-1" / "missing.pdf"

    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))
    monkeypatch.setenv("OFFICIAL_ARTIFACTS_DIR", str(official_root))
    import services.official_artifacts as official_artifacts

    official_artifacts = importlib.reload(official_artifacts)
    metric = FakeMetric()
    monkeypatch.setattr(official_artifacts, "OFFICIAL_ARTIFACT_CREATION_TOTAL", metric)
    db = FakeDb(
        {
            "id": "doc-1",
            "tenant_id": "tenant-1",
            "original_filename": "Approved.pdf",
            "file_path": str(missing_source),
            "file_size": 123,
            "mime_type": "application/pdf",
            "effective_date": None,
            "next_review_date": None,
            "retention_expires_at": None,
        }
    )

    with caplog.at_level("ERROR", logger="aminra.official_artifacts"):
        with pytest.raises(ValueError, match="source document file is missing"):
            asyncio.run(
                official_artifacts.create_official_artifact_for_document(
                    db, document_id="doc-1", approved_by_user_id="user-1"
                )
            )

    assert metric.calls == [{"result": "failure", "reason": "ValueError"}]
    assert metric.child.count == 1
    assert any("official artifact creation failed" in record.message for record in caplog.records)
