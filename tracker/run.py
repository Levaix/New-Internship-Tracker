#!/usr/bin/env python3
"""Internship tracker — fetch all mapped firms, filter to target cities +
internship/graduate roles, dedup against seen-store, send Telegram alerts.

New-firm auto-seed: the first time a firm appears (returns data), its current
matching postings are recorded silently (no alert). Only postings that appear
*after* a firm is known trigger alerts — so you can add firms anytime without
a backfill flood."""
import os, sys, csv, json, time, re, urllib.request, urllib.parse
import concurrent.futures as cf
import connectors

ROLE_PATTERNS = [
    r"\bintern(ship)?s?\b", r"\bgraduate", r"\btrainee", r"\bapprentice",
    r"\bpraktik", r"\bwerkstudent", r"\bworking student",
    r"\bstagiaire\b", r"\bstage\b", r"\bvisiting analyst",
    r"\bsummer (analyst|associate|intern)", r"\boff[- ]cycle",
    r"\bspring (week|intern|insight)", r"\binsight (day|week|programme|program)",
    r"\bnew analyst", r"\bfull[- ]time analyst", r"\banalyst programme",
    r"\banalyst program\b", r"\bplacement", r"\bearly career",
]
ROLE_RE = re.compile("|".join(ROLE_PATTERNS), re.I)

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
SEEN_PATH = os.path.join(HERE, "state", "seen.json")
KNOWN_PATH = os.path.join(HERE, "state", "known_companies.json")

def load_registry():
    rows = []
    with open(os.path.join(HERE, "registry.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("company") and r.get("platform") and r.get("token"):
                rows.append(r)
    return rows

def _load(path):
    try: return set(json.load(open(path, encoding="utf-8")))
    except Exception: return set()

def _save(path, s):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(sorted(s), open(path, "w", encoding="utf-8"))

def matches(posting):
    title = (posting["title"] or "").lower()
    loc = (posting["location"] or "").lower()
    cities = [c.lower() for c in CFG["cities"]]
    if not any(c in loc for c in cities):
        if not any(c in title for c in cities):
            return False
    if any(x in title for x in CFG["exclude_keywords"]):
        return False
    return bool(ROLE_RE.search(title))

def telegram(text):
    tok = os.environ.get("TG_BOT_TOKEN") or CFG["telegram"]["bot_token"]
    chat = os.environ.get("TG_CHAT_ID") or CFG["telegram"]["chat_id"]
    data = urllib.parse.urlencode({"chat_id": chat, "text": text,
        "parse_mode": "HTML", "disable_web_page_preview": "false"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                 data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print("telegram error:", e); return False

def main():
    dry = "--dry-run" in sys.argv
    seed = "--seed" in sys.argv
    reg = load_registry()
    seen = _load(SEEN_PATH)
    known = _load(KNOWN_PATH)

    def fetch_one(r): return connectors.fetch(r["company"], r["platform"], r["token"])
    all_posts = []
    with cf.ThreadPoolExecutor(max_workers=40) as ex:
        for posts in ex.map(fetch_one, reg):
            all_posts.extend(posts)

    fetched_companies = {p["company"] for p in all_posts}     # firms that returned data
    new_firms = fetched_companies - known                     # first time we see them
    hits = [p for p in all_posts if matches(p)]

    if seed:
        for p in hits: seen.add(p["uid"])
        _save(SEEN_PATH, seen); _save(KNOWN_PATH, known | fetched_companies)
        print(f"seeded {len(seen)} postings; known firms {len(known | fetched_companies)}")
        return

    to_alert, silently_seeded = [], 0
    for p in hits:
        if p["uid"] in seen:
            continue
        if p["company"] in new_firms:        # brand-new firm -> learn silently
            seen.add(p["uid"]); silently_seeded += 1
        else:                                # known firm -> genuine new posting
            to_alert.append(p)

    print(f"firms={len(reg)} fetched={len(all_posts)} matches={len(hits)} "
          f"new_firms={len(new_firms)} silently_seeded={silently_seeded} to_alert={len(to_alert)}")

    for p in sorted(to_alert, key=lambda x: x["company"]):
        msg = (f"\U0001F4BC <b>{p['company']}</b> posted <b>{p['title']}</b>\n"
               f"\U0001F4CD {p['location'] or 'see listing'}\n\U0001F517 {p['url']}")
        if dry:
            print("WOULD ALERT:", p["company"], "|", p["title"], "|", p["location"])
        else:
            if telegram(msg): seen.add(p["uid"])
            time.sleep(0.4)

    if not dry:
        _save(SEEN_PATH, seen)
        _save(KNOWN_PATH, known | fetched_companies)
    print("done.")

if __name__ == "__main__":
    main()
