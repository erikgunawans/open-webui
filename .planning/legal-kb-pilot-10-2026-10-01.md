# Contract KB pilot — the 10 contracts (2026-10-01)

Picked by Alesha from a read-only Graph inventory of `SCAN PERJANJIAN` (None-Jupe, item-level grant).
Erik: go ahead, Alesha picks, Rully (legal officer) approves or swaps. OCR starts only after Rully replies.

## Inventory facts
- 36 top folders (1994–2026 + "Akan menjadi Outstanding", "KSO WTP PLUIT", "MoU JUP Mitra"), 697 partner folders.
- **Before 2016: 276 of 281 partner folders are EMPTY**; 4 hold a file. Scans exist from 2016 on.
- 2016+: 347 of 387 partner folders have PDFs (595 PDFs; MB p10 0.56 / p50 1.79 / p90 8.75 / max 43.8).
- "MoU JUP Mitra" (19 folders) and "Akan menjadi Outstanding" (1): no PDFs at partner level.
- 2025: 7 partner folders, PDFs sit in 61 subfolders one level deeper (not in this pick).

## The 10 (≈81 MB; all counterparties are companies — nothing to mask)
| # | Folder | Partner folder | File | MB | Why |
|---|---|---|---|---|---|
| 1 | 2013 | JME - PRASTO PROPERTINDO | PKS PT Prasto Propertindo.pdf | 27.4 | oldest scan; very large |
| 2 | 2015 | JAKPRO - JUP | Perpanjangan 23 KSO.pdf | 14.0 | pre-2016; extension |
| 3 | 2016 | PGN - aksara | PJBG Rambutan - Transportasi AAP - PGN 2016.pdf | 6.2 | gas sale/transport (PJBG) |
| 4 | 2017 | Perjanjian tahun 2017 | Perjanjian JUP Telkomsel.pdf | 15.9 | large |
| 5 | 2018 | Petross - JUP - PGN | perjanjian novasi (jual beli gas)-…pdf | 0.7 | three-party novation; small |
| 6 | 2019 | Jakpro | Perjanjian Pinjaman untuk Proyek perparkiran.pdf | 1.1 | loan agreement |
| 7 | KSO WTP PLUIT | OWJJ (Obayashi, WIKA, Jaya Konstruksi, JFE) | PKS AIR BERSIH OWJJ VS KSO WTP PLUIT sign obayashi.pdf | 3.7 | KSO / consortium |
| 8 | 2022 | JUP - TEKNO INTEGRASI SOLUSINDO | JUP - TIS.pdf | 8.4 | large recent |
| 9 | 2024 | JUP - BIOTEK GRAHADUTA | Addendum JUP Biotek.pdf | 1.8 | addendum |
| 10 | 2026 | JUP - JAKTOUR | PKS Induk Jaktour - JUP tentang Penyediaan Lahan (SPKL).pdf | 2.2 | newest; master PKS |

---
## (Same day, unrelated) Website KB upload — 2026-10-01
- Group **Kontributor KB** (`e52ce433-e2f7-4005-a1d9-964e3449ec5c`) created with `jup.kb.submit: true`, Erik only (Erik's choice; the admin role does not imply submit).
- First live approval failed: `KbReviewStore.attach` passed `db=None` to the vendor; fixed `58af67d96`, deployed `ent-os-00063-8dm` (image `4b9a5d3df`; rollback `ent-os-00062-6zl`, before-value `.planning/kb-attach-fix-deploy-before-2026-10-01.json`).
- 47 `.kb.md` from `~/Documents/JUP-KB-Web-2026-10-01/` submitted + approved into **JUP Staff Contributions** (`35b1abaf-7777-4286-88c1-f6c2bdaa16ed`): 47 files confirmed.
- **Not yet read by Asisten JUP:** the model (`xiaomi/mimo-v2.6-pro-ultraspeed`, "Asisten JUP") has only "JUP Strategy KB" attached. Attaching the collection is a separate production write (ADR-0015 §1), waiting on Erik's OK.
