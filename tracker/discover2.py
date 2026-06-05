#!/usr/bin/env python3
"""Improved auto-discovery: more token variants per firm across Greenhouse,
Lever, Ashby, SmartRecruiters. Prints verified hits as TSV (firm/platform/token/n)."""
import sys, json, re, urllib.request, concurrent.futures as cf
TIMEOUT = 7
SUFFIXES = ("group","capital","partners","management","advisory","securities",
            "asset","investors","investments","international","global","llp",
            "ltd","plc","inc","co","the","and","company")

def _get(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "Mozilla/5.0 (tracker)")
    if data is not None:
        req.add_header("Content-Type", "application/json"); data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8","replace")) if r.status==200 else None
    except Exception:
        return None

def tokens(name):
    n = name.lower().replace("&","and").replace(".","").replace("'","")
    words = re.sub(r"[^a-z0-9 ]+"," ", n).split()
    base = "".join(words)
    core = [w for w in words if w not in SUFFIXES] or words
    cands = [base, "-".join(words), "".join(core), "-".join(core)]
    # only keep "tight" tokens: at least 6 chars OR >=2 core words joined
    out=[]
    for c in cands:
        if c and c not in out and (len(c) >= 6 or len(core) >= 2):
            out.append(c)
    return out

def probe(firm):
    for tok in tokens(firm):
        j=_get(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs?content=false")
        if isinstance(j,dict) and j.get("jobs"): return (firm,"greenhouse",tok,len(j["jobs"]))
        j=_get(f"https://api.lever.co/v0/postings/{tok}?mode=json")
        if isinstance(j,list) and j: return (firm,"lever",tok,len(j))
        j=_get(f"https://api.ashbyhq.com/posting-api/job-board/{tok}")
        if isinstance(j,dict) and j.get("jobs"): return (firm,"ashby",tok,len(j["jobs"]))
        j=_get(f"https://api.smartrecruiters.com/v1/companies/{tok}/postings")
        if isinstance(j,dict) and j.get("content"): return (firm,"smartrecruiters",tok,j.get("totalFound",0))
        j=_get(f"https://apply.workable.com/api/v1/widget/accounts/{tok}?details=true")
        if isinstance(j,dict) and j.get("jobs"): return (firm,"workable",tok,len(j["jobs"]))
        j=_get(f"https://{tok}.pinpointhq.com/postings.json")
        if isinstance(j,dict) and j.get("data"): return (firm,"pinpoint",tok,len(j["data"]))
        j=_get(f"https://{tok}.breezy.hr/json")
        if isinstance(j,list) and j: return (firm,"breezy",tok,len(j))

    return (firm,None,None,0)

if __name__=="__main__":
    firms=[l.strip() for l in open(sys.argv[1],encoding="utf-8") if l.strip()]
    hits=0
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        for firm,plat,tok,n in ex.map(probe, firms):
            if plat: hits+=1; print(f"{firm}\t{plat}\t{tok}\t{n}", flush=True)
    print(f"# {hits}/{len(firms)} mapped", file=sys.stderr)
