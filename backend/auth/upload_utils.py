import os
import magic  # python-magic for MIME type detection
from pathlib import Path
from fastapi import UploadFile, HTTPException

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024  # default 50MB

ALLOWED_EXTENSIONS = {".pptx", ".ppt", ".pdf", ".txt", ".md", ".docx", ".odt"}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument.text",
    "text/plain",
    "text/markdown",
}

# DOCX/PPTX/ODT are ZIP-based — magic sometimes detects them as these
_ZIP_BASED_MIMES = {"application/octet-stream", "application/zip", "application/x-zip-compressed"}
_ZIP_BASED_EXTENSIONS = {".docx", ".pptx", ".odt"}


async def validate_upload(file: UploadFile) -> bytes:
    """Validate file extension, size, and MIME type. Returns file bytes."""
    # 1. Extension check
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed: {suffix}")

    # 2. Read and check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

    # 3. MIME type check (magic bytes)
    detected_mime = magic.from_buffer(content, mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        # ZIP-based formats (DOCX, PPTX, ODT) may be detected as octet-stream/zip
        if not (detected_mime in _ZIP_BASED_MIMES and suffix in _ZIP_BASED_EXTENSIONS):
            raise HTTPException(400, f"Invalid file content type: {detected_mime}")

    await file.seek(0)  # reset for downstream readers
    return content
