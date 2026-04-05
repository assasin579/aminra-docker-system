# Aminra — Halal Certification AI

> **Nền tảng AI tư vấn chứng nhận Halal** dựa trên tài liệu chính thức HDC Berhad Malaysia

---

## Kiến trúc

```
Tài liệu HDC/JAKIM (PPTX/PDF)
        │
        ▼
  pipeline/ingest.py          ← Extract → Chunk → Embed → Qdrant
        │
        ▼
  Qdrant Vector DB             ← Lưu trữ 768-dim vectors
        │
        ▼
  pipeline/query.py            ← Embed query → Search → Build context
        │
        ▼
  DeepSeek API (LLM)           ← Generate answer (deepseek-chat)
        │
        ▼
  app.py (FastAPI)             ← REST API cho web/mobile frontend
```

---

## Cài đặt nhanh

### 1. Clone và cấu hình

```bash
git clone <repo>
cd aminra
cp .env.example .env
# Chỉnh sửa .env với thông tin server của bạn
```

### 2. Chạy infrastructure (Docker)

```bash
# Khởi động Qdrant
docker compose up qdrant -d
```

### 3. Cài dependencies Python

```bash
pip install -r requirements.txt
```

### 4. Ingest tài liệu HDC

```bash
# Đặt file PPTX/PDF vào thư mục docs/
mkdir -p docs
cp /path/to/CU_01___CU_02.pptx docs/
cp /path/to/other_hdc_materials.pdf docs/

# Ingest toàn bộ (lần đầu dùng --reset)
python pipeline/ingest.py --dir docs/ --reset

# Kết quả mong đợi:
# [INFO] PPTX: 73 slides có nội dung từ CU_01___CU_02.pptx
# [INFO] → 44 chunks
# [INFO] Embedding... 100%|████████| 1/1 [00:08<00:00]
# [INFO] Upserted 44 points vào 'halal_kb'
```

### 5. Test query

```bash
python pipeline/query.py "Audit checklist là gì và tại sao cần thiết?"
```

### 6. Chạy API server

```bash
python app.py
# → http://localhost:8000
# → Docs: http://localhost:8000/docs
```

---

## API Usage

### Chat endpoint

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Kiểm định bên thứ ba là gì?",
    "top_k": 5,
    "topic_filter": "audit_types"
  }'
```

Response:
```json
{
  "question": "Kiểm định bên thứ ba là gì?",
  "answer": "Kiểm định bên thứ ba (Third Party Audit) là...\n\n[Nguồn: CU_01___CU_02.pptx, Slide 11 \"THIRD PARTY AUDIT\"]",
  "sources": ["CU_01___CU_02.pptx · Slide 11 · \"THIRD PARTY AUDIT\""],
  "scores": [0.891],
  "chunks_used": 3
}
```

### Upload tài liệu mới

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@/path/to/new_jakim_standard.pdf"
```

### Streaming (cho chat UI)

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Quy trình xin chứng nhận JAKIM gồm mấy bước?"}' \
  --no-buffer
```

---

## Topic Filters

| Filter | Mô tả |
|--------|-------|
| `audit_principles` | 6 nguyên tắc kiểm định HDC |
| `audit_planning` | Lập kế hoạch, checklist, audit program |
| `audit_types` | Nội bộ, bên ngoài, 1st/2nd/3rd party |
| `audit_team` | Lead Auditor, Auditor, Auditee |
| `halal_standard` | JAKIM, MS1500, MHMS, MHCMP |
| `non_conformance` | NCR, Corrective Action |
| `documentation` | Tài liệu, hồ sơ, bằng chứng |
| `fiqh_halal` | Halal/Haram, giết mổ, nguyên liệu |
| `certification_body` | JAKIM, MUI, ESMA, HDC |
| `logistics` | Chuỗi cung ứng, bao bì, nhãn mác |

---

## Thêm tài liệu mới

```bash
# Thêm tài liệu JAKIM, MUI, ESMA vào docs/
python pipeline/ingest.py --file docs/ms1500_2019.pdf

# Kiểm tra số vectors
curl http://localhost:8000/stats
```

---

## Cấu hình nâng cao

```env
# .env

# Điều chỉnh chunk size (tăng nếu tài liệu có đoạn dài)
CHUNK_SIZE=500
CHUNK_OVERLAP=100

# Tăng số chunk retrieve nếu cần ngữ cảnh rộng hơn
TOP_K=8

# Giảm threshold nếu muốn nhiều kết quả hơn (chấp nhận kém liên quan hơn)
SCORE_THRESHOLD=0.35

# Dùng model lớn hơn nếu có GPU mạnh
LLM_MODEL=qwen2.5:14b
```

---

## On-premise deployment (khách Enterprise)

```bash
# Đóng gói toàn bộ stack
docker compose build

# Export image
docker save aminra_api | gzip > aminra_v1.tar.gz

# Trên server khách hàng
docker load < aminra_v1.tar.gz
docker compose up -d
```

Tất cả dữ liệu nằm trong Docker volumes trên server khách — không có gì gửi ra ngoài.

---

## Roadmap tích hợp

- [ ] **Tuần 3**: Web chat UI (Next.js) kết nối `/chat/stream`
- [ ] **Tuần 4**: Checklist generator dùng RAG context
- [ ] **Tuần 5**: GAP Analysis — upload SOP → so sánh với chuẩn Halal
- [ ] **Tuần 6**: Admin dashboard + user management

---

*aminra Vietnam · Dựa trên tài liệu được cấp phép từ HDC Berhad Malaysia*
