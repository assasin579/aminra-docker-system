# Hướng dẫn tạo Mobile App AMINRA — Từ 0 đến App Store

> **Đối tượng:** Người chưa từng làm mobile app. Có biết một chút lập trình là đủ.
> **Sản phẩm cuối:** App AMINRA Auditor có thể tải từ App Store (iOS) + Play Store (Android).
> **Tổng thời gian:** ~3 tuần (gồm thời gian chờ approval Apple/Google).
> **Tổng chi phí 1 năm đầu:** ~$125 USD (Apple $99 + Google $25 once).

---

## Bản đồ tổng quan

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  PHẦN 1      │  │  PHẦN 2      │  │  PHẦN 3      │  │  PHẦN 4      │
│  Chuẩn bị    │→ │  Code &      │→ │  Build cloud │→ │  Phát hành   │
│  (1 ngày)    │  │  Test        │  │  (4 giờ)     │  │  (1-2 tuần)  │
│              │  │  (∞)         │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘

  Cài tools          Sửa code          eas build            TestFlight
  Apple Dev          Hot reload        Tải file .apk        Play Internal
  Google Play        npm start         Tải file .ipa        Production
  Expo account       Test trên phone                        Live
```

---

## PHẦN 1 — Chuẩn bị máy & tài khoản

### Bước 1.1 — Cài Node.js (5 phút)

Node.js là môi trường chạy JavaScript. Expo + React Native cần nó.

**Mac/Linux:**
```bash
# Cài bản LTS mới nhất qua nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install --lts
node --version    # nên thấy v20.x.x hoặc cao hơn
```

**Windows:**
Tải installer từ https://nodejs.org → chọn bản LTS → Next Next Finish → mở Command Prompt → `node --version`.

> ✅ Done khi `node --version` ra số ≥ 20.

### Bước 1.2 — Cài Expo Go trên điện thoại (2 phút)

Đây là app cho phép bạn chạy app đang dev mà không cần build. Dev rất nhanh.

- **iPhone:** App Store → tìm "Expo Go" → cài
- **Android:** Play Store → tìm "Expo Go" → cài

> ⚠️ Lưu ý: máy tính + điện thoại phải cùng wifi để dev mode hoạt động.

### Bước 1.3 — Tạo tài khoản Expo (5 phút, miễn phí)

Expo là công ty làm React Native dễ hơn. Bạn cần tài khoản để build app trên cloud của họ.

```bash
npm install -g eas-cli
eas login
# Nó hỏi tên, email, password — tạo tài khoản mới
```

> ✅ Done khi `eas whoami` ra username của bạn.

### Bước 1.4 — Tạo Apple Developer account ($99/năm, ~2 tuần)

Đây là cổng vào để app lên App Store.

1. Vào https://developer.apple.com/programs/enroll/
2. Đăng nhập bằng Apple ID (cùng cái dùng iPhone)
3. Nếu đăng ký dạng **Company** (khuyến nghị cho AMINRA):
   - Cần **D-U-N-S Number** (mã định danh doanh nghiệp toàn cầu)
   - Đăng ký miễn phí tại https://developer.apple.com/enroll/duns-lookup/
   - Apple verify → mất 1-2 tuần
4. Trả $99 USD (Apple sẽ charge thẻ visa/mastercard)
5. Đợi email xác nhận

> 🟡 **Tip:** Nếu cần ship sớm, đăng ký dạng **Individual** ($99 vẫn vậy nhưng D-U-N-S không cần). Sau này upgrade lên Company sau cũng được.

### Bước 1.5 — Tạo Google Play Developer account ($25 once)

Một lần $25 là dùng vĩnh viễn.

1. Vào https://play.google.com/console/signup
2. Đăng nhập Google account
3. Trả $25
4. Điền tên công ty, địa chỉ, contact
5. Done — không cần D-U-N-S

> ✅ Done sau ~30 phút.

### Bước 1.6 — Cài Git (nếu chưa có)

Git để quản lý code. Bạn đã có nếu repo `aminra-docker-system` chạy được.

```bash
git --version    # nếu ra version → OK
```

---

## PHẦN 2 — Code & Test

### Bước 2.1 — Mở dự án có sẵn (1 phút)

App đã được scaffold sẵn ở `mobile/auditor-app/`. Bạn chỉ cần install deps:

```bash
cd /home/user/Documents/aminra-docker-system/mobile/auditor-app
npm install --legacy-peer-deps
```

Đợi 1-2 phút.

### Bước 2.2 — Hiểu cấu trúc thư mục (5 phút đọc)

```
mobile/auditor-app/
├── app/                    ← các MÀN HÌNH (mỗi file = 1 màn hình)
│   ├── _layout.tsx         ← layout chung (provider, navigation)
│   ├── index.tsx           ← màn hình mở đầu (redirect tới login hoặc visits)
│   ├── (auth)/
│   │   └── login.tsx       ← màn đăng nhập
│   └── (app)/
│       └── visits/
│           ├── index.tsx           ← danh sách visit
│           └── [id]/
│               ├── index.tsx       ← chi tiết visit + checklist
│               ├── photos.tsx      ← chụp ảnh
│               └── sign-off.tsx    ← GPS + đóng visit
│
├── lib/                    ← TIỆN ÍCH (auth, API, design tokens)
│   ├── api.ts              ← gọi backend
│   ├── auth.ts             ← Keycloak password grant + lưu token bảo mật (SecureStore)
│   ├── AuthContext.tsx     ← share auth state cho mọi màn hình
│   └── tokens.ts           ← màu sắc + kích thước
│
├── package.json            ← danh sách thư viện
├── app.json                ← config app (tên, icon, permissions)
└── tsconfig.json           ← config TypeScript
```

**Quy tắc đơn giản của expo-router:**
- File trong `app/` = 1 màn hình
- Tên file `[id].tsx` = URL có biến (vd `/visits/abc-123`)
- Folder `(name)` = nhóm logic (không xuất hiện trong URL)
- File `_layout.tsx` = wrap quanh các route con

### Bước 2.3 — Chạy app lần đầu (5 phút)

```bash
npm start
```

Xuất hiện QR code trong terminal.

- **iPhone:** mở camera → quét QR → bấm link → Expo Go mở app
- **Android:** mở Expo Go → bấm "Scan QR Code" → quét

App load ~30 giây lần đầu (sau đó nhanh).

> 🐛 **Hay gặp lỗi:** "Tunnel started... but unreachable"
>   - Cách 1: Đảm bảo điện thoại + máy tính cùng wifi
>   - Cách 2: Chạy `npm start -- --tunnel` (dùng Expo cloud relay, chậm hơn nhưng luôn work)

### Bước 2.4 — Sửa code và thấy thay đổi ngay (Hot Reload)

Đây là phần ma thuật. Mở 1 file, sửa, save → app trên điện thoại tự reload.

Thử ngay:

1. Mở `app/(auth)/login.tsx`
2. Tìm dòng `<Text style={{...}}>AMINRA Auditor</Text>`
3. Đổi thành `<Text style={{...}}>AMINRA Của Tôi</Text>`
4. Save (Ctrl+S)
5. Nhìn vào điện thoại — chữ thay đổi ngay (không cần restart)

> 💡 Đây là cách bạn dev mọi feature. Code → save → thấy ngay.

### Bước 2.5 — Connect tới backend AMINRA thật (10 phút)

App hiện trỏ về `https://dev-web.silvergem.org`. Đổi tới backend của bạn:

Mở `app.json`:
```json
"extra": {
  "apiBaseUrl": "https://your-domain.vn"     ← đổi thành domain bạn
}
```

Save → restart app (Ctrl+C → `npm start`).

> 🐛 **Lưu ý:** Nếu test với backend local (`localhost:8100`), thay localhost bằng IP máy tính trên LAN (vd `192.168.1.5:8100`). Điện thoại không hiểu localhost của máy tính.

### Bước 2.6 — Test flow đăng nhập + xem visit

1. App mở ra trang login
2. Nhập email + password của 1 provider/auditor account thật (vd `cb-demo@demo.aminra.vn` / `DemoP@ss2026`). Login đi qua **Keycloak OAuth2 password grant** trực tiếp tới `auth.silvergem.org` (xem `lib/auth.ts`) — không phải REST /auth/login như bản cũ.
3. Đăng nhập → vào trang Visits → thấy danh sách audit
4. Click 1 visit → thấy checklist
5. Click pass/fail → backend update real-time

Nếu work hết → bạn đã có app dev mode chạy thật. 🎉

> 🔧 **Đổi Keycloak target:** nếu test với realm khác, sửa `keycloakUrl` / `keycloakRealm` / `keycloakClientId` trong `app.json` (section `extra`). Mặc định trỏ tới `https://auth.silvergem.org` / realm `aminra` / client `aminra-frontend`.

---

## PHẦN 3 — Build production app

### Bước 3.1 — Hiểu khác biệt: Expo Go vs Production Build

| Loại | Khi nào dùng | Tốc độ | Có thể publish? |
|---|---|---|---|
| **Expo Go** (dev) | Code + test hằng ngày | Hot reload tức thì | ❌ |
| **Development build** | Test custom native modules | Nhanh nhưng cần build | ❌ |
| **Preview build** | Beta test với 1-2 người | 15 phút build | ❌ (qua TestFlight/Internal) |
| **Production build** | Phát hành chính thức | 15 phút build | ✅ |

Phần này làm Preview build trước (an toàn, ít rủi ro), rồi upgrade lên Production.

### Bước 3.2 — Setup EAS Build (10 phút, lần đầu)

EAS là dịch vụ build trên cloud của Expo (free tier 30 builds/tháng — đủ cho dev).

```bash
cd mobile/auditor-app
eas build:configure
# Nó hỏi: Setup for which platforms? → chọn All
# Tạo file eas.json (config build)
```

File `eas.json` được tạo với 3 profile:
- `development` — dev build
- `preview` — beta test (apk/ipa local install)
- `production` — App Store / Play Store

### Bước 3.3 — Build lần đầu cho Android (15 phút)

Android dễ hơn iOS — bắt đầu từ đây.

```bash
eas build --platform android --profile preview
```

Lần đầu nó hỏi:
- "Generate a new Android Keystore?" → **YES** (Expo lưu giùm bạn)
- "Choose a build" → cứ đợi

→ EAS upload code lên cloud → build → 10-15 phút.

Khi xong:
```
✔ Build finished
🪐 Android app:
https://expo.dev/artifacts/eas/abc123.apk
```

→ Mở link đó trên điện thoại Android → tải về → cài → mở.

> ⚠️ Android sẽ cảnh báo "Unknown source" — chấp nhận → "Install anyway".

### Bước 3.4 — Build lần đầu cho iOS (15 phút)

iOS phức tạp hơn vì cần Apple credentials.

```bash
eas build --platform ios --profile preview
```

Lần đầu nó hỏi:
- "Apple ID?" → email Apple Developer
- "Password?" → password (kèm 2FA code)
- "Generate Provisioning Profile?" → YES
- "Generate Distribution Certificate?" → YES

Đợi 15 phút. Khi xong → file `.ipa`.

> ⚠️ Không cài trực tiếp lên iPhone được — phải qua TestFlight (Phần 4).

> 💡 **Mẹo cho người không có Mac:** EAS làm hết — bạn không cần Macbook để build iOS. Đây là điểm đáng giá $19/tháng.

---

## PHẦN 4 — Phát hành

### Bước 4.1 — TestFlight (iOS beta, 1-2 ngày)

TestFlight = nơi mời người dùng test app iOS trước khi public.

1. **Tạo app trên App Store Connect:**
   - Vào https://appstoreconnect.apple.com
   - "My Apps" → "+" → "New App"
   - Bundle ID: `vn.aminra.auditor` (đã set trong app.json)
   - Tên: AMINRA Auditor
   - Save

2. **Upload build:**
   ```bash
   eas submit --platform ios --profile production
   ```
   → EAS upload file `.ipa` lên App Store Connect → mất 30 phút Apple process.

3. **Mời beta tester:**
   - App Store Connect → app → TestFlight tab
   - "Add testers" → email
   - Họ nhận email, click → cài app TestFlight → test app của bạn

4. **Iterate:**
   - Sửa code → `eas build` lại → `eas submit` → tester thấy version mới sau 30 phút

> 💡 TestFlight cho phép tới **10,000 tester** — đủ cho mọi business case.

### Bước 4.2 — Google Play Internal Testing (Android beta, 1 ngày)

1. **Tạo app trên Play Console:**
   - Vào https://play.google.com/console
   - "Create app"
   - Tên: AMINRA Auditor
   - Default language: Vietnamese
   - Phải điền form về privacy policy, target audience, etc. (~30 phút)

2. **Upload build:**
   ```bash
   eas submit --platform android --profile production
   ```

3. **Tạo Internal Testing track:**
   - Play Console → app → "Testing" → "Internal testing"
   - Add tester email list (max 100 cho internal)
   - Share opt-in URL → tester click → cài qua Play Store

> 💡 Google Play review **internal track** rất nhanh (~vài giờ) so với production (3-7 ngày).

### Bước 4.3 — Production launch (1-2 tuần review)

Khi beta tester happy → submit production:

**iOS:**
1. App Store Connect → app → "App Store" tab → "+" version 1.0
2. Điền:
   - Screenshots (5 cái, kích thước iPhone 15 Pro Max + iPad)
   - Description (vi + en)
   - Keywords
   - Support URL: `https://aminra.vn/support`
   - Privacy Policy URL: `https://aminra.vn/privacy`
3. Submit for Review → Apple review 24-72 giờ

**Android:**
1. Play Console → app → "Production" → "Create new release"
2. Promote build từ Internal Testing
3. Điền store listing (icon, screenshots, description)
4. Submit → Google review 1-3 ngày

**🎉 Live!** App xuất hiện trên store, bất kỳ ai search "AMINRA" cũng tải được.

---

## PHẦN 5 — Sau khi live

### Bước 5.1 — OTA Updates (cập nhật không cần Apple/Google review)

Đây là siêu power của Expo: sửa code JavaScript → đẩy update → user nhận tự động trong 5 phút, KHÔNG cần re-submit App Store.

```bash
eas update --branch production --message "Sửa lỗi load slow"
```

User mở app lần sau → app tự download bản mới → reload.

> ⚠️ OTA chỉ work cho code JS/UI. Nếu thay native modules (vd thêm camera plugin mới) → phải build + submit lại.

### Bước 5.2 — Theo dõi crash + error

Cài Sentry để biết app crash ở đâu:

```bash
npx expo install sentry-expo
```

Setup theo docs Sentry. Khi user bị crash → bạn nhận email kèm stack trace.

### Bước 5.3 — Versioning

Mỗi lần submit App Store cần tăng version:

`app.json`:
```json
"version": "1.0.1",     ← user thấy
"ios": { "buildNumber": "2" },     ← Apple track
"android": { "versionCode": 2 }     ← Google track
```

Hoặc dùng `expo-build-properties` plugin để auto-increment.

---

## Tổng kết timeline thực tế

| Tuần | Việc | Ai làm |
|---|---|---|
| **1** | Phần 1 (chuẩn bị) + Apple D-U-N-S verification | Bạn |
| 2 | Phần 2 (code thêm features còn thiếu) | Bạn |
| 3 | Phần 3 (first build) + Phần 4.1-4.2 (beta) | Bạn + EAS cloud |
| 4 | Beta feedback → fix → re-build | Bạn + 5-10 beta tester |
| 5 | Submit production → wait review | Apple + Google |
| 6 | **🎉 LIVE** trên 2 store | — |

## Cost summary 1 năm

```
Apple Developer Program       $99/năm
Google Play Developer         $25 (1 lần)
EAS Build (free tier)         $0/tháng (đủ 30 builds)
EAS Build (production tier)   $19/tháng (khi cần >30 builds)
Sentry (free tier)            $0/tháng (5k events/tháng)
─────────────────────────────────────────
TỔNG năm 1                    ~$125 USD
TỔNG năm 2+                   ~$99/năm + $19/tháng nếu prod tier
```

## Khi cần help

| Vấn đề | Tra cứu |
|---|---|
| Lỗi build EAS | https://docs.expo.dev/build-reference/troubleshooting/ |
| Lỗi RN code | https://docs.expo.dev — search lỗi |
| Apple Developer | https://developer.apple.com/forums/ |
| Play Console | https://support.google.com/googleplay/android-developer/ |
| Hỏi cộng đồng | Expo Discord https://chat.expo.dev (cực kỳ active) |

## Checklist done

- [ ] **Phần 1.1-1.6:** Cài Node, Expo Go, EAS CLI, Apple Dev, Play Dev — 1 ngày
- [ ] **Phần 2.1-2.6:** Mở project, hiểu structure, dev với hot reload — vài giờ
- [ ] **Phần 3.1-3.4:** First Android + iOS builds — 1 ngày
- [ ] **Phần 4.1:** Upload TestFlight + mời tester — 1 ngày
- [ ] **Phần 4.2:** Upload Play Internal — vài giờ
- [ ] **Phần 4.3:** Submit production → live — 1-2 tuần (chờ review)

**Tổng:** 3 tuần realistic timeline cho 1 người chưa biết gì.

---

> 📁 Project location: `mobile/auditor-app/`
> 📋 Roadmap memory: `~/.claude/projects/-home-user-Documents/memory/project_aminra_mobile_roadmap.md`
> 📚 Document này: `mobile/MOBILE_APP_GUIDE.md`
