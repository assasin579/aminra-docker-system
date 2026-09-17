# AMINRA Gate 1 Customer Onboarding Acceptance Matrix

Generated: 2026-09-17T05:56:49

| ID | Priority | Category | Scenario | Test target | Status | Customer risk if failed |
|---|---|---|---|---|---|---|
| G1-ENTRY-001 | P1 | ENTRY | Landing page loads on fresh browser, incognito, and logged-out state. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-ENTRY-002 | P0 | ENTRY | Business login page has `Về trang chủ`, Keycloak CTA, and does not trap unauthenticated users. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ENTRY-003 | P0 | ENTRY | Provider login page has the same escape/CTA behavior. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ENTRY-004 | P0 | ENTRY | Direct deep link to protected business page redirects to login, then returns to the intended page after login if safe. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ENTRY-005 | P1 | ENTRY | Direct deep link to provider-only page as business user shows clear no-access message, not redirect loop. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-ENTRY-006 | P0 | ENTRY | Browser back button after login does not resurrect login page with stale authenticated state. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ENTRY-007 | P0 | ENTRY | Browser refresh on dashboard preserves session and role context. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ENTRY-008 | P1 | ENTRY | Two tabs open: logout in one tab causes the other tab to require re-auth or refresh identity safely. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-ENTRY-009 | P0 | ENTRY | Session expiry while editing a form preserves draft locally if possible, or clearly asks user to re-login without data loss. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ENTRY-010 | P0 | ENTRY | User opens app after many hours: stale local profile is not shown before `/auth/me` verifies token. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-IDENTITY-001 | P0 | IDENTITY | Valid new business self-registration succeeds and sends verification email. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-IDENTITY-002 | P0 | IDENTITY | Duplicate email registration does not create duplicate Keycloak/Postgres rows. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-IDENTITY-003 | P1 | IDENTITY | Duplicate company name with different owner follows the intended policy and explains conflict clearly. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-004 | P1 | IDENTITY | Email with uppercase letters normalizes consistently. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-005 | P1 | IDENTITY | Email with leading/trailing spaces is trimmed or rejected consistently. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-006 | P1 | IDENTITY | Invalid email domains/formats show inline error. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-007 | P1 | IDENTITY | Password below policy is rejected with readable policy details. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-008 | P1 | IDENTITY | Password with user email/name is rejected if Keycloak policy enforces it; UI message is readable. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-009 | P1 | IDENTITY | Terms/privacy required checkbox cannot be bypassed if required. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-010 | P1 | IDENTITY | Required business fields missing show field-level errors. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-011 | P0 | IDENTITY | Registration interrupted after Keycloak user creation but before app DB row creation compensates or recovers idempotently. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-IDENTITY-012 | P1 | IDENTITY | Re-submitting after network timeout does not create duplicate users/tenants. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-013 | P1 | IDENTITY | Verification email resend works and rate-limits abuse. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-014 | P1 | IDENTITY | Verification link opened on a different browser/device completes the account and does not require original browser state. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-015 | P1 | IDENTITY | Expired verification link offers resend path. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-016 | P1 | IDENTITY | Already verified link shows safe success/already-verified message, not scary failure. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-017 | P0 | IDENTITY | Disabled/suspended account cannot verify/login and sees support guidance. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-IDENTITY-018 | P1 | IDENTITY | Provider/CB invite accepts only intended email/role. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-019 | P0 | IDENTITY | Auditor invite accepts only intended email/assignment. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-IDENTITY-020 | P1 | IDENTITY | Invite link expired shows clear contact/resend path. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-021 | P1 | IDENTITY | Invite already used cannot provision a second account. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-022 | P1 | IDENTITY | Invite opened by wrong existing logged-in user warns and requires logout/account switch. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-IDENTITY-023 | P0 | IDENTITY | Provider/auditor invite failure does not leave orphan Keycloak user without app row. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-EMAIL-001 | P0 | EMAIL | Verify email subject/sender/from-domain are recognizable to customer. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-EMAIL-002 | P0 | EMAIL | Verify email link points to canonical `auth.aminra.org` / `aminra.org`, never legacy `silvergem.org`. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-EMAIL-003 | P0 | EMAIL | Password reset email link points to canonical domain. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-EMAIL-004 | P1 | EMAIL | Email HTML and plaintext contain enough context and no secrets. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-EMAIL-005 | P1 | EMAIL | User clicks the newest verification email after requesting resend multiple times; newest works, old links fail safely or remain valid per policy. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-EMAIL-006 | P1 | EMAIL | SMTP provider accepts but event is delayed; UI sets expectation and offers resend after cooldown. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-EMAIL-007 | P1 | EMAIL | SMTP provider failure surfaces as retry/support, not silent success. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-EMAIL-008 | P1 | EMAIL | Rate limiting prevents email spam without locking legitimate customer permanently. | `e2e/41-gate1-onboarding-email.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-001 | P0 | SESSION | Correct business credentials login successfully. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SESSION-002 | P1 | SESSION | Wrong password shows non-enumerating error. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-003 | P1 | SESSION | Nonexistent email shows non-enumerating error. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-004 | P1 | SESSION | Unverified account gets verification-required guidance. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-005 | P1 | SESSION | Disabled account gets support guidance. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-006 | P1 | SESSION | Locked/brute-force account gets safe support guidance. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-007 | P0 | SESSION | Business logout clears local/session storage and app profile. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SESSION-008 | P0 | SESSION | Provider logout clears provider state and Keycloak realm session as designed. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SESSION-009 | P0 | SESSION | Platform admin logout does not leave admin token/profile. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SESSION-010 | P1 | SESSION | Business -> provider account switch in same browser shows correct organization/sidebar. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-011 | P1 | SESSION | Provider -> admin account switch does not show provider menu inside admin panel. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-012 | P0 | SESSION | Login in private/incognito works without service-worker cache residue. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SESSION-013 | P1 | SESSION | Service worker update does not cache auth/admin routes. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer friction or support load increases |
| G1-SESSION-014 | P0 | SESSION | Refresh token expiry leads to controlled re-login, not blank screen. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SESSION-015 | P0 | SESSION | Malformed/expired token API calls return 401 and frontend prompts re-auth. | `e2e/42-gate1-role-landing.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-BUSINESS-001 | P1 | BUSINESS | Empty profile displays setup checklist. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-002 | P1 | BUSINESS | Valid company profile save persists after refresh. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-003 | P1 | BUSINESS | Invalid tax/company identifier format is rejected if policy exists. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-004 | P1 | BUSINESS | Logo upload valid image succeeds. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-005 | P1 | BUSINESS | Unsupported file type, huge file, and corrupted file show clear error. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-006 | P1 | BUSINESS | Missing company logo returns graceful empty state, not 500/noisy error. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-007 | P0 | BUSINESS | Business can create first material with eligible supplier. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-BUSINESS-008 | P1 | BUSINESS | Supplier dropdown lists only eligible suppliers for selected material category. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-009 | P1 | BUSINESS | No eligible supplier state explains next step instead of showing empty unexplained dropdown. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-010 | P1 | BUSINESS | Ineligible/expired supplier is rejected backend-side even if user tampers request. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-011 | P1 | BUSINESS | Material create/update non-2xx keeps form open and shows readable error. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-012 | P1 | BUSINESS | Process create persists, appears in list, detail, and after refresh. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-013 | P1 | BUSINESS | Process update with invalid fields shows field-level error. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-014 | P1 | BUSINESS | Batch create with valid materials/process succeeds. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-015 | P1 | BUSINESS | Batch create without required materials/process is blocked. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-016 | P1 | BUSINESS | Batch with duplicate code/identifier follows conflict policy and explains it. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-017 | P1 | BUSINESS | Sealed batch cannot be mutated; UI explains immutable/sealed state. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-018 | P0 | BUSINESS | Public trace is unavailable before publish/seal readiness. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-BUSINESS-019 | P1 | BUSINESS | Published/sealed trace shows snapshot state, not later live mutation. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-020 | P1 | BUSINESS | Bulk/rapid double-click submit does not create duplicates. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-BUSINESS-021 | P1 | BUSINESS | Network offline during save shows retry and does not claim success. | `e2e/43-gate1-business-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-001 | P0 | PROVIDER | Provider sees only own submissions/certificates/authority records. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-PROVIDER-002 | P1 | PROVIDER | Provider cannot search or open another provider's record by URL/id. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-003 | P1 | PROVIDER | Provider can perform allowed status transition. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-004 | P1 | PROVIDER | Invalid status transition is blocked with clear explanation. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-005 | P0 | PROVIDER | Provider certificate action output matches backend state after refresh. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-PROVIDER-006 | P1 | PROVIDER | Provider cannot create/mark supplier eligibility without source authority evidence. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-007 | P1 | PROVIDER | Provider cannot take over another provider's supplier eligibility. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-008 | P1 | PROVIDER | Expired certificate/authority cannot be used for active eligibility. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-009 | P1 | PROVIDER | Revoked/suspended certificate disappears or is marked unavailable in business selection. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-010 | P1 | PROVIDER | Provider upload/view certificate PDF works with valid file. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-011 | P1 | PROVIDER | Invalid PDF/file type too large is rejected. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-PROVIDER-012 | P0 | PROVIDER | Provider public certificate verification page shows correct public fields only. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-PROVIDER-013 | P1 | PROVIDER | Provider action race/double-submit remains idempotent or conflict-safe. | `e2e/44-gate1-provider-first-value.spec.ts` | TODO | Customer friction or support load increases |
| G1-AUDITOR-001 | P0 | AUDITOR | Auditor login lands on assigned workspace. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-AUDITOR-002 | P0 | AUDITOR | Auditor sees only assigned tenant/submission/batch. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-AUDITOR-003 | P0 | AUDITOR | Auditor direct URL to unassigned item returns forbidden/not-found without private hints. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-AUDITOR-004 | P0 | AUDITOR | Auditor allowed comment/review action persists if in scope. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-AUDITOR-005 | P0 | AUDITOR | Auditor cannot approve/finalize provider/admin-only actions. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-AUDITOR-006 | P0 | AUDITOR | Auditor account removed/disabled loses access immediately after refresh. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-AUDITOR-007 | P0 | AUDITOR | Auditor with no assignments sees helpful empty state. | `e2e/45-gate1-auditor-boundary.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ADMIN-001 | P1 | ADMIN | Platform admin can locate customer user by email without exposing secrets. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-002 | P1 | ADMIN | Platform admin can safely resend verification email. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-003 | P1 | ADMIN | Platform admin can reset password via Keycloak-backed endpoint. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-004 | P1 | ADMIN | Admin reset revokes sessions; target old session loses access. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-005 | P1 | ADMIN | Admin self-reset purges own session and requires re-login. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-006 | P1 | ADMIN | Admin cannot edit user password through profile update endpoint silently. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-007 | P1 | ADMIN | Admin disabled account state is reflected in login behavior. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-ADMIN-008 | P1 | ADMIN | Admin-created placeholder/test user cleanup removes Keycloak and app rows safely where intended. | `e2e/20-admin-unified-auth.spec.ts` | TODO | Customer friction or support load increases |
| G1-OUTPUT-001 | P0 | OUTPUT | Public certificate verify page shows exact certificate number, status, company, issue/expiry dates. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-OUTPUT-002 | P1 | OUTPUT | Expired/revoked certificate shows the correct non-active status. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer friction or support load increases |
| G1-OUTPUT-003 | P1 | OUTPUT | Draft/pending certificate is not public. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer friction or support load increases |
| G1-OUTPUT-004 | P0 | OUTPUT | Certificate PDF renders with correct status and no stale cached previous state. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-OUTPUT-005 | P0 | OUTPUT | Public trace valid opaque ID returns 200 and integrity markers. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-OUTPUT-006 | P0 | OUTPUT | Public trace invalid/random/injection ID returns safe 404/not-found. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-OUTPUT-007 | P0 | OUTPUT | Public trace does not leak tenant IDs, provider internal IDs, audit actor IDs, source certificate IDs, private notes. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-OUTPUT-008 | P1 | OUTPUT | Dashboard status badges match backend canonical state. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer friction or support load increases |
| G1-OUTPUT-009 | P0 | OUTPUT | After provider revokes certificate, business dashboard/public output reflect new state according to policy. | `e2e/47-gate1-output-correctness.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ERROR-001 | P1 | ERROR | Missing required field. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-002 | P1 | ERROR | Invalid format. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-003 | P1 | ERROR | Too long input. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-004 | P1 | ERROR | Leading/trailing whitespace. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-005 | P1 | ERROR | Unicode/Vietnamese names. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-006 | P1 | ERROR | HTML/script injection text renders escaped. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-007 | P1 | ERROR | Duplicate/conflict state. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-008 | P1 | ERROR | Unauthorized anonymous request. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-009 | P0 | ERROR | Forbidden authenticated role. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ERROR-010 | P0 | ERROR | Expired session. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-ERROR-011 | P1 | ERROR | Backend 422 `detail` array. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-012 | P1 | ERROR | Backend 409 conflict. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-013 | P1 | ERROR | Backend 429 rate limit. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-014 | P1 | ERROR | Backend 500. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-015 | P1 | ERROR | Network timeout/offline. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-016 | P1 | ERROR | Slow response with loading state. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-ERROR-017 | P1 | ERROR | Double submit while loading. | `e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-001 | P1 | UX | Chromium desktop full matrix passes. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-002 | P1 | UX | WebKit/Safari smoke for login/register/verify/reset/core dashboard if customer uses Safari. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-003 | P1 | UX | Mobile narrow viewport: login/register/reset usable, no horizontal overflow, CTA visible. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-004 | P1 | UX | Tablet viewport: dashboard/sidebar usable. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-005 | P1 | UX | Keyboard-only navigation through login/register/reset forms works. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-006 | P1 | UX | Focus moves to first invalid field or error summary after failed submit. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-007 | P1 | UX | Screen-reader labels exist for critical inputs/buttons. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-008 | P1 | UX | Color contrast serious warnings triaged for onboarding-critical pages. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-009 | P1 | UX | Vietnamese and English copy both understandable if app supports both. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-UX-010 | P1 | UX | Date/time/number formatting is consistent for certificate validity and statuses. | `e2e/accessibility.spec.ts` | TODO | Customer friction or support load increases |
| G1-INTEGRITY-001 | P1 | INTEGRITY | User presses submit twice quickly: one record or safe duplicate prevention. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-INTEGRITY-002 | P1 | INTEGRITY | User opens same edit form in two tabs; stale save conflict policy is clear. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-INTEGRITY-003 | P0 | INTEGRITY | Backend rejects tampered tenant/provider IDs even if UI hides them. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-INTEGRITY-004 | P0 | INTEGRITY | Partial provisioning failure compensates or recovers idempotently. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-INTEGRITY-005 | P1 | INTEGRITY | Audit log records critical onboarding/account/security actions. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-INTEGRITY-006 | P1 | INTEGRITY | Append-only audit immutability is respected; tests must not bypass trigger. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-INTEGRITY-007 | P1 | INTEGRITY | Created QA records can be identified and cleaned up safely. | `backend/integration + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-SECURITY-001 | P0 | SECURITY | Anonymous cannot access protected APIs/pages. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-002 | P0 | SECURITY | Business cannot access provider/admin/auditor routes. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-003 | P0 | SECURITY | Provider cannot access platform-admin routes. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-004 | P0 | SECURITY | Auditor cannot access business owner/provider-admin mutation routes. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-005 | P1 | SECURITY | Path traversal/file upload abuse rejected. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-SECURITY-006 | P1 | SECURITY | Uploaded file download requires correct tenant/authority. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer friction or support load increases |
| G1-SECURITY-007 | P0 | SECURITY | XSS payload in company/material/process names renders escaped in UI and public outputs. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-008 | P0 | SECURITY | CSRF/state mismatch in OIDC callback fails closed. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-009 | P0 | SECURITY | Open redirect attempt in `next`/return URL is rejected. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-SECURITY-010 | P0 | SECURITY | Rate limit on login/reset/verification resend is effective and user-friendly. | `backend boundary tests + e2e/46-gate1-error-ux.spec.ts` | TODO | Customer blocked/confused or security/compliance trust loss |
| G1-OBSERVE-001 | P1 | OBSERVE | Failed verification send is logged with non-secret correlation ID. | `scripts/qa/run-gate1-onboarding.sh logs` | TODO | Customer friction or support load increases |
| G1-OBSERVE-002 | P1 | OBSERVE | Password reset failure is logged without token/password leakage. | `scripts/qa/run-gate1-onboarding.sh logs` | TODO | Customer friction or support load increases |
| G1-OBSERVE-003 | P1 | OBSERVE | Backend 5xx during onboarding increments/appears in logs/metrics. | `scripts/qa/run-gate1-onboarding.sh logs` | TODO | Customer friction or support load increases |
| G1-OBSERVE-004 | P1 | OBSERVE | Customer support can ask user for a safe request/correlation ID. | `scripts/qa/run-gate1-onboarding.sh logs` | TODO | Customer friction or support load increases |
| G1-OBSERVE-005 | P1 | OBSERVE | Fatal frontend console/page errors are captured during E2E; Gate 1 fails on uncaught errors in onboarding-critical pages. | `scripts/qa/run-gate1-onboarding.sh logs` | TODO | Customer friction or support load increases |
