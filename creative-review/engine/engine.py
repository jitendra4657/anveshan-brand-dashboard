"""Weekly creative review engine (Anveshan).
Inputs : meta_raw.ROWS (1d-click spend/reach/purchases/revenue, may repeat names)
         meta_video.VID (default attribution: impressions, link clicks, 3s plays, thruplays; by name)
         google_raw.ROWS / SEARCH
Output : report.json
Rules  : bucket from ad-name convention; winners = spend >= MIN_SPEND and ROAS > account avg.
"""
import json, re, sys, importlib
from collections import defaultdict

MIN_SPEND = 5000
WEEK = sys.argv[1] if len(sys.argv) > 1 else "5–11 Oct 2026"

meta_raw = importlib.import_module("meta_raw")
meta_video = importlib.import_module("meta_video")
google_raw = importlib.import_module("google_raw")

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


# ---- merge Meta ----
ads = {}
for (name, spend, imp, reach, clk, v3, thru, purch, rev) in meta_raw.ROWS:
    a = ads.setdefault(name, dict(spend=0, reach=0, purch=0, rev=0))
    a["spend"] += spend; a["reach"] += reach; a["purch"] += purch; a["rev"] += rev
missing = []
for name, a in ads.items():
    v = meta_video.VID.get(name)
    if v is None:
        missing.append(name); v = (0, 0, 0, 0)
    a["imp"], a["clk"], a["v3"], a["thru"] = v
    a.update(parse(name))


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


def roll(items):
    t = defaultdict(float)
    for a in items:
        for k in ("spend", "reach", "imp", "clk", "purch", "rev", "v3", "thru"):
            t[k] += a[k]
        if a["v3"]:
            t["vimp"] += a["imp"]
    return metrics(t)


# links (optional links.json: [{ad_name, ad_id, ad_preview_shareable_link, instagram_permalink_url, facebook_permalink_url, thumbnail_url}])
import os
LINKS = {}
if os.path.exists("links.json"):
    for x in json.load(open("links.json")):
        LINKS[x["ad_name"]] = x
ACT = "540514437231734"
for name, a in ads.items():
    x = LINKS.get(name, {})
    a["ad_id"] = x.get("ad_id")
    a["preview"] = x.get("ad_preview_shareable_link")
    a["ig"] = x.get("instagram_permalink_url")
    a["thumb"] = x.get("thumbnail_url")
    a["manager"] = f"https://adsmanager.facebook.com/adsmanager/manage/ads?act={ACT}&selected_ad_ids={x['ad_id']}" if x.get("ad_id") else None


def top_links(items):
    best = max(items, key=lambda a: (1 if a.get("ad_id") else 0, a["spend"]))
    return dict(ad_id=best.get("ad_id"), preview=best.get("preview"), ig=best.get("ig"), manager=best.get("manager"), thumb=best.get("thumb"))


all_ads = list(ads.values())
acct = roll(all_ads)
AVG = acct["roas"]


def verdict(m):
    if m["spend"] < MIN_SPEND:
        return "Learning" if (m["roas"] or 0) >= AVG else "Watch"
    r = m["roas"] or 0
    if r >= AVG * 1.2: return "Scale"
    if r >= AVG: return "Keep"
    if r >= AVG * 0.6: return "Iterate"
    return "Pause"


# buckets
ORDER = ["Founder", "Expert", "Paid Partnership", "UGC", "Product Video / Carousel", "Static", "GIF"]
buckets = []
for b in ORDER:
    items = [a for a in all_ads if a["bucket"] == b]
    if not items:
        buckets.append(dict(bucket=b, ads=0, **{k: None for k in metrics(defaultdict(float, spend=0, imp=0, clk=0, reach=0, purch=0, rev=0))}))
        continue
    m = roll(items)
    m["spend_share"] = round(m["spend"] / acct["spend"] * 100, 1)
    m["rev_share"] = round(m["rev"] / acct["rev"] * 100, 1) if acct["rev"] else 0
    buckets.append(dict(bucket=b, ads=len(items), **m))

# partnership tiers
tiers = []
for t in ["Macro", "Micro", "Nano"]:
    items = [a for a in all_ads if a["bucket"] == "Paid Partnership" and a["tier"] == t]
    if items:
        tiers.append(dict(tier=t, ads=len(items), **roll(items)))

# concepts (copies + V1/V2/V3 merged)
concepts = defaultdict(list)
for a in all_ads:
    concepts[a["concept"]].append(a)
crows = []
for c, items in concepts.items():
    a0 = items[0]
    m = roll(items)
    crows.append(dict(concept=c, bucket=a0["bucket"], fmt=a0["fmt"], cat=a0["cat"], product=a0["product"],
                      angle=a0["angle"], creator=a0["creator"], n=len(items), verdict=verdict(m), **top_links(items), **m))
crows.sort(key=lambda r: -r["spend"])

# angle level (hooks / scripts / design themes)
angles = defaultdict(list)
for a in all_ads:
    angles[(a["bucket"] if a["fmt"] in ("Video",) else a["fmt"], a["angle"])].append(a)
arows = []
for (grp, ang), items in angles.items():
    m = roll(items)
    arows.append(dict(group=grp, angle=ang, cat=items[0]["cat"], n=len(items), **top_links(items), **m))

vid = [r for r in arows if r["hook"] is not None and r["group"] not in ("Static",)]
q = lambda r: r["spend"] >= MIN_SPEND and (r["roas"] or 0) > AVG
win_scripts = sorted([r for r in vid if q(r) and r["group"] not in ("GIF",)], key=lambda r: (-r["roas"], -(r["hold"] or 0)))[:8]
win_design = sorted([r for r in arows if r["group"] in ("Static", "GIF", "Carousel") and q(r)], key=lambda r: -r["roas"])[:8]
# high-attention-but-not-converting hooks (spend>=MIN, hook >= 1.3x median, ROAS < avg)
hooks_sorted = sorted([r["hook"] for r in vid if r["spend"] >= MIN_SPEND])
med_hook = hooks_sorted[len(hooks_sorted) // 2] if hooks_sorted else 0
win_hooks = sorted([r for r in vid if q(r) and r["hook"] >= med_hook], key=lambda r: (-r["hook"], -r["roas"]))[:8]
attention_leaks = sorted([r for r in vid if r["spend"] >= MIN_SPEND and r["hook"] >= med_hook * 1.3 and (r["roas"] or 0) < AVG],
                         key=lambda r: -r["spend"])[:6]
pause = sorted([r for r in crows if r["verdict"] == "Pause"], key=lambda r: -r["spend"])
scale = sorted([r for r in crows if r["verdict"] == "Scale"], key=lambda r: -r["roas"])

# category x bucket matrix (spend, roas)
matrix = defaultdict(lambda: defaultdict(float))
for a in all_ads:
    matrix[(a["cat"], a["bucket"])]["spend"] += a["spend"]
    matrix[(a["cat"], a["bucket"])]["rev"] += a["rev"]
mx = [dict(cat=c, bucket=b, spend=round(v["spend"]), roas=round(v["rev"] / v["spend"], 2) if v["spend"] else None)
      for (c, b), v in matrix.items()]


# ---- bucket actions ----
def fmt_inr(x):
    return f"₹{x/100000:.1f}L" if x >= 100000 else f"₹{x/1000:.1f}k"


actions = []
med_hold = sorted([b["hold"] for b in buckets if b.get("hold")])
med_hold = med_hold[len(med_hold) // 2] if med_hold else 0
for b in buckets:
    if not b["ads"]:
        actions.append(dict(bucket=b["bucket"], tone="gap", text=f"No live {b['bucket']} ads last week — brief 3–4 to test against the {AVG}x account ROAS."))
        continue
    r, ss, rs = b["roas"] or 0, b["spend_share"], b["rev_share"]
    if b["spend"] < MIN_SPEND:
        actions.append(dict(bucket=b["bucket"], tone="gap", text=f"Barely live ({fmt_inr(b['spend'])}, {b['ads']} ads) — not enough to judge. Brief 3–4 {b['bucket']} ads and give them {fmt_inr(MIN_SPEND)} each next week."))
        continue
    if r >= AVG * 1.15 and rs > ss:
        t = (f"Earns {rs}% of revenue on {ss}% of spend ({r}x vs {AVG}x). Move 10–15% more budget here and brief 2 new variants of its top concept.", "scale")
    elif r < AVG * 0.6:
        t = (f"{r}x ROAS on {fmt_inr(b['spend'])} — under 60% of account. Cut spend to ads ≥ {AVG}x and pause the rest; re-brief before refunding.", "cut")
    elif b.get("hook") and b.get("hold") and b["hold"] < med_hold * 0.8:
        t = (f"Hooks stop the scroll ({b['hook']}%) but hold is weak ({b['hold']}%). Keep the openers, tighten the middle — shorter edits, product proof by second 5.", "fix")
    elif r < AVG:
        t = (f"{r}x is below the {AVG}x average. Keep only ads above average and test new angles in this bucket.", "fix")
    else:
        t = (f"On par at {r}x. Hold budget; refresh the lowest-ROAS 20% of ads.", "hold")
    actions.append(dict(bucket=b["bucket"], tone=t[1], text=t[0]))

# ---- Google ----
g = defaultdict(lambda: defaultdict(float))
gcre = defaultdict(lambda: defaultdict(float))
for (acc, camp, typ, name, s, imp, clk, val) in google_raw.ROWS:
    g[typ]["spend"] += s; g[typ]["imp"] += imp; g[typ]["clk"] += clk; g[typ]["rev"] += val
    if typ in ("DG", "CTV"):
        k = (typ, name)
        gcre[k]["spend"] += s; gcre[k]["imp"] += imp; gcre[k]["clk"] += clk; gcre[k]["rev"] += val
for (camp, s, imp, clk, val) in google_raw.SEARCH:
    g["Search"]["spend"] += s; g["Search"]["imp"] += imp; g["Search"]["clk"] += clk; g["Search"]["rev"] += val


def gm(v):
    s = v["spend"]
    return dict(spend=round(s), imp=int(v["imp"]), clk=int(v["clk"]), rev=round(v["rev"]),
                cpm=round(s / v["imp"] * 1000, 1) if v["imp"] else None,
                cpc=round(s / v["clk"], 1) if v["clk"] else None,
                ctr=round(v["clk"] / v["imp"] * 100, 2) if v["imp"] else None,
                roas=round(v["rev"] / s, 2) if s else None)


def gbucket(name):
    n = name.lower()
    if "kd" in n: return "Founder"
    if "sec" in n: return "Brand film (CTV)"
    return "Product Video"


gtypes = [dict(type={"DG": "Demand Gen video", "CTV": "CTV / Video reach", "PMax": "Performance Max",
                     "Shopping": "Shopping", "Search": "Search"}[k], **gm(v)) for k, v in g.items()]
gtypes.sort(key=lambda r: -r["spend"])
gcreatives = [dict(platform=k[0], ad=k[1], bucket=gbucket(k[1]), **gm(v)) for k, v in gcre.items()]
gcreatives.sort(key=lambda r: -r["spend"])
gtot = gm({k: sum(v[k] for v in g.values()) for k in ("spend", "imp", "clk", "rev")})

report = dict(
    week=WEEK, generated="Monday auto-run", min_spend=MIN_SPEND,
    meta=dict(account="Anveshan_Acqui", attribution="1-day click", total=acct, buckets=buckets, tiers=tiers,
              concepts=crows, win_hooks=win_hooks, win_scripts=win_scripts, win_design=win_design,
              attention_leaks=attention_leaks, scale=scale[:10], pause=pause[:10], matrix=mx, actions=actions,
              median_hook=med_hook, missing_video_rows=missing),
    google=dict(attribution="Google default (account conversion settings)", total=gtot, types=gtypes, creatives=gcreatives),
)
json.dump(report, open("report.json", "w"), ensure_ascii=False, indent=1)
print("Meta", acct)
print("missing video", missing)
for b in buckets: print(b["bucket"], b["ads"], b.get("spend"), b.get("roas"), b.get("hook"), b.get("hold"))
print("Google", gtot)
for t in gtypes: print(t)
