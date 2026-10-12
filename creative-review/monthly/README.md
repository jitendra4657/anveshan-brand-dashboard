# Monthly creative review — Meta only (Anveshan)

Month-on-month version of the weekly creative review, for Meta (Anveshan_Acqui, 1-day click). Refreshed on the 2nd of each month by a Claude scheduled task.

Live dashboard: https://claude.ai/artifact/Xq7QzyHyf1BDYerSzs2Lau (private until shared)

## Folders
- `engine/monthly_engine.py` — same ad-name classification as the weekly engine; builds per-month totals, creative-type and tier splits, monthly and consistent winners, and per-concept month columns with a status and action
- `raw/` — Windsor.ai pulls: `m_1dc.json` (spend, reach, purchases, revenue, 1-day click), `m_vid.json` (impressions, link clicks, 3-sec plays, ThruPlays, default attribution), `links.json` (ad IDs and preview links)
- `data/` — the 6 dashboard data files
- `dashboard/index.html` — the dashboard page (runs inside the Claude Dashboard artifact; blank if opened on GitHub Pages)

## Run
```
cd raw
python3 ../engine/monthly_engine.py 2026-10-12   # last date of data; flags a part month as MTD
# writes raw/data/m_*.json
```

## What it adds over the weekly view
- Spend per day, so a part month compares fairly with full months
- ROAS by creative type over time and spend mix by month
- Consistent winners: hooks/scripts/themes above the account average in 2+ months
- Concept status: New, Scale, Keep, Iterate, Fatiguing (ROAS down 30%+ MoM), Pause, Paused winner, Watch, Off

This folder is public: it includes real spend, revenue and ROAS per ad.
