"""Turn report.json into the dashboard's dataset files (data/*.json), each row carrying an action."""
import json, os, sys

r = json.load(open("report.json"))
WEEK = r["week"]
WEEK_START = sys.argv[1] if len(sys.argv) > 1 else "2026-10-05"
m, g = r["meta"], r["google"]
AVG = m["total"]["roas"]
MIN = r["min_spend"]
os.makedirs("data", exist_ok=True)


def L(x):
    return f"₹{x/100000:.1f}L" if x >= 100000 else f"₹{x/1000:.1f}k"


def dump(name, rows):
    json.dump(rows, open(f"data/{name}.json", "w"), ensure_ascii=False)


# 1 summary
t, gt = m["total"], g["total"]
dump("summary", [dict(week=WEEK, week_start=WEEK_START, meta_spend=t["spend"], meta_reach=t["reach"], meta_cpm=t["cpm"],
                      meta_cpc=t["cpc"], meta_roas=t["roas"], meta_hook=t["hook"], meta_thru=t["thru"], meta_hold=t["hold"],
                      meta_purchases=t["purch"], meta_revenue=t["rev"], google_spend=gt["spend"], google_roas=gt["roas"],
                      google_revenue=gt["rev"], total_spend=round(t["spend"] + gt["spend"]))])

# 2 buckets
acts = {a["bucket"]: a for a in m["actions"]}
dump("meta_buckets", [dict(bucket=b["bucket"], ads=b["ads"], spend=b["spend"], spend_share=b.get("spend_share"),
                           rev_share=b.get("rev_share"), reach=b["reach"], cpm=b["cpm"], cpc=b["cpc"], roas=b["roas"],
                           hook=b["hook"], thru=b["thru"], hold=b["hold"], signal=acts[b["bucket"]]["tone"],
                           action=acts[b["bucket"]]["text"]) for b in m["buckets"]])

# 3 tiers
def tier_action(x):
    if x["roas"] >= AVG: return f"Above {AVG}x — rebook top {x['tier']} creators for new scripts."
    if x["roas"] < AVG * 0.6: return f"{x['roas']}x on {L(x['spend'])}: stop new {x['tier']} bookings until scripts are reworked; keep only ads ≥ {AVG}x."
    return f"Below {AVG}x — keep creators above average, swap the rest."
dump("meta_tiers", [dict(tier=x["tier"], ads=x["ads"], spend=x["spend"], cpm=x["cpm"], cpc=x["cpc"], roas=x["roas"],
                         hook=x["hook"], hold=x["hold"], action=tier_action(x)) for x in m["tiers"]])

# 4 winners & leaks
win = []
for kind, key, act in [
    ("Winning hook", "win_hooks", lambda x: f"Hook rate {x['hook']}% at {x['roas']}x — reuse this opener on 2 new scripts this week."),
    ("Winning script", "win_scripts", lambda x: f"{x['roas']}x on {L(x['spend'])}, hold {x['hold']}% — re-shoot with a new face/format; raise budget 20%."),
    ("Winning design theme", "win_design", lambda x: f"{x['roas']}x on {L(x['spend'])} — make 3 static/GIF variants of this theme for other SKUs."),
    ("Attention leak", "attention_leaks", lambda x: f"Hook {x['hook']}% (well above median) but {x['roas']}x — attention isn't converting: fix offer, CTA or landing page before more spend."),
]:
    for x in m[key]:
        win.append(dict(kind=kind, angle=x["angle"], group=x["group"], ads=x["n"], preview=x.get("preview"), ig=x.get("ig"), manager=x.get("manager"), spend=x["spend"], roas=x["roas"],
                        hook=x["hook"], thru=x["thru"], hold=x["hold"], cpc=x["cpc"], action=act(x)))
for i, w in enumerate(win):
    w["id"] = f"{w['kind'][:4]}-{i}"
dump("winners", win)

# 5 ads (concepts)
def ad_action(c):
    v = c["verdict"]
    return {"Scale": f"Scale: +20% budget; {c['roas']}x vs {AVG}x avg.",
            "Keep": "Keep running; refresh when frequency > 3.",
            "Iterate": "Iterate: keep script, test 2 new hooks.",
            "Pause": f"Pause and move {L(c['spend'])}/wk to Scale ads.",
            "Learning": f"Under {L(MIN)} but above avg — let it reach {L(MIN)}.",
            "Watch": f"Under {L(MIN)} and below avg — cap spend; judge at {L(MIN)}."}[v]
dump("meta_ads", [dict(concept=c["concept"], bucket=c["bucket"], format=c["fmt"], category=c["cat"], angle=c["angle"],
                       ads=c["n"], preview=c.get("preview"), ig=c.get("ig"), manager=c.get("manager"), thumb=c.get("thumb"), spend=c["spend"], reach=c["reach"], cpm=c["cpm"], cpc=c["cpc"], roas=c["roas"],
                       hook=c["hook"], thru=c["thru"], hold=c["hold"], verdict=c["verdict"], action=ad_action(c))
                  for c in m["concepts"]])

# 6 google types
def gtype_action(x):
    T = x["type"]
    if T.startswith("CTV"): return f"{L(x['spend'])} at ~0x is expected for reach buys — judge on reach and brand-search lift, not ROAS. Check if brand search grew; if not, cut 30%."
    if T == "Search": return f"{x['roas']}x — mostly brand/PB terms. Protect budget; don't count it as creative performance."
    if T.startswith("Demand"): return f"{x['roas']}x at ₹{x['cpc']} CPC — strongest creative channel on Google. Move CTV savings here; add Meta winners as DG videos."
    if T.startswith("Performance"): return f"{x['roas']}x — feed it Meta's winning hooks/statics as new asset groups."
    return f"{x['roas']}x — hold; keep feed titles fresh."
dump("google_types", [dict(**x, action=gtype_action(x)) for x in g["types"]])

# 7 google creatives
dg = [x for x in g["creatives"] if x["platform"] == "DG"]
dgavg = sum(x["rev"] for x in dg) / sum(x["spend"] for x in dg)
def gc_action(x):
    if x["platform"] == "CTV": return "Reach asset — compare 6s vs 15s vs 30s on completed views, not ROAS."
    if x["spend"] < MIN: return f"Under {L(MIN)} — too early to call."
    if x["roas"] >= dgavg * 1.2: return f"{x['roas']}x vs {dgavg:.2f}x DG avg — scale and cut a 15s version."
    if x["roas"] < dgavg * 0.5: return f"{x['roas']}x — pause; swap in a Meta winner."
    return "Keep; refresh opener."
dump("google_creatives", [dict(**x, action=gc_action(x)) for x in g["creatives"]])

# 8 history (one row per week x bucket; the Monday run appends)
hist_path = "data/history.json"
hist = json.load(open(hist_path)) if os.path.exists(hist_path) else []
hist = [h for h in hist if h["week_start"] != WEEK_START]
for b in m["buckets"]:
    if b["ads"]:
        hist.append(dict(week_start=WEEK_START, platform="Meta", bucket=b["bucket"], spend=b["spend"], roas=b["roas"], hook=b["hook"]))
hist.append(dict(week_start=WEEK_START, platform="Meta", bucket="All", spend=t["spend"], roas=t["roas"], hook=t["hook"]))
hist.append(dict(week_start=WEEK_START, platform="Google", bucket="All", spend=gt["spend"], roas=gt["roas"], hook=None))
dump("history", hist)
print({f: len(json.load(open('data/' + f))) for f in os.listdir("data")})
