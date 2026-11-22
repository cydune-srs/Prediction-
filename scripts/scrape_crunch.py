"""Scrape Crunch club pages listed in the sitemap: address, coordinates, plan prices."""
import json, re, sys, time, csv, urllib.request
OUT = sys.argv[1]  # CSV path; rerunning resumes from rows already saved
UA = {"User-Agent": "Mozilla/5.0 (research; club location list)"}
def get(u):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "replace")
        except Exception as e:
            err = e; time.sleep(2 * (i + 1))
    raise err
sm = get("https://www.crunch.com/sitemap.xml")
urls = sorted({u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if re.match(r"https://www\.crunch\.com/locations/[^/]+$", u)})
print(len(urls), "club urls", flush=True)
cols = ["url","status","name","address","city","state","zip","country","lat","lon","price_range","base","base_no_commit","peak","peak_results","presale"]
import os
done = set()
if os.path.exists(OUT):
    done = {r["url"] for r in csv.DictReader(open(OUT)) if r.get("status") == "ok"}
new = not os.path.exists(OUT)
fh = open(OUT, "a", newline=""); w = csv.DictWriter(fh, cols, extrasaction="ignore")
if new: w.writeheader()
rows = []
for i, u in enumerate(urls):
    if u in done: continue
    try:
        h = get(u)
    except Exception as e:
        w.writerow({"url": u, "status": f"error {e}"}); fh.flush(); continue
    r = {"url": u, "status": "ok"}
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S):
        try: d = json.loads(m.group(1))
        except Exception: continue
        for g in d.get("@graph", [d]):
            if g.get("@type") == "ExerciseGym":
                a = g.get("address", {}); geo = g.get("geo", {})
                r.update(name=g.get("name"), address=a.get("streetAddress"), city=a.get("addressLocality"),
                         state=a.get("addressRegion"), zip=a.get("postalCode"), country=a.get("addressCountry"),
                         lat=geo.get("latitude"), lon=geo.get("longitude"), price_range=g.get("priceRange"))
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
    for label, key in (("Peak Results", "peak_results"), ("Peak", "peak"), ("Base", "base")):
        m = re.search(rf"{label}: \$(\d+\.\d\d) monthly", t)
        if m: r[key] = m.group(1)
    m = re.search(r"Base: \$\d+\.\d\d monthly with annual commitment and \$(\d+\.\d\d) monthly", t)
    if m: r["base_no_commit"] = m.group(1)
    r["presale"] = int(bool(re.search(r"presale|pre-sale|coming soon", t, re.I) and "Flexible Membership Options" not in t))
    w.writerow(r); fh.flush()
    if i % 100 == 0: print(i, r.get("name"), r.get("peak"), flush=True)
    time.sleep(0.25)
fh.close()
print("done", len(urls))
