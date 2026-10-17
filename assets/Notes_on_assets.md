# Notes on assets

All screenshots taken 17-10-2026. Sources: **MyNeta** (scraped) and **ECI 2024 results via OpenCity** (downloaded).

| # | File | Why we visited | Conclusion |
|---|---|---|---|
| 01 | `01_myneta_robots.png` | Check what MyNeta lets crawlers fetch | Only print pages blocked (`/*printer=true`, `/*print=true`). Candidate lists allowed. No crawl delay. |
| 02 | `02_adr_terms.png` | MyNeta's "Terms of Use" link opens ADR's terms, so these are MyNeta's rules | Free for **non-commercial research** with citation. No selling, redistributing or editing the data. Email ADR about any publication. |
| 03 | `03_adr_terms_scraping_clause.png` | The clause that covers scraping | "You must not conduct any systematic or automated data collection activities (including … scraping …) … without ADR's express written consent." Need consent before the full scrape. |
| 04 | `04_myneta_disclaimer.png` | Where MyNeta's data comes from | Taken from the ECI affidavit archive and "available in public domain". The data is public, but ADR's site terms (02, 03) still apply. |
| 05 | `05_opencity_robots.png` | Check what OpenCity lets crawlers fetch | `/api/`, `/revision/`, `/dataset/rate/`, `/dataset/*/history` blocked. `Crawl-Delay: 10`. Direct CSV downloads are fine. |
| 06 | `06_opencity_licence.png` | Can we reuse the 2024 results file? | "Other (Public Domain)". Source results.eci.gov.in. Updated 27 Nov 2025. Free to use, cite OpenCity and ECI. |
| 07 | `07_myneta_ls2024.png` | Confirm 2024 data exists and get a row-count check | 543 constituencies, **8,338** candidates, 543 winners. |
| 08 | `08_myneta_ls2019.png` | Same, for 2019 | 543 constituencies, **7,945** candidates, 542 winners. |
| 09 | `09_myneta_ls2014.png` | Same, for 2014 | 543 constituencies, **8,201** candidates, 541 winners. |

## Overall
- **OpenCity / ECI:** fine to use. Obey the 10 s crawl delay, cite the source.
- **MyNeta:** robots.txt allows it, but ADR's terms require written consent for scraping. Scrape only after consent or instructor OK. Until then, test on one page per year.
- **Row counts to match after scraping:** 2014 = 8,201 · 2019 = 7,945 · 2024 = 8,338.
