"""Monthly (month-on-month) Meta creative review engine (Anveshan). Classification rules are shared with the weekly engine.
Original weekly header:
Inputs : meta_raw.ROWS (1d-click spend/reach/purchases/revenue, may repeat names)
         meta_video.VID (default attribution: impressions, link clicks, 3s plays, thruplays; by name)
         google_raw.ROWS / SEARCH
Output : report.json
Rules  : bucket from ad-name convention; winners = spend >= MIN_SPEND and ROAS > account avg.
"""
import json, re, sys, importlib
from collections import defaultdict

MIN_SPEND = 5000


FOUNDERS = {"kd", "aayushi"}
EXPERTS = {"poornima"}
CATS = {"oil", "ghee", "atta", "superfood", "combo"}
SKIP = {"video", "viddeo", "re", "cara", "image", "gif", "founder", "partnership", "ad",
        "macro", "micro", "nano", "ugc", "l", "mix"} | FOUNDERS | EXPERTS | CATS
DATE_RE = re.compile(r"^\d{1,3}[A-Za-z]+\d{2,4}$")
SIZE_RE = re.compile(r"^\d+(\.\d+)?L$", re.I)
VER_RE = re.compile(r"^V\d$", re.I)


def clean(name):
    return re.sub(r"\s*–\s*Copy(\s*\d+)?$", "", name).strip()


def parse(name):
    n = clean(name)
    toks = n.split("_")
    low = [t.lower() for t in toks]
    fmt0 = low[0]
    d = {"name": name, "concept": None}
    # format
    if fmt0 == "partnership":
        fmt = "Video"
    elif fmt0 == "cara":
        fmt = "Carousel"
    elif fmt0 == "image":
        fmt = "Static"
    elif fmt0 == "gif":
        fmt = "GIF"
    else:
        fmt = "Video"
    # bucket
    tier = creator = None
    if fmt0 == "partnership":
        bucket = "Paid Partnership"
        tier = toks[2] if len(toks) > 2 and low[2] in {"macro", "micro", "nano"} else "Other"
        rest = toks[3:]
        creator = rest[0] if rest and rest[0].lower() not in CATS else "Unnamed"
    elif "ugc" in low:
        bucket = "UGC"
        creator = next((t for t in toks[2:] if t.lower() not in SKIP), "UGC")
    elif fmt == "Video" and (FOUNDERS & set(low)):
        bucket = "Founder"
        creator = "KD" if "kd" in low else "Aayushi"
    elif fmt == "Video" and (EXPERTS & set(low)):
        bucket = "Expert"
        creator = "Poornima"
    elif fmt in ("Video", "Carousel"):
        bucket = "Product Video / Carousel"
    elif fmt == "Static":
        bucket = "Static"
    else:
        bucket = "GIF"
    # category + product
    cat = next((t.capitalize() for t in low if t in CATS), "Other")
    ci = next((i for i, t in enumerate(low) if t in CATS), None)
    product = toks[ci + 1] if ci is not None and ci + 1 < len(toks) and not DATE_RE.match(toks[ci + 1]) else ""
    PRODUCTS = {"gno", "bmo", "ymo", "sfo", "vco", "bsme", "hpa", "khapli", "multigrain", "girdolchi",
                "halikardolchi", "halikar", "dolchi", "buffalo", "buffalodolchi", "olive", "oliveoil", "almond",
                "coconut", "cocountoil", "blacksesame", "honey", "gir", "desicowdolchi2.5l", "ghee+oil", "bmo+ymo"}
    if SIZE_RE.match(product) or product.lower() in SKIP or product.lower() not in PRODUCTS:
        product = ""
    # angle = CamelCase phrase tokens after product, not size/date/version
    cand = []
    for i, t in enumerate(toks):
        if ci is not None and i <= ci + (1 if product else 0):
            continue
        if DATE_RE.match(t) or SIZE_RE.match(t) or VER_RE.match(t) or t.lower() in SKIP:
            continue
        if creator and t == creator:
            continue
        cand.append(t)
    angle = cand[-1] if cand else ""
    if bucket == "Paid Partnership":
        angle = f"{creator} ({tier})"
    if not angle:
        angle = f"{cat} {product}".strip() + " (untitled)"
    # concept: strip copies + versions
    concept = "_".join(t for t in clean(name).split("_") if not VER_RE.match(t))
    d.update(fmt=fmt, bucket=bucket, tier=tier, creator=creator, cat=cat, product=product,
             angle=angle, concept=concept, expert_partner=bool(creator and creator.lower().startswith("dr")))
    return d



def metrics(x):
    s, imp = x["spend"], x["imp"]
    vid = x.get("vimp", imp)
    return dict(
        spend=round(s, 2), reach=int(x["reach"]), imp=int(imp), clk=int(x["clk"]),
        purch=int(x["purch"]), rev=round(x["rev"], 2),
        cpm=round(s / imp * 1000, 1) if imp else None,
        cpc=round(s / x["clk"], 1) if x["clk"] else None,
        ctr=round(x["clk"] / imp * 100, 2) if imp else None,
        roas=round(x["rev"] / s, 2) if s else None,
        hook=round(x["v3"] / vid * 100, 1) if x.get("v3") and vid else None,
        thru=round(x["thru"] / vid * 100, 1) if x.get("v3") and vid else None,
        hold=round(x["thru"] / x["v3"] * 100, 1) if x.get("v3") else None,
    )

# ================= Month-on-month engine (Meta only) =================
# Inputs (same folder): m_1dc.json  -> Windsor {result:[{year_month, ad_name, spend, reach, actions_omni_purchase, action_values_omni_purchase}]}  (1-day click)
#                       m_vid.json  -> Windsor {result:[{year_month, ad_name, impressions, link_clicks, actions_video_view, video_thruplay_watched_actions_video_view}]} (default attribution)
#                       links.json  -> [{ad_name, ad_id, ad_preview_shareable_link, instagram_permalink_url}]
# Args: month labels are derived from year_month ("2026|9" -> "2026-09"). argv[1] = last data date (YYYY-MM-DD) to flag a partial month.
# Output: data/*.json for the dashboard.
import os, calendar, datetime
from collections import defaultdict

LAST_DATE = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today() - datetime.timedelta(days=1)
ACT = "540514437231734"
MIN_SPEND = 5000


def ym(s):
    y, m = s.split("|")
    return f"{int(y):04d}-{int(m):02d}"


def mlabel(k):
    y, m = map(int, k.split("-"))
    lab = calendar.month_abbr[m] + " " + str(y)
    if (y, m) == (LAST_DATE.year, LAST_DATE.month) and LAST_DATE.day < calendar.monthrange(y, m)[1]:
        lab += f" (1–{LAST_DATE.day}, MTD)"
    return lab


def days_in(k):
    y, m = map(int, k.split("-"))
    if (y, m) == (LAST_DATE.year, LAST_DATE.month):
        return LAST_DATE.day
    return calendar.monthrange(y, m)[1]


A = defaultdict(lambda: defaultdict(float))  # (month, name) -> metrics
for r in json.load(open("m_1dc.json"))["result"]:
    a = A[(ym(r["year_month"]), r["ad_name"])]
    a["spend"] += r.get("spend") or 0; a["reach"] += r.get("reach") or 0
    a["purch"] += r.get("actions_omni_purchase") or 0; a["rev"] += r.get("action_values_omni_purchase") or 0
for r in json.load(open("m_vid.json"))["result"]:
    a = A[(ym(r["year_month"]), r["ad_name"])]
    a["imp"] += r.get("impressions") or 0; a["clk"] += r.get("link_clicks") or 0
    a["v3"] += r.get("actions_video_view") or 0; a["thru"] += r.get("video_thruplay_watched_actions_video_view") or 0
LINKS = {x["ad_name"]: x for x in json.load(open("links.json"))} if os.path.exists("links.json") else {}

MONTHS = sorted({k[0] for k in A})
LATEST, PREV = MONTHS[-1], (MONTHS[-2] if len(MONTHS) > 1 else None)
PARSED = {}
rows = []
for (mo, name), a in A.items():
    if name not in PARSED:
        PARSED[name] = parse(name)
    d = dict(a); d.update(PARSED[name]); d["month"] = mo
    for k in ("spend", "reach", "purch", "rev", "imp", "clk", "v3", "thru"):
        d.setdefault(k, 0.0)
    rows.append(d)


def link_of(names_spend):
    best = max(names_spend, key=lambda t: (1 if t[0] in LINKS else 0, t[1]))[0]
    x = LINKS.get(best, {})
    aid = x.get("ad_id")
    return dict(preview=x.get("ad_preview_shareable_link"), ig=x.get("instagram_permalink_url"),
                manager=f"https://adsmanager.facebook.com/adsmanager/manage/ads?act={ACT}&selected_ad_ids={aid}" if aid else None)


def roll_m(items):
    t = defaultdict(float)
    for a in items:
        for k in ("spend", "reach", "imp", "clk", "purch", "rev", "v3", "thru"):
            t[k] += a[k]
        if a["v3"]:
            t["vimp"] += a["imp"]
    return metrics(t)


def pct(a, b):
    return round((a - b) / b * 100, 1) if (a is not None and b not in (None, 0)) else None


L = lambda x: (f"₹{x/100000:.1f}L" if x >= 100000 else f"₹{x/1000:.1f}k")

# ---- month totals ----
summary = []
AVG = {}
for mo in MONTHS:
    m = roll_m([r for r in rows if r["month"] == mo])
    AVG[mo] = m["roas"]
    summary.append(dict(month=mo, label=mlabel(mo), days=days_in(mo), spend_per_day=round(m["spend"] / days_in(mo)),
                        ads=len({r["name"] for r in rows if r["month"] == mo and r["spend"] > 0}), **m))
for i, s in enumerate(summary):
    p = summary[i - 1] if i else None
    for k in ("spend_per_day", "roas", "cpm", "cpc", "hook", "thru", "hold"):
        s[k + "_mom"] = pct(s[k], p[k]) if p else None

# ---- month x bucket ----
ORDER = ["Founder", "Expert", "Paid Partnership", "UGC", "Product Video / Carousel", "Static", "GIF"]
mb = []
for mo in MONTHS:
    tot = next(s for s in summary if s["month"] == mo)
    for b in ORDER:
        items = [r for r in rows if r["month"] == mo and r["bucket"] == b]
        if not items:
            continue
        m = roll_m(items)
        mb.append(dict(key=f"{mo}|{b}", month=mo, label=mlabel(mo), bucket=b, ads=len({r["name"] for r in items}),
                       spend_share=round(m["spend"] / tot["spend"] * 100, 1), rev_share=round(m["rev"] / tot["rev"] * 100, 1) if tot["rev"] else None,
                       vs_avg=round(m["roas"] / AVG[mo], 2) if m["roas"] is not None and AVG[mo] else None, **m))


def bucket_action(b):
    cur = next((x for x in mb if x["month"] == LATEST and x["bucket"] == b), None)
    prv = next((x for x in mb if x["month"] == PREV and x["bucket"] == b), None) if PREV else None
    hist = [x for x in mb if x["bucket"] == b]
    if not cur or cur["spend"] < MIN_SPEND:
        return ("gap", f"Barely live this month ({L(cur['spend']) if cur else '₹0'}). Brief 3–4 {b} ads with ₹5k each to get a read.")
    r, a = cur["roas"] or 0, AVG[LATEST]
    trend = pct(cur["roas"], prv["roas"]) if prv else None
    share_trend = (cur["spend_share"] - prv["spend_share"]) if prv else 0
    above_months = sum(1 for x in hist if x["vs_avg"] and x["vs_avg"] >= 1)
    if r >= a * 1.15 and above_months >= 2:
        msg = f"Above average in {above_months}/{len(hist)} months ({r}x vs {a}x now) — a proven type. Raise its share from {cur['spend_share']}% toward {min(60, round(cur['spend_share']*1.25))}% and keep 2 fresh concepts a week coming."
        return ("scale", msg)
    if r < a * 0.6:
        return ("cut", f"{r}x vs {a}x average on {L(cur['spend'])} this month{f' (ROAS {trend:+}% MoM)' if trend is not None else ''}. Cap at its above-average ads and re-brief the format.")
    if trend is not None and trend <= -20:
        return ("fix", f"ROAS fell {trend}% MoM to {r}x while spend share moved {share_trend:+.1f} pts. Likely fatigue: refresh the top 3 concepts' hooks before adding budget.")
    if r < a:
        if trend is not None and trend >= 15:
            return ("fix", f"Improving ({trend:+}% MoM) but still below average at {r}x vs {a}x. Keep budget flat; move spend inside the type to its above-average ads only.")
        return ("fix", f"{r}x vs {a}x average on {L(cur['spend'])}. Keep only above-average ads and test 2 new angles; no extra budget until it clears {a}x.")
    if trend is not None and trend >= 20:
        return ("scale", f"ROAS up {trend}% MoM to {r}x (above the {a}x average). Add 10% budget and clone the month's top concept.")
    return ("hold", f"Steady at {r}x vs {a}x average. Hold budget; replace the lowest-ROAS 20% of ads.")


bucket_actions = []
for b in ORDER:
    t, msg = bucket_action(b)
    bucket_actions.append(dict(bucket=b, signal=t, action=msg))
act_map = {x["bucket"]: x for x in bucket_actions}
for x in mb:
    x["action"] = act_map[x["bucket"]]["action"] if x["month"] == LATEST else ""
    x["signal"] = act_map[x["bucket"]]["signal"] if x["month"] == LATEST else ""

# ---- tiers per month ----
tiers = []
for mo in MONTHS:
    for t in ["Macro", "Micro", "Nano"]:
        items = [r for r in rows if r["month"] == mo and r["bucket"] == "Paid Partnership" and r["tier"] == t]
        if items:
            m = roll_m(items)
            tiers.append(dict(key=f"{mo}|{t}", month=mo, label=mlabel(mo), tier=t, ads=len({r["name"] for r in items}), **m))

# ---- winners per month (angle level) ----
winners = []
angle_hist = defaultdict(dict)
for mo in MONTHS:
    groups = defaultdict(list)
    for r in rows:
        if r["month"] == mo:
            groups[(r["bucket"] if r["fmt"] == "Video" else r["fmt"], r["angle"])].append(r)
    ar = []
    for (grp, ang), items in groups.items():
        m = roll_m(items)
        ar.append(dict(group=grp, angle=ang, n=len({i["name"] for i in items}), **link_of([(i["name"], i["spend"]) for i in items]), **m))
        angle_hist[(grp, ang)][mo] = m
    vid = [x for x in ar if x["hook"] is not None and x["group"] != "Static"]
    hooks = sorted([x["hook"] for x in vid if x["spend"] >= MIN_SPEND])
    med = hooks[len(hooks) // 2] if hooks else 0
    q = lambda x: x["spend"] >= MIN_SPEND and (x["roas"] or 0) > AVG[mo]
    sets = [
        ("Winning hook", sorted([x for x in vid if q(x) and x["hook"] >= med], key=lambda x: (-x["hook"], -x["roas"]))[:6],
         lambda x: f"Hook {x['hook']}% at {x['roas']}x — reuse this opener on 2 new scripts."),
        ("Winning script", sorted([x for x in vid if q(x) and x["group"] != "GIF"], key=lambda x: -x["roas"])[:6],
         lambda x: f"{x['roas']}x on {L(x['spend'])}, hold {x['hold']}% — re-shoot with a new face or format."),
        ("Winning design theme", sorted([x for x in ar if x["group"] in ("Static", "GIF", "Carousel") and q(x)], key=lambda x: -x["roas"])[:6],
         lambda x: f"{x['roas']}x on {L(x['spend'])} — make 3 variants for other SKUs."),
        ("Attention leak", sorted([x for x in vid if x["spend"] >= MIN_SPEND and x["hook"] >= med * 1.3 and (x["roas"] or 0) < AVG[mo]], key=lambda x: -x["spend"])[:5],
         lambda x: f"Hook {x['hook']}% but {x['roas']}x — fix offer, CTA or landing page before more spend."),
    ]
    for kind, lst, act in sets:
        for x in lst:
            winners.append(dict(key=f"{mo}|{kind}|{x['group']}|{x['angle']}", month=mo, label=mlabel(mo), kind=kind, angle=x["angle"], group=x["group"], ads=x["n"],
                                preview=x["preview"], ig=x["ig"], manager=x["manager"], spend=x["spend"], roas=x["roas"], hook=x["hook"],
                                thru=x["thru"], hold=x["hold"], cpc=x["cpc"], action=act(x)))

# consistent winners: above-average ROAS with >= MIN_SPEND in 2+ months
consistent = []
for (grp, ang), byM in angle_hist.items():
    good = [mo for mo, m in byM.items() if m["spend"] >= MIN_SPEND and (m["roas"] or 0) > AVG[mo]]
    if len(good) >= 2:
        tot_sp = sum(m["spend"] for m in byM.values()); tot_rev = sum(m["rev"] for m in byM.values())
        last = byM.get(LATEST)
        consistent.append(dict(key=f"all|Consistent winner|{grp}|{ang}", month="all", label=f"{len(good)} of {len(MONTHS)} months", kind="Consistent winner",
                               angle=ang, group=grp, ads=None, spend=round(tot_sp, 2), roas=round(tot_rev / tot_sp, 2) if tot_sp else None,
                               hook=last["hook"] if last else None, thru=last["thru"] if last else None, hold=last["hold"] if last else None,
                               cpc=last["cpc"] if last else None,
                               action=(f"Beat the average in {', '.join(mlabel(m).split(' (')[0] for m in sorted(good))}. Evergreen angle — keep it live and brief a new execution each month."
                                       if last and last["spend"] >= MIN_SPEND else
                                       f"Beat the average in {', '.join(mlabel(m).split(' (')[0] for m in sorted(good))} but {'barely' if last else 'not'} running in {mlabel(LATEST)}. Relaunch a fresh cut of it.")))
consistent.sort(key=lambda x: -x["spend"])
for c in consistent:
    names = [(r["name"], r["spend"]) for r in rows if (r["bucket"] if r["fmt"] == "Video" else r["fmt"], r["angle"]) == (c["group"], c["angle"])]
    c.update(link_of(names))
winners = consistent[:12] + winners

# ---- concepts with month columns ----
cons = defaultdict(list)
for r in rows:
    cons[r["concept"]].append(r)
concepts = []
for c, items in cons.items():
    total = roll_m(items)
    if total["spend"] < 2000:
        continue
    a0 = items[0]
    d = dict(concept=c, bucket=a0["bucket"], category=a0["cat"], angle=a0["angle"], months_live=len({i["month"] for i in items if i["spend"] > 0}),
             total_spend=total["spend"], total_roas=total["roas"], **link_of([(i["name"], i["spend"]) for i in items]))
    per = {}
    for mo in MONTHS:
        mi = [i for i in items if i["month"] == mo]
        per[mo] = roll_m(mi) if mi else None
        k = mo.replace("-", "_")
        d[f"spend_{k}"] = per[mo]["spend"] if per[mo] else None
        d[f"roas_{k}"] = per[mo]["roas"] if per[mo] else None
    cur, prv = per[LATEST], per.get(PREV) if PREV else None
    d["hook_latest"] = cur["hook"] if cur else None
    d["hold_latest"] = cur["hold"] if cur else None
    a_now = AVG[LATEST]
    if cur and cur["spend"] > 0 and not any(per[m] and per[m]["spend"] > 0 for m in MONTHS[:-1]):
        st, act = "New", (f"New this month: {cur['roas']}x on {L(cur['spend'])}. " + ("Ahead of average — scale +20%." if (cur["roas"] or 0) >= a_now and cur["spend"] >= MIN_SPEND else f"Judge at {L(MIN_SPEND)} spend."))
    elif not cur or cur["spend"] < 500:
        best_m = max((m for m in MONTHS if per[m]), key=lambda m: per[m]["roas"] or 0)
        good = (per[best_m]["roas"] or 0) >= AVG[best_m] and per[best_m]["spend"] >= MIN_SPEND
        st, act = ("Paused winner", f"Hit {per[best_m]['roas']}x in {mlabel(best_m).split(' (')[0]} but is off now. Relaunch with a fresh hook.") if good else ("Off", "Not running; no action.")
    elif prv and prv["spend"] >= MIN_SPEND and cur["spend"] >= MIN_SPEND and prv["roas"] and cur["roas"] is not None and cur["roas"] < prv["roas"] * 0.7:
        st, act = "Fatiguing", f"ROAS down {pct(cur['roas'], prv['roas'])}% MoM ({prv['roas']}x → {cur['roas']}x). Refresh the opener or swap the creator; cut budget 30% meanwhile."
    elif cur["spend"] >= MIN_SPEND and (cur["roas"] or 0) >= a_now * 1.2:
        st, act = "Scale", f"{cur['roas']}x vs {a_now}x average this month. Add 20% budget; brief 2 variants."
    elif cur["spend"] >= MIN_SPEND and (cur["roas"] or 0) < a_now * 0.6:
        st, act = "Pause", f"{cur['roas']}x on {L(cur['spend'])} this month. Pause and move the budget to Scale concepts."
    elif cur["spend"] >= MIN_SPEND and (cur["roas"] or 0) >= a_now:
        st, act = "Keep", "Above average. Keep running; refresh when frequency passes 3."
    elif cur["spend"] >= MIN_SPEND:
        st, act = "Iterate", "Below average. Keep the script, test 2 new hooks."
    else:
        st, act = "Watch", f"Under {L(MIN_SPEND)} this month. Judge once it reaches {L(MIN_SPEND)}."
    d["status"], d["action"] = st, act
    concepts.append(d)
concepts.sort(key=lambda x: -(x.get(f"spend_{LATEST.replace('-', '_')}") or 0) - x["total_spend"] / 1000)

meta = dict(months=[dict(key=m, label=mlabel(m), col=m.replace("-", "_")) for m in MONTHS], latest=LATEST, prev=PREV, last_date=str(LAST_DATE),
            min_spend=MIN_SPEND, account="Anveshan_Acqui", attribution="1-day click")
os.makedirs("data", exist_ok=True)
for name, obj in [("m_summary", summary), ("m_buckets", mb), ("m_tiers", tiers), ("m_winners", winners), ("m_concepts", concepts), ("m_meta", [meta])]:
    json.dump(obj, open(f"data/{name}.json", "w"), ensure_ascii=False)
print({s["label"]: (s["spend"], s["roas"], s["hook"], s["hold"]) for s in summary})
print("concepts", len(concepts), "winners", len(winners), "consistent", len(consistent))
for x in bucket_actions: print(x)
