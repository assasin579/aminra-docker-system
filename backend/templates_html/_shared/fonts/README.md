# Inter font (Latin Extended + Vietnamese)

Inter is bundled locally to ensure deterministic PDF rendering — no Google Fonts CDN dependency
inside the container's network policy.

## Download

Run from repo root:

```bash
bash scripts/download_inter_font.sh
```

This places 4 weights into this folder:

```
Inter-Regular.woff2     # 400
Inter-Medium.woff2      # 500
Inter-SemiBold.woff2    # 600
Inter-Bold.woff2        # 700
```

Total bundle ~200KB. Subset includes Latin + Latin-Extended + Vietnamese (covers `đ`, `ơ`, `ư` and tone marks).

## License

Inter is licensed under the SIL Open Font License v1.1 — free for commercial use including PDF embedding.
See https://github.com/rsms/inter/blob/master/LICENSE.txt

## Why subset

Full Inter family is ~14MB. We subset to cover only Vietnamese + Latin glyphs needed for AMINRA documents,
reducing both PDF size and license attribution surface.

## Update

When upgrading Inter version, run the download script and commit the new woff2 files.
Visual regression tests will flag any rendering shift.
