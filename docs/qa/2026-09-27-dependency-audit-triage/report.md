# Dependency audit triage — 2026-09-27

Scope: npm audit evidence for AMINRA frontend/mobile workspaces. Raw JSON/stderr kept under `raw/`. No dependency remediation was applied; `npm audit fix --dry-run` was evidence-only.

## Summary

- `frontend-aminra-web`: total=15, critical=0, high=10, moderate=4, low=1
  - dry-run remediation conflict: npm error code ERESOLVE; npm error ERESOLVE could not resolve; npm error   peer eslint@"^6.0.0 || ^7.0.0 || >=8.0.0" from @eslint-community/eslint-utils@4.9.1; npm error peer eslint@">=9.0.0" from eslint-config-next@16.2.1
- `frontend-legacy-removed-web`: total=8, critical=1, high=5, moderate=2, low=0
- `mobile-auditor-app`: total=29, critical=2, high=9, moderate=17, low=1
  - dry-run remediation conflict: npm warn ERESOLVE overriding peer dependency; npm warn ERESOLVE overriding peer dependency; npm warn ERESOLVE overriding peer dependency; npm warn ERESOLVE overriding peer dependency

## Findings

### frontend-aminra-web

- `@babel/core` severity=low, direct=False, via=1123528:@babel/core: Arbitrary File Read via sourceMappingURL Comment, effects=[]
- `@vitest/coverage-v8` severity=moderate, direct=True, via=vitest, effects=['vitest']
- `@vitest/mocker` severity=moderate, direct=False, via=1193684:Vitest: Path Traversal / Arbitrary File Read via @vitest/mocker Redirect Mock, effects=['vitest']
- `@xmldom/xmldom` severity=high, direct=False, via=1158517:xmldom: XML fragment injection via invalid EntityReference.nodeName during requireWellFormed serialization; 1193671:xmldom: HTML raw-text closing-tag case mismatch causes output amplification; 1193687:xmldom PI grammar regex ReDoS: quadratic backtracking on unterminated processing instructions; 1193690:xmldom: Element name injection via createElement() bypasses requireWellFormed, effects=[]
- `axios` severity=high, direct=True, via=1120547:Axios: Regular Expression Denial of Service (ReDoS) via Cookie Name Injection; 1120643:Allocation of Resources Without Limits or Throttling in Axios; 1120645:Axios: Proxy-Authorization Credential Leak to Origin Server Across HTTP-to-HTTPS Redirect in Axios Node.js HTTP Adapter; 1120647:Axios: Proxy-Authorization header leaks to redirect target when proxy is re-evaluated to direct connection, effects=[]
- `baseline-browser-mapping` severity=moderate, direct=False, via=1193686:baseline-browser-mapping process termination on invalid input causes denial of service, effects=[]
- `brace-expansion` severity=high, direct=False, via=1120311:brace-expansion: Large numeric range defeats documented `max` DoS protection; 1123897:brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups; 1123898:brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups; 1130588:brace-expansion: DoS via unbounded expansion length causing an out-of-memory process crash, effects=[]
- `browserslist` severity=high, direct=False, via=1153171:Browserslist: Unbounded memory growth (no cache eviction) via distinct query results, leading to eventual OOM; 1153172:Browserslist: Uncaught crash / prototype write via untrusted browserslist-stats.json custom stats (normalizeStats), effects=[]
- `form-data` severity=high, direct=False, via=1120743:form-data: CRLF injection in form-data via unescaped multipart field names and filenames, effects=[]
- `js-yaml` severity=high, direct=False, via=1121860:JS-YAML: Quadratic-complexity DoS in merge key handling via repeated aliases; 1123911:js-yaml: YAML merge-key chains can force quadratic CPU consumption; 1138115:JS-YAML: Quadratic CPU consumption in !!omap resolution (3.x and 4.x) — CVE-2026-59870 fix not backported; 1193727:js-yaml: maxTotalMergeKeys does not limit CPU use for empty merge sources, effects=[]
- `nanoid` severity=high, direct=False, via=1138811:nanoid: non-secure generators can loop indefinitely with negative size; 1139427:nanoid: custom generators can loop indefinitely when size is zero; 1153189:nanoid: Integer Overflow or Wraparound, effects=[]
- `postcss` severity=high, direct=False, via=1130709:PostCSS: incomplete fix of GHSA-6g55-p6wh-862q — attacker-controlled sourceMappingURL reads arbitrary .map files when `from` is unset; 1139510:PostCSS: Path Traversal in Previous Source Map Auto-Loading (sourceMappingURL) leads to Arbitrary .map File Disclosure, effects=[]
- `undici` severity=high, direct=False, via=1121187:undici vulnerable to TLS certificate validation bypass via dropped requestTls in SOCKS5 ProxyAgent; 1121241:undici vulnerable to HTTP header injection via Set-Cookie percent-decoding; 1121244:undici WebSocket client vulnerable to denial of service via fragment count bypass; 1121247:undici vulnerable to cross-origin request routing via SOCKS5 proxy pool reuse, effects=[]
- `vite` severity=high, direct=False, via=1120786:launch-editor: NTLMv2 hash disclosure via UNC path handling on Windows; 1123527:vite: `server.fs.deny` bypass on Windows alternate paths, effects=[]
- `vitest` severity=moderate, direct=True, via=@vitest/coverage-v8; @vitest/mocker; 1193683:Vitest: Path Traversal / Arbitrary File Read via @vitest/mocker Redirect Mock, effects=['@vitest/coverage-v8']

### frontend-legacy-removed-web

- `axios` severity=high, direct=True, via=1116673:Axios has a NO_PROXY Hostname Normalization Bypass that Leads to SSRF; 1117574:Axios: Authentication Bypass via Prototype Pollution Gadget in `validateStatus` Merge Strategy; 1117576:Axios: Incomplete Fix for CVE-2025-62718 — NO_PROXY Protection Bypassed via RFC 1122 Loopback Subnet (127.0.0.0/8) in Axios 1.15.0; 1117577:Axios: Invisible JSON Response Tampering via Prototype Pollution Gadget in `parseReviver`, effects=[]
- `baseline-browser-mapping` severity=moderate, direct=False, via=1193686:baseline-browser-mapping process termination on invalid input causes denial of service, effects=[]
- `follow-redirects` severity=moderate, direct=False, via=1116560:follow-redirects leaks Custom Authentication Headers to Cross-Domain Redirect Targets, effects=[]
- `form-data` severity=high, direct=False, via=1120743:form-data: CRLF injection in form-data via unescaped multipart field names and filenames, effects=[]
- `nanoid` severity=high, direct=False, via=1138811:nanoid: non-secure generators can loop indefinitely with negative size; 1139427:nanoid: custom generators can loop indefinitely when size is zero; 1153189:nanoid: Integer Overflow or Wraparound, effects=[]
- `next` severity=critical, direct=True, via=1116375:Next.js has a Denial of Service with Server Components; 1117930:Next.js Vulnerable to Denial of Service with Server Components; 1118938:Next.js has a Middleware / Proxy bypass in App Router applications via segment-prefetch routes - Incomplete Fix Follow-Up; 1118941:Next.js's Middleware / Proxy redirects can be cache-poisoned, effects=[]
- `postcss` severity=high, direct=False, via=1117015:PostCSS has XSS via Unescaped </style> in its CSS Stringify Output; 1124252:PostCSS: Arbitrary file read and information disclosure via attacker-controlled sourceMappingURL in CSS comments; 1130709:PostCSS: incomplete fix of GHSA-6g55-p6wh-862q — attacker-controlled sourceMappingURL reads arbitrary .map files when `from` is unset; 1139510:PostCSS: Path Traversal in Previous Source Map Auto-Loading (sourceMappingURL) leads to Arbitrary .map File Disclosure, effects=['next']
- `sharp` severity=high, direct=False, via=1124066:sharp inherited vulnerabilities in libvips: CVE-2026-33327, CVE-2026-33328, CVE-2026-35590, CVE-2026-35591; 1193725:sharp: Vulnerabilities in libheif: GHSA-g89c-p67h-r497 and GHSA-2jg2-4ch7-h545, effects=['next']

### mobile-auditor-app

- `@babel/core` severity=low, direct=False, via=1123528:@babel/core: Arbitrary File Read via sourceMappingURL Comment, effects=[]
- `@expo/cli` severity=moderate, direct=False, via=@expo/config; @expo/config-plugins; @expo/metro-config; @expo/prebuild-config, effects=['expo']
- `@expo/config` severity=moderate, direct=False, via=@expo/config-plugins, effects=['@expo/metro-config', 'expo', 'expo-constants']
- `@expo/config-plugins` severity=moderate, direct=False, via=xcode, effects=['@expo/cli', '@expo/config', '@expo/prebuild-config', 'expo']
- `@expo/metro-config` severity=moderate, direct=False, via=@expo/config; postcss, effects=['@expo/cli', 'expo']
- `@expo/prebuild-config` severity=moderate, direct=False, via=@expo/config; @expo/config-plugins, effects=[]
- `@react-navigation/core` severity=moderate, direct=False, via=query-string, effects=[]
- `@xmldom/xmldom` severity=high, direct=False, via=1158517:xmldom: XML fragment injection via invalid EntityReference.nodeName during requireWellFormed serialization; 1158518:xmldom: XML fragment injection via invalid EntityReference.nodeName during requireWellFormed serialization; 1193671:xmldom: HTML raw-text closing-tag case mismatch causes output amplification; 1193687:xmldom PI grammar regex ReDoS: quadratic backtracking on unterminated processing instructions, effects=[]
- `baseline-browser-mapping` severity=moderate, direct=False, via=1193686:baseline-browser-mapping process termination on invalid input causes denial of service, effects=[]
- `brace-expansion` severity=high, direct=False, via=1120311:brace-expansion: Large numeric range defeats documented `max` DoS protection; 1123896:brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups; 1123897:brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups; 1123898:brace-expansion: DoS via exponential-time expansion of consecutive non-expanding {} groups, effects=[]
- `browserslist` severity=high, direct=False, via=1153171:Browserslist: Unbounded memory growth (no cache eviction) via distinct query results, leading to eventual OOM; 1153172:Browserslist: Uncaught crash / prototype write via untrusted browserslist-stats.json custom stats (normalizeStats), effects=[]
- `decode-uri-component` severity=moderate, direct=False, via=1147955:decode-uri-component: Denial of service via exponential decoding of malformed percent-encoded input, effects=['query-string']
- `expo` severity=moderate, direct=True, via=@expo/cli; @expo/config; @expo/config-plugins; @expo/metro-config, effects=[]
- `expo-asset` severity=moderate, direct=False, via=expo-constants, effects=['expo']
- `expo-constants` severity=moderate, direct=True, via=@expo/config, effects=['expo', 'expo-asset', 'expo-linking', 'expo-notifications', 'expo-router']
- `expo-linking` severity=moderate, direct=True, via=expo-constants, effects=[]
- `expo-notifications` severity=moderate, direct=True, via=expo-constants, effects=[]
- `expo-router` severity=moderate, direct=True, via=expo-constants; expo-linking; query-string, effects=[]
- `image-size` severity=high, direct=False, via=1239765:image-size: JXL and HEIF parsers allow denial of service through infinite loops; 1239766:image-size: ICNS parser allows denial of service through an infinite loop, effects=[]
- `js-yaml` severity=high, direct=False, via=1121859:JS-YAML: Quadratic-complexity DoS in merge key handling via repeated aliases; 1121860:JS-YAML: Quadratic-complexity DoS in merge key handling via repeated aliases; 1123911:js-yaml: YAML merge-key chains can force quadratic CPU consumption; 1123912:js-yaml: YAML merge-key chains can force quadratic CPU consumption, effects=[]
- `nanoid` severity=high, direct=False, via=1138811:nanoid: non-secure generators can loop indefinitely with negative size; 1139427:nanoid: custom generators can loop indefinitely when size is zero; 1153189:nanoid: Integer Overflow or Wraparound, effects=[]
- `postcss` severity=high, direct=False, via=1117015:PostCSS has XSS via Unescaped </style> in its CSS Stringify Output; 1124252:PostCSS: Arbitrary file read and information disclosure via attacker-controlled sourceMappingURL in CSS comments; 1130709:PostCSS: incomplete fix of GHSA-6g55-p6wh-862q — attacker-controlled sourceMappingURL reads arbitrary .map files when `from` is unset; 1139510:PostCSS: Path Traversal in Previous Source Map Auto-Loading (sourceMappingURL) leads to Arbitrary .map File Disclosure, effects=['@expo/metro-config']
- `query-string` severity=moderate, direct=False, via=decode-uri-component, effects=['@react-navigation/core', 'expo-router']
- `shell-quote` severity=critical, direct=False, via=1120422:shell-quote quote() does not escape newlines in object .op values; 1123944:shell-quote: Quadratic-complexity Denial of Service in `parse()` (CWE-407), effects=[]
- `tar` severity=critical, direct=False, via=1120782:node-tar applies PAX size override to intermediary GNU long-name/long-link headers, causing tar parser interpretation differential (file smuggling); 1123939:node-tar: Process crash via PAX numeric path type confusion; 1123940:node-tar: Decompression/parse DoS via unlimited input; 1123941:node-tar: Negative tar entry size causes infinite loop in archive replace, effects=[]
- `undici` severity=high, direct=False, via=1121242:undici vulnerable to HTTP header injection via Set-Cookie percent-decoding; 1121245:undici WebSocket client vulnerable to denial of service via fragment count bypass; 1121255:undici vulnerable to Set-Cookie SameSite attribute downgrade via permissive substring matching; 1130716:undici vulnerable to downstream response desynchronization via retry interceptor, effects=[]
- `uuid` severity=moderate, direct=False, via=1119441:uuid: Missing buffer bounds check in v3/v5/v6 when buf is provided, effects=['xcode']
- `ws` severity=high, direct=False, via=1119108:ws: Uninitialized memory disclosure; 1123259:ws: Memory exhaustion DoS from tiny fragments and data chunks; 1123260:ws: Memory exhaustion DoS from tiny fragments and data chunks; 1123261:ws: Memory exhaustion DoS from tiny fragments and data chunks, effects=[]
- `xcode` severity=moderate, direct=False, via=uuid, effects=['@expo/config-plugins']

## Verdict

P1: direct high/critical findings exist and require a controlled remediation branch before unsupervised pilot if the affected workspace serves public traffic.
- frontend-aminra-web: axios (high)
- frontend-legacy-removed-web: axios (high)
- frontend-legacy-removed-web: next (critical)

Dry-run remediation is not clean. Do not run forceful audit-fix in this branch; resolve peer graph deliberately.

## Next action

If remediation is needed, create a dedicated dependency branch; do not run `npm audit fix --force` in this feature branch. Re-run install, lint, build, tests, and browser smoke after lockfile changes.
