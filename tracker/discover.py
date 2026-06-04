#!/usr/bin/env python3
"""Probe known ATS platforms to find each firm's careers feed.
Outputs verified {firm -> platform, token} rows. Greenhouse / Lever / Ashby /
SmartRecruiters are auto-discoverable via predictable public JSON endpoints.
Workday / Avature / custom sites are mapped manually in registry.csv.
"""
import sys, json, re, urllib.request, urllib.error, concurrent.futures as cf

TIMEOUT = 7

def _get(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "Mozilla/5.0 (tracker)")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None

def tokens(name):
    n = name.lower()
    n = n.replace("&", "and")
    base = re.sub(r"[^a-z0-9]+", "", n)            # janestreet
    hyph = re.sub(r"[^a-z0-9]+", "-", n).strip("-") # jane-street
    # strip common suffixes
    stripped = re.sub(r"(group|capital|partners|management|advisory|securities|"
                      r"co|llp|ltd|inc|and|the)$", "", base)
    cands = []
    for t in (base, hyph, stripped):
        if t and t not in cands:
            cands.append(t)
    return cands

def probe(firm):
    for tok in tokens(firm):
        # Greenhouse
        j = _get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs?content=false")
        if isinstance(j, dict) and j.get("jobs"):
            return (firm, "greenhouse", tok, len(j["jobs"]))
        # Lever
        j = _get(f"https://api.lever.co/v0/postings/{tok}?mode=json")
        if isinstance(j, list) and len(j) > 0:
            return (firm, "lever", tok, len(j))
        # Ashby
        j = _get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
        if isinstance(j, dict) and j.get("jobs"):
            return (firm, "ashby", tok, len(j["jobs"]))
        # SmartRecruiters
        j = _get(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings")
        if isinstance(j, dict) and j.get("content"):
            return (firm, "smartrecruiters", tok, j.get("totalFound", len(j["content"])))
    return (firm, None, None, 0)

if __name__ == "__main__":
    firms = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    hits = []
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        for firm, plat, tok, n in ex.map(probe, firms):
            if plat:
                hits.append((firm, plat, tok, n))
                print(f"HIT\t{firm}\t{plat}\t{tok}\t{n}", flush=True)
    print(f"\n{len(hits)}/{len(firms)} firms auto-mapped", file=sys.stderr)
