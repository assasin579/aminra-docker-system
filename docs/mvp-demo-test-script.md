# AMINRA MVP Demo — 20-Flow Test Script

> Last updated: 2026-04-25
> Status: Ready for demo verification
> Owner: Engineering team

This document is the **authoritative test plan** for AMINRA MVP demos. Run all 20 flows against staging before any external demo. Use `scripts/pre_demo_check.sh` for the automated subset.

---

## Quick reference — 20 flows

| # | Persona | Flow | Tier | Auto-tested |
|---|---|---|---|---|
| 1 | Public | Public verify cert (QR + blockchain badge) | 🟢 | ✅ E2E + a11y |
| 2 | Public | Halal advisor chat (RAG no-auth) | 🟢 | ✅ E2E |
| 3 | Public | Forgot password full flow | 🟡 | ✅ E2E + unit |
| 4 | Public | Landing + Privacy/Terms render | 🟢 | ✅ E2E + a11y |
| 5 | Public | Cert PDF download from public link | 🟢 | ✅ E2E |
| 6 | Business | Registration → login → dashboard | 🟢 | ✅ E2E |
| 7 | Business | Document upload + AI evaluation | 🟡 | ⚠ Manual (LLM cost) |
| 8 | Business | Submit hồ sơ tới CB (multi-doc) | 🟡 | ✅ E2E |
| 9 | Business | Self-assessment workflow | 🟡 | ✅ E2E |
| 10 | Business | Resubmit sau revision request | 🟡 | ✅ E2E |
| 11 | Business | View submission status + history | 🟢 | ✅ E2E |
| 12 | Provider | Login → portfolio → dashboard stats | 🟢 | ✅ E2E |
| 13 | Provider | Review submission → request revision | 🔴 | ✅ E2E + integration |
| 14 | Provider | Assign auditor to submission | 🟡 | ✅ E2E |
| 15 | Provider | Approve submission → issue cert | 🔴 | ✅ E2E |
| 16 | Provider | Cert revoke với reason | 🟡 | ✅ E2E + integration |
| 17 | Auditor | Onsite audit (checklist + photo + NCR) | 🔴 | ⚠ Manual (mobile) |
| 18 | Admin | Analytics dashboard | 🟢 | ✅ E2E |
| 19 | Admin | Approve pending provider | 🟡 | ✅ E2E + integration |
| 20 | Admin | Overdue submissions escalation | 🔴 | ✅ E2E |

---

## Pre-demo setup checklist (T-60 phút)

```bash
# Health
curl -sf http://localhost:8100/health || echo "Backend DOWN"
curl -sf http://localhost:3100 || echo "Frontend DOWN"
docker compose ps   # Tất cả services healthy

# Seed demo data
python scripts/seed_demo_data.py --reset

# Run automated smoke
bash scripts/pre_demo_check.sh

# Sanity 1 flow manually
open http://localhost:3100/verify/HALAL-2026-DEMO
```

If `pre_demo_check.sh` exits 0 → safe to demo.
If exits 1 → investigate before going live.

---

## Tier 1 — Public flows (5)

### Flow 1: Public verify cert
**Goal:** Importer scans QR → sees green check + blockchain proof.

**Pre-conditions:** Cert `HALAL-2026-DEMO` active in DB.

**Steps:**
1. Navigate to `/verify/HALAL-2026-DEMO`
2. Page loads in <2s with green check + "Chứng nhận hợp lệ"
3. Details card: cert_number, doanh nghiệp, tổ chức cấp, ngày cấp, ngày hết hạn
4. Optional blockchain badge (when Polygon deployed)

**Critical:**
- [ ] No flash of "404" before loading
- [ ] Mobile responsive
- [ ] No console errors

**Smoke:**
```bash
curl -s http://localhost:8100/api/submissions/certificates/public/HALAL-2026-DEMO | jq .valid
# Expected: true
```

### Flow 2: Halal advisor chat (RAG)
**Goal:** Public visitor gets accurate halal answer with citations.

**Steps:**
1. Navigate to `/chat`
2. Ask "Gelatin từ bò có Halal không?"
3. Wait 3-15s for streaming response
4. Verify response cites sources (JAKIM MS 1500, HAS 23000)

**Critical:**
- [ ] No hallucination
- [ ] Response in correct language (Vietnamese)
- [ ] Diacritics render properly

**Smoke:**
```bash
curl -s -X POST http://localhost:8100/chat -H "Content-Type: application/json" \
  -d '{"question":"Halal là gì?","top_k":2,"agent_id":"aminra"}' | head -c 200
```

### Flow 3: Forgot password
**Goal:** Lost-password user resets to new credentials.

**Steps:**
1. `/business/login` → click "Quên mật khẩu?"
2. Enter `demo.biz@example.com` → submit
3. See generic confirmation (no leak)
4. Extract token from DB, navigate to `/reset-password?token=<TOKEN>`
5. Set new password `NewPass1234` → success
6. Login with new password → access granted
7. Login with old password → 401

**Critical:**
- [ ] Generic message regardless of email validity
- [ ] Token single-use (60 min TTL)
- [ ] Password rule enforced

### Flow 4: Landing + Privacy/Terms
**Goal:** First-time visitor sees compliant legal pages.

**Steps:**
1. Visit `/` → CTAs functional
2. Click footer "Chính sách bảo mật" → 10 sections render
3. Click "Điều khoản dịch vụ" → 12 sections
4. Verify "Cập nhật lần cuối: 2026-04-25"
5. Verify "Nghị định 13/2023/NĐ-CP" in privacy

### Flow 5: Public cert PDF download
**Goal:** Importer downloads PDF; opens with QR + hash.

**Steps:**
1. From `/verify/HALAL-2026-DEMO` click "Tải PDF"
2. File downloads as `HALAL-2026-DEMO.pdf`
3. PDF includes: logo, title (vi+en), cert number, dates, QR code, hash footer
4. QR scans to public verify URL

---

## Tier 2 — Business flows (6)

### Flow 6: Business registration → dashboard
1. `/business/register` form → submit
2. Redirect `/business/login`
3. Login → `/dashboard/business`
4. Dashboard widgets render

### Flow 7: Document upload + AI evaluation
1. `/upload` → pick demo PDF
2. Status `uploaded` → click "Đánh giá AI" → status `evaluating`
3. After 30-90s status `evaluated` with compliance_score 0-100
4. Issues list with severity + suggestions

### Flow 8: Submit hồ sơ tới CB
1. `/submissions` → "Tạo hồ sơ mới"
2. Pick provider, tick docs, add notes
3. Submit → toast confirms
4. Submission appears in list with status `pending`/`reviewing`
5. Provider notified

### Flow 9: Self-assessment
1. `/self-assessment` → "Bắt đầu đánh giá"
2. Pick standard (JAKIM MS 1500)
3. Tick 50-100 checklist items
4. Save partial → reload → state restored
5. "Hoàn thành" → score displayed
6. Export PDF

### Flow 10: Resubmit after revision request
1. Submission with status `revision_required`
2. Click expand → RevisionPanel shows feedback
3. Read per-doc issues with severity
4. Upload replacement docs (optional)
5. "Đã sửa — gửi lại" with notes
6. Status → `reviewing`, round resolved

### Flow 11: View submission status + history
1. `/submissions` → list all owned
2. Verify status badges, deadline, SLA badge if at-risk
3. Filter/search functional
4. Tenant isolation: business A ≠ business B

---

## Tier 3 — Provider flows (5)

### Flow 12: Provider login + portfolio
1. `/provider/login` → dashboard
2. Stats accurate vs DB
3. Portfolio drill-down works

### Flow 13: Review → request revision (COMPLEX)
1. Click submission → expand
2. Tabs: Documents, Đánh giá Halal, Comments
3. RevisionPanel "Yêu cầu sửa" → form
4. Overall feedback + add per-doc issues with severity + suggestion
5. Submit → status `revision_required`, business notified

### Flow 14: Assign auditor
1. Submission expand → "Gán auditor" dropdown
2. Pick auditor → save
3. Auditor sees in their queue; other auditors don't

### Flow 15: Approve → issue cert (COMPLEX)
1. All submissions for business `approved`
2. "Cấp chứng nhận" form → expiry + notes
3. PDF generated, cert number assigned, QR created
4. Public verify URL works
5. Block if duplicate active cert exists

### Flow 16: Cert revoke với reason
1. `/certificates` → click cert → "Thu hồi"
2. Modal with mandatory reason textarea
3. Submit → status `revoked` + banner shows reason
4. Public verify shows revocation
5. DB CHECK constraint enforces reason

---

## Tier 4 — Auditor flow (1)

### Flow 17: Onsite audit (COMPLEX)
1. Auditor `/audits` → click visit
2. "Bắt đầu visit" → status `in_progress`, GPS recorded
3. Checklist 30 items: Pass/Fail/N/A
4. Failed item → NCR with severity + photo
5. Auditor + business signatures on canvas
6. "Hoàn tất" → status `report_submitted`
7. Audit report PDF generated with all data

**Mobile-specific:**
- iOS Safari camera + gallery upload
- Touch signature canvas
- GPS permission

---

## Tier 5 — Admin flows (3)

### Flow 18: Analytics dashboard
1. `/admin/analytics` → 5 widgets render
2. Numbers match DB queries

### Flow 19: Approve pending provider
1. List pending providers
2. Click "Approve" → status `active`
3. Provider notified, can login

### Flow 20: Overdue escalation queue
1. `/admin/overdue-submissions`
2. Table sorted by deadline (oldest first)
3. Email links to providers
4. Resolved submissions disappear from queue

---

## Cross-cutting verification

| Aspect | Check |
|---|---|
| Mobile | iPhone 14 Safari + Pixel 7 Chrome + iPad Pro |
| i18n | Switch vi → en, all 20 flows still work |
| Performance | LCP < 2.5s, TTI < 3.5s |
| Security | CSRF tokens present, JWT expiry 8h |
| Accessibility | No critical axe violations |
| Visual regression | No unintentional CSS shifts |

---

## Disaster recovery during demo

| Issue | Fix |
|---|---|
| Backend container crashed | `docker compose up -d aminra-backend` |
| Frontend white screen | Hard refresh (Ctrl+Shift+R) + check console |
| Login 401 | Check Vault: `docker exec ... cat /vault/secrets/env.sh` |
| RAG chat timeout | Skip Flow 2, demo later |
| PDF generation fail | Use pre-generated PDF |
| Polygon RPC down | Skip blockchain badge demo |
| DB transient error | `docker exec aminra-docker-system-postgres-db-1 pg_isready` |

---

## Recommended demo sequence (45-60 min)

```
[10 min] Tier 1 Public — landing, verify cert, RAG chat
[15 min] Tier 2 Business — register, upload + AI eval, submit
[15 min] Tier 3 Provider — review, request revision, approve, issue cert
[10 min] Tier 4 + 5 — audit highlights, admin overdue queue
[10 min] Q&A buffer
```

---

## Test artifacts location

- Automated test specs: `frontend/aminra-web/e2e/17-cuj-*.spec.ts`
- Backend tests: `backend/tests/test_*.py`
- Seed script: `scripts/seed_demo_data.py`
- Pre-demo verifier: `scripts/pre_demo_check.sh`
