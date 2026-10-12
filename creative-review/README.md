# Creative review — Meta + Google (Anveshan)

Weekly creative performance report, cut by creative type, refreshed every Monday 9:20 AM IST by a Claude scheduled task.

Live dashboard: https://claude.ai/artifact/BXG4hsqFbcDbFrHWizH5C2 (private until shared)

## Folders
- `engine/engine.py` — classifies ads from their names and computes metrics, winners and verdicts → `report.json`
- `engine/export.py` — turns `report.json` into the dashboard's data files (`data/*.json`) and appends `data/history.json`
- `raw/` — the Windsor.ai pulls for the week (Meta Acqui 1-day click, Meta default-attribution video/clicks, ad links, Google Ads)
- `data/` — the 8 dashboard data files for the latest week
- `dashboard/index.html` — the dashboard page. It runs inside the Claude Dashboard artifact, so it shows blank if opened directly on GitHub Pages; use the live dashboard link above.

## Run
```
cd raw   # needs meta_raw.py, meta_video.py, google_raw.py, links.json
PYTHONPATH=. python3 ../engine/engine.py "5–11 Oct 2026"
mkdir -p data && cp ../data/history.json data/   # so the new week is appended to history
python3 ../engine/export.py 2026-10-05            # writes raw/data/*.json
```

## Creative types (from ad names)
| Type | Rule |
|---|---|
| Founder | Video ads with KD or Aayushi |
| Expert | Video ads with Poornima |
| Paid Partnership | `Partnership_Ad_Macro/Micro/Nano_…` (Dr-named creators stay here) |
| UGC | names containing UGC |
| Product Video / Carousel | other `Video_` and `Cara_` ads |
| Static | `Image_` |
| GIF | `Gif_` |

The hook/angle is the CamelCase phrase in the name (e.g. `IsYourOilTruelyColdPressed`).

## Metrics
- 1-day ROAS = purchase value (1-day click) ÷ spend
- Hook rate = 3-sec plays ÷ impressions · Thru-play rate = ThruPlays ÷ impressions · Hold rate = ThruPlays ÷ 3-sec plays (Meta default attribution — video plays are wrong under 1-day click)
- CPC = spend ÷ link clicks · CPM = spend ÷ impressions × 1000
- Winner = spend ≥ ₹5k and ROAS above account average (hooks also need above-median hook rate)
- Verdicts: Scale ≥ 1.2× avg ROAS · Keep ≥ avg · Iterate ≥ 0.6× avg · Pause below (at ≥ ₹5k spend)
- Google ROAS uses Google's default attribution; not comparable 1:1 with Meta 1-day click.

## Note
This folder is public: `data/` and `raw/` include real spend, revenue and ROAS per ad.
