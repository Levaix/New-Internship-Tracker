#!/usr/bin/env python3
"""Platform connectors. Each returns a list of normalized postings:
   {company, title, location, url, uid, platform}
Supported: greenhouse, lever, ashby, smartrecruiters, workday.
"""
import json, urllib.request, urllib.error

TIMEOUT = 15
UA = "Mozilla/5.0 (internship-tracker)"

def _req(url, method="GET", payload=None):
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", UA)
    data = None
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(payload).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace")) if r.status == 200 else None
    except Exception:
        return None

def greenhouse(company, token):
    j = _req(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false")
    out = []
    if isinstance(j, dict):
        for job in j.get("jobs", []):
            out.append(dict(company=company, title=job.get("title", ""),
                            location=(job.get("location") or {}).get("name", ""),
                            url=job.get("absolute_url", ""),
                            uid=f"gh:{token}:{job.get('id')}", platform="greenhouse"))
    return out

def lever(company, token):
    j = _req(f"https://api.lever.co/v0/postings/{token}?mode=json")
    out = []
    if isinstance(j, list):
        for job in j:
            cat = job.get("categories") or {}
            out.append(dict(company=company, title=job.get("text", ""),
                            location=cat.get("location", "") or "",
                            url=job.get("hostedUrl", ""),
                            uid=f"lv:{token}:{job.get('id')}", platform="lever"))
    return out

def ashby(company, token):
    j = _req(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    out = []
    if isinstance(j, dict):
        for job in j.get("jobs", []):
            out.append(dict(company=company, title=job.get("title", ""),
                            location=job.get("location", "") or "",
                            url=job.get("jobUrl", "") or job.get("applyUrl", ""),
                            uid=f"as:{token}:{job.get('id')}", platform="ashby"))
    return out

def smartrecruiters(company, token):
    out, offset = [], 0
    while True:
        j = _req(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}")
        if not isinstance(j, dict):
            break
        for job in j.get("content", []):
            loc = job.get("location") or {}
            loc_s = ", ".join(x for x in [loc.get("city"), loc.get("country")] if x)
            out.append(dict(company=company, title=job.get("name", ""),
                            location=loc_s,
                            url=f"https://jobs.smartrecruiters.com/{token}/{job.get('id')}",
                            uid=f"sr:{token}:{job.get('id')}", platform="smartrecruiters"))
        offset += 100
        if offset >= j.get("totalFound", 0):
            break
    return out

def workday(company, spec):
    """spec = 'host|tenant|site'. Workday supports server-side search, so we
    query only role-relevant terms (multi-language) and merge — fast + targeted."""
    import time as _t
    host, tenant, site = spec.split("|")
    base = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    terms = ["internship", "intern", "graduate", "summer analyst", "off-cycle",
             "praktikum", "werkstudent", "trainee", "stage", "placement"]
    seen, out = set(), []
    for term in terms:
        offset, total = 0, None
        while offset < 100:                       # cap 5 pages/term
            j = None
            for _ in range(3):
                j = _req(base, method="POST",
                         payload={"limit": 20, "offset": offset, "searchText": term})
                if isinstance(j, dict):
                    break
                _t.sleep(0.6)
            if not isinstance(j, dict):
                break
            if total is None:
                total = j.get("total", 0)
                if total > 500:        # search not filtering for this term -> skip
                    break
            posts = j.get("jobPostings", [])
            if not posts:
                break
            for job in posts:
                path = job.get("externalPath", "")
                uid = f"wd:{tenant}:{path}"
                if uid in seen:
                    continue
                seen.add(uid)
                out.append(dict(company=company, title=job.get("title", ""),
                                location=job.get("locationsText", "") or "",
                                url=f"https://{host}{path}",
                                uid=uid, platform="workday"))
            offset += 20
            if offset >= (total or 0):
                break
    return out

def oracle(company, spec):
    """Oracle Recruiting Cloud (Candidate Experience). spec = 'host|siteNumber'
    e.g. jpmc.fa.oraclecloud.com|CX_1001 . Public REST API, keyword-searchable."""
    import time as _t, urllib.parse as _up
    host, site = spec.split("|")
    base = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    terms = ["internship", "graduate", "apprentice", "off-cycle"]
    seen, out = set(), []
    for term in terms:
        offset = 0
        while offset < 400:                       # cap
            finder = (f"findReqs;siteNumber={site},keyword={_up.quote(term)},"
                      f"limit=100,offset={offset},sortBy=POSTING_DATES_DESC")
            url = (f"{base}?onlyData=true&expand=requisitionList"
                   f"&finder={_up.quote(finder, safe='=;,')}")
            j = None
            for _ in range(3):
                j = _req(url)
                if isinstance(j, dict):
                    break
                _t.sleep(0.6)
            if not isinstance(j, dict) or not j.get("items"):
                break
            top = j["items"][0]
            reqs = top.get("requisitionList", []) or []
            total = top.get("TotalJobsCount", 0)
            if not reqs:
                break
            for r in reqs:
                rid = r.get("Id")
                uid = f"or:{host}:{rid}"
                if uid in seen:
                    continue
                seen.add(uid)
                out.append(dict(company=company, title=r.get("Title", ""),
                                location=r.get("PrimaryLocation", "") or "",
                                url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}",
                                uid=uid, platform="oracle"))
            offset += 100
            if offset >= total:
                break
    return out

def avature(company, spec):
    """Generic Avature portal scraper. spec = base, e.g.
    'carlyle.avature.net/externalcareers'. Avature gives no machine-readable
    location in the listing, so: enumerate listing -> keep role-matching titles
    -> fetch those detail pages for the 'Location:' field. Brittle by nature."""
    import time as _t, re as _re, html as _html, urllib.request as _ur
    role = _re.compile(r"\bintern(ship)?s?\b|\bgraduate|\btrainee|\bpraktik|"
                       r"\bwerkstudent|\bstage\b|\bapprentice|\bplacement|"
                       r"summer (analyst|associate|intern)|off.?cycle|"
                       r"early career|spring (week|insight)", _re.I)
    base = "https://" + spec.rstrip("/")
    def get(url):
        try:
            req=_ur.Request(url, headers={"User-Agent": UA})
            with _ur.urlopen(req, timeout=TIMEOUT) as r:
                return r.read().decode("utf-8","replace")
        except Exception:
            return ""
    # enumerate listing pages
    jobs={}
    for off in range(0, 300, 10):
        h=get(f"{base}/SearchJobs/?jobRecordsPerPage=10&jobOffset={off}")
        arts=_re.findall(r'<article class="article article--result">(.*?)</article>', h, _re.S)
        if not arts:
            break
        for a in arts:
            m=_re.search(r'href="([^"]*JobDetail[^"]*)"[^>]*>\s*(.*?)\s*</a>', a, _re.S)
            if m:
                link=_html.unescape(m.group(1))
                title=_html.unescape(_re.sub(r'<[^>]+>','',m.group(1+1))).strip()
                jobs[link]=title
        _t.sleep(0.1)
    out=[]
    for link, title in jobs.items():
        if not role.search(title):
            continue
        d=get(link)
        loc=""
        mm=_re.search(r'Location:\s*</[^>]+>\s*(.*?)<', d, _re.S) or \
           _re.search(r'Location:\s*([A-Za-z][^<\n]{1,60})', d)
        if mm:
            loc=_html.unescape(_re.sub(r'<[^>]+>',' ',mm.group(1))).strip()
        rid=link.rstrip("/").split("/")[-1]
        out.append(dict(company=company, title=title, location=loc,
                        url=link, uid=f"av:{spec}:{rid}", platform="avature"))
        _t.sleep(0.1)
    return out

DISPATCH = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
            "smartrecruiters": smartrecruiters, "workday": workday,
            "oracle": oracle, "avature": avature}

def fetch(company, platform, token):
    fn = DISPATCH.get(platform)
    if not fn:
        return []
    try:
        return fn(company, token)
    except Exception:
        return []
