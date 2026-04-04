"""
aminra Vietnam - RAG Ingestion Pipeline
==========================================
Xu ly tai lieu HDC/JAKIM (PPTX + PDF) -> chunk -> embed -> Qdrant

Cai dat:
    pip install pymupdf python-pptx markitdown qdrant-client \
                sentence-transformers tqdm python-dotenv

Chay:
    python ingest.py --file docs/CU_01___CU_02.pptx
    python ingest.py --dir docs/
    python ingest.py --dir docs/ --reset
"""

# UTF-8 fix - phai dat truoc moi import khac
import sys, os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "en_US.UTF-8")
os.environ.setdefault("LC_ALL", "en_US.UTF-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import re
import json
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("aminra.ingest")

QDRANT_URL      = os.getenv("QDRANT_URL",      "http://localhost:6333")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "halal_kb")
EMBED_MODEL     = os.getenv("EMBED_MODEL",     "intfloat/multilingual-e5-large")
CHUNK_SIZE      = int(os.getenv("CHUNK_SIZE",  "400"))
CHUNK_OVERLAP   = int(os.getenv("CHUNK_OVERLAP","80"))
MIN_CHUNK_WORDS = int(os.getenv("MIN_CHUNK_WORDS","30"))
# Model dimension for multilingual-e5-base is 768
VECTOR_DIM      = 768

TOPIC_KEYWORDS = {
    "audit_principles":   ["ethical","integrity","confidentiality","independence",
                           "fair presentation","evidence","risk-based",
                           "đạo đức","chính trực","bảo mật","độc lập",
                           "trình bày công bằng","bằng chứng","dựa trên rủi ro"],
    "audit_planning":     ["planning","audit program","checklist","schedule",
                           "lập kế hoạch","chương trình đánh giá","danh sách kiểm tra","lịch trình"],
    "audit_types":        ["internal","external","first party","second party",
                           "third party","surveillance","compliance","site audit",
                           "nội bộ","bên ngoài","bên thứ nhất","bên thứ hai",
                           "bên thứ ba","giám sát","tuân thủ","đánh giá tại chỗ",
                           "kiểm định","đánh giá"],
    "audit_team":         ["lead auditor","auditor","auditee",
                           "trưởng đoàn đánh giá","đánh giá viên","được đánh giá"],
    "halal_standard":     ["jakim","ms1500","mhms","mhcmp","halal assurance",
                           "tiêu chuẩn halal","đảm bảo halal"],
    "non_conformance":    ["non-conformance","ncr","corrective action","car",
                           "không phù hợp","hành động khắc phục"],
    "documentation":      ["document","record","evidence","report","agenda",
                           "tài liệu","hồ sơ","bằng chứng","báo cáo","chương trình làm việc"],
    "fiqh_halal":         ["halal","haram","najs","zabihah","slaughter","fiqh",
                           "hợp thức","cấm","ô uế","giết mổ","luật học"],
    "certification_body": ["jakim","mui","muis","esma","sfda","hdc",
                           "cơ quan chứng nhận"],
    "logistics":          ["logistics","cold chain","labelling","packaging","traceability",
                           "hậu cần","chuỗi lạnh","dán nhãn","bao bì","truy xuất nguồn gốc"],
}


@dataclass
class Chunk:
    id:          str
    text:        str
    source_file: str
    source_type: str
    slide_num:   Optional[int]
    slide_title: Optional[str]
    chunk_idx:   int
    topics:      list
    language:    str
    word_count:  int
    created_at:  str


def extract_pptx(path: Path) -> list:
    from pptx import Presentation
    prs = Presentation(str(path))
    slides_data = []
    for i, slide in enumerate(prs.slides, 1):
        texts, title = [], None
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            frame_text = shape.text_frame.text.strip()
            if not frame_text:
                continue
            # FIX: boc try/except vi khong phai shape nao cung la placeholder
            try:
                if hasattr(shape, "placeholder_format") and shape.placeholder_format is not None:
                    ph_idx = shape.placeholder_format.idx
                    if ph_idx in (0, 1) and title is None:
                        title = frame_text
                        continue
            except (ValueError, AttributeError):
                pass
            texts.append(frame_text)
        full_text = "\n".join(texts).strip()
        if full_text:
            slides_data.append({"slide_num": i, "title": title or f"Slide {i}", "text": full_text})
    log.info(f"  PPTX: {len(slides_data)} slides co noi dung tu {path.name}")
    return slides_data


def extract_pdf(path: Path) -> list:
    import fitz
    doc = fitz.open(str(path))
    pages_data = []
    for i, page in enumerate(doc, 1):
        text = page.get_text("text").strip()
        if not text or len(text.split()) < 5:
            continue
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        title = lines[0][:80] if lines else f"Page {i}"
        pages_data.append({"slide_num": i, "title": title, "text": text})
    log.info(f"  PDF: {len(pages_data)} trang co noi dung tu {path.name}")
    return pages_data


def extract_txt(path: Path) -> list:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    sections = re.split(r"\n#{1,3} |\n\n\n+", raw)
    result = []
    for i, sec in enumerate(sections, 1):
        sec = sec.strip()
        if len(sec.split()) < 10:
            continue
        lines = sec.splitlines()
        title = lines[0][:80] if lines else f"Section {i}"
        result.append({"slide_num": i, "title": title, "text": sec})
    return result


def extract(path: Path):
    ext = path.suffix.lower()
    if ext in (".pptx", ".ppt"):
        return "pptx", extract_pptx(path)
    elif ext == ".pdf":
        return "pdf", extract_pdf(path)
    elif ext in (".txt", ".md"):
        return "txt", extract_txt(path)
    else:
        raise ValueError(f"Khong ho tro dinh dang: {ext}")


def sliding_window_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    words = text.split()
    if len(words) <= chunk_size:
        return [text] if len(words) >= MIN_CHUNK_WORDS else []
    chunks, i = [], 0
    while i < len(words):
        end = min(i + chunk_size, len(words))
        chunk_text = " ".join(words[i:end])
        if len(chunk_text.split()) >= MIN_CHUNK_WORDS:
            chunks.append(chunk_text.strip())
        i += chunk_size - overlap
    return chunks


def detect_topics(text):
    t = text.lower()
    matched = [k for k, kws in TOPIC_KEYWORDS.items() if any(kw in t for kw in kws)]
    return matched or ["general"]


_VI_CHARS = re.compile(r"[àáảãạăắặẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]", re.I)

def detect_language(text):
    ratio = len(_VI_CHARS.findall(text)) / max(len(text), 1)
    if ratio > 0.03:
        return "vi"
    elif ratio > 0.01:
        return "mixed"
    return "en"


def build_chunks(source_file, source_type, slides):
    all_chunks = []
    for slide in slides:
        raw_text   = slide["text"]
        slide_num  = slide["slide_num"]
        slide_title = slide.get("title", "")
        context_text = f"{slide_title}\n{raw_text}" if slide_title else raw_text
        sub_chunks = sliding_window_chunks(context_text)
        for idx, chunk_text in enumerate(sub_chunks):
            raw_id = f"{source_file}::slide{slide_num}::chunk{idx}"
            chunk_id = hashlib.sha256(raw_id.encode()).hexdigest()[:32]
            chunk = Chunk(
                id          = chunk_id,
                text        = chunk_text,
                source_file = source_file,
                source_type = source_type,
                slide_num   = slide_num,
                slide_title = slide_title,
                chunk_idx   = idx,
                topics      = detect_topics(chunk_text),
                language    = detect_language(chunk_text),
                word_count  = len(chunk_text.split()),
                created_at  = datetime.utcnow().isoformat(),
            )
            all_chunks.append(chunk)
    log.info(f"  -> {len(all_chunks)} chunks tu {source_file}")
    return all_chunks


_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer
        log.info(f"Dang tai embedding model: {EMBED_MODEL} ...")
        _encoder = SentenceTransformer(EMBED_MODEL)
        log.info("  Model da tai xong.")
    return _encoder


def embed_chunks(chunks, batch_size=32):
    encoder = get_encoder()
    texts = [f"passage: {c.text}" for c in chunks]
    vectors = []
    
    import numpy as np
    from tqdm import tqdm
    
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding", unit="batch"):
        batch = texts[i: i + batch_size]
        vecs = encoder.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        vectors.extend(vecs.tolist())
    
    # Save encoder info (not the whole model - too large)
    import pickle
    import os
    encoder_path = "./encoder_info.pkl"
    with open(encoder_path, "wb") as f:
        pickle.dump({"model_name": EMBED_MODEL, "dimension": len(vectors[0])}, f)
    log.info(f"  Da luu encoder info vao {encoder_path}")
    
    return vectors


def get_qdrant_client():
    from qdrant_client import QdrantClient
    # Khong truyen api_key de tranh UnicodeEncodeError trong httpx
    return QdrantClient(url=QDRANT_URL)


def ensure_collection(client, reset=False):
    from qdrant_client.models import Distance, VectorParams
    existing = [c.name for c in client.get_collections().collections]
    if reset and COLLECTION_NAME in existing:
        client.delete_collection(COLLECTION_NAME)
        log.info(f"  Da xoa collection cu: {COLLECTION_NAME}")
        existing = []
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
        )
        log.info(f"  Da tao collection: {COLLECTION_NAME} (dim={VECTOR_DIM})")
    else:
        count = client.count(COLLECTION_NAME).count
        log.info(f"  Collection '{COLLECTION_NAME}' da ton tai ({count} vectors).")


def upsert_chunks(client, chunks, vectors):
    from qdrant_client.models import PointStruct
    BATCH = 128
    total = 0
    for i in tqdm(range(0, len(chunks), BATCH), desc="Upsert Qdrant", unit="batch"):
        batch_chunks  = chunks[i: i + BATCH]
        batch_vectors = vectors[i: i + BATCH]
        points = [
            PointStruct(
                id      = abs(int(c.id[:8], 16)),
                vector  = v,
                payload = asdict(c),
            )
            for c, v in zip(batch_chunks, batch_vectors)
        ]
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        total += len(points)
    log.info(f"  Upserted {total} points vao '{COLLECTION_NAME}'.")
    return total


def ingest_file(path: Path, client, reset_done=False):
    log.info(f"\n{'='*60}")
    log.info(f"Dang xu ly: {path.name}")
    source_type, slides = extract(path)
    if not slides:
        log.warning(f"  Khong tim thay noi dung trong {path.name}")
        return 0
    chunks = build_chunks(source_file=path.name, source_type=source_type, slides=slides)
    if not chunks:
        log.warning(f"  Khong tao duoc chunk tu {path.name}")
        return 0
    vectors = embed_chunks(chunks)
    return upsert_chunks(client, chunks, vectors)


def ingest_dir(dir_path: Path, client, reset=False):
    supported = {".pptx", ".ppt", ".pdf", ".txt", ".md"}
    files = [f for f in sorted(dir_path.iterdir()) if f.suffix.lower() in supported]
    if not files:
        log.warning(f"Khong co file duoc ho tro trong {dir_path}")
        return {}
    ensure_collection(client, reset=reset)
    summary = {}
    for i, f in enumerate(files):
        count = ingest_file(f, client, reset_done=(i > 0 or not reset))
        summary[f.name] = count
    total = sum(summary.values())
    log.info(f"\n{'='*60}")
    log.info(f"HOAN THANH: {len(files)} files -> {total} chunks da ingest")
    for fname, cnt in summary.items():
        log.info(f"  {fname}: {cnt} chunks")
    return summary


def main():
    parser = argparse.ArgumentParser(description="aminra RAG Ingestion Pipeline")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Ingest 1 file (PPTX/PDF/TXT)")
    group.add_argument("--dir",  type=Path, help="Ingest tat ca files trong thu muc")
    parser.add_argument("--reset", action="store_true", help="Xoa collection cu va ingest lai")
    args = parser.parse_args()
    client = get_qdrant_client()
    if args.file:
        ensure_collection(client, reset=args.reset)
        count = ingest_file(args.file, client)
        log.info(f"\nKet qua: {count} chunks tu {args.file.name}")
    else:
        ingest_dir(args.dir, client, reset=args.reset)


if __name__ == "__main__":
    main()