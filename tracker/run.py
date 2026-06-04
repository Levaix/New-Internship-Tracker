#!/usr/bin/env python3
"""Internship tracker — fetch all mapped firms, filter to target cities +
internship/graduate roles, dedup against seen-store, send Telegram alerts."""
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

def load_registry():
    rows = []
    with open(os.path.join(HERE, "registry.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("company") and r.get("platform") and r.get("token"):
                rows.append(r)
    return rows

def load_seen():
    try:
        return set(json.load(open(SEEN_PATH, encoding="utf-8")))
    except Exception:
        return set()

def save_seen(seen):
    os.makedirs(os.path.dirname(SEEN_PATH), exist_ok=True)
    json.dump(sorted(seen), open(SEEN_PATH, "w", encoding="utf-8"))

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
    seen = load_seen()
    def fetch_one(r): return connectors.fetch(r["company"], r["platform"], r["token"])
    all_posts = []
    with cf.ThreadPoolExecutor(max_workers=40) as ex:
        for posts in ex.map(fetch_one, reg):
            all_posts.extend(posts)
    hits = [p for p in all_posts if matches(p)]
    new = [p for p in hits if p["uid"] not in seen]
    print(f"firms={len(reg)} fetched={len(all_posts)} city+role matches={len(hits)} new={len(new)}")
    if seed:
        for p in hits: seen.add(p["uid"])
        save_seen(seen)
        print(f"seeded {len(seen)} postings as already-seen (no alerts sent)")
        return
    for p in sorted(new, key=lambda x: x["company"]):
        msg = (f"\U0001F4BC <b>{p['company']}</b> posted <b>{p['title']}</b>\n"
               f"\U0001F4CD {p['location'] or 'see listing'}\n\U0001F517 {p['url']}")
        if dry:
            print("WOULD ALERT:", p["company"], "|", p["title"], "|", p["location"])
        else:
            if telegram(msg): seen.add(p["uid"])
            time.sleep(0.4)
    if not dry: save_seen(seen)
    print("done.")

if __name__ == "__main__":
    main()
