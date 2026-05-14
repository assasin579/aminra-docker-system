# AMINRA Auditor — Mobile (Expo)

Field-audit companion app for CB auditors. Login with the same provider account
as `aminra.vn`, see assigned visits, fill checklist, capture photos, sign-off
with GPS.

## Status — Phase 1 MVP scaffold (2026-04-26)

| Screen | File | Status |
|---|---|---|
| Login | `app/(auth)/login.tsx` | ✅ |
| Visits list | `app/(app)/visits/index.tsx` | ✅ |
| Visit detail + checklist | `app/(app)/visits/[id]/index.tsx` | ✅ |
| Photo capture | `app/(app)/visits/[id]/photos.tsx` | ✅ (camera + resize + upload) |
| Sign-off | `app/(app)/visits/[id]/sign-off.tsx` | ✅ (GPS; signature pad pending Phase 1.4) |
| Offline queue + sync | `lib/offline.ts` | ⏳ Phase 1.4 |
| Push notifications | `lib/push.ts` | ⏳ Phase 1.5 |

## Run locally (dev)

```bash
cd mobile/auditor-app
npm install                       # one-time
npm start                         # Expo dev server, scan QR with Expo Go
# OR
npm run android                   # if Android emulator running
npm run ios                       # if macOS + iOS simulator
```

Backend defaults to `https://dev-web.silvergem.org`; override in `app.json` →
`expo.extra.apiBaseUrl` for staging/prod, or set per-env via EAS profiles.

## Test login

Use any existing provider account from the web. Demo seed:

- `cb-demo@demo.aminra.vn` / `DemoP@ss2026` (provider owner)
- `auditor-demo@demo.aminra.vn` / `DemoP@ss2026` (auditor sub-role)

## Deploy to TestFlight / Play Internal

```bash
npm install -g eas-cli
eas login
eas build:configure                # creates eas.json
eas build --platform ios --profile preview
eas build --platform android --profile preview
eas submit --platform ios          # → TestFlight
eas submit --platform android      # → Play Internal
```

Prerequisites:
- Apple Developer Program ($99/yr) — needs D-U-N-S, ~2 weeks
- Google Play Developer ($25 once)
- Bundle ids already set: `vn.aminra.auditor`

## Architecture

- **Routing:** expo-router (file-based, mirrors Next.js feel)
- **Data:** TanStack Query for server state; SecureStore for JWT
- **Auth:** Keycloak OAuth2 password grant against the realm (`POST /realms/aminra/protocol/openid-connect/token`), then `/api/auth/me` to resolve the AMINRA profile + enforce the provider-role guard. Token stored in SecureStore.
- **Images:** Resize to 1600px @ 0.7 quality before upload (factory wifi friendly)
- **GPS:** `expo-location` with foreground permission for sign-off
- **Tokens:** Design tokens in `lib/tokens.ts` mirror web emerald-700 brand

## Backend dependencies

| Endpoint | Used by |
|---|---|
| `POST {KEYCLOAK_URL}/realms/aminra/protocol/openid-connect/token` (grant_type=password) | Login |
| `GET  /api/auth/me` | Profile resolve (post-login + token verify on app launch) |
| `GET  /api/audits/` | Visits list |
| `GET  /api/audits/visits/{id}` | Visit detail |
| `GET  /api/audits/visits/{id}/items` | Checklist |
| `PUT  /api/audits/visits/{id}/items/{item_id}` | Mark pass/fail/na |
| `POST /api/audits/visits/{id}/status` | Status transitions |
| `POST /api/audits/{vid}/items/{item_id}/photo` | Photo upload (multipart) |
| `POST /api/audits/{vid}/signature?type=auditor` | Signature upload (Phase 1.4) |

## Known gaps for Phase 1.4

- Signature pad (currently stubbed) — use `react-native-svg` + custom path drawing
- Offline queue (SQLite + Network state observer)
- NCR creation flow
- Push notification registration

See `memory/project_aminra_mobile_roadmap.md` in repo brain for full roadmap.
