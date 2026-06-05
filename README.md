# Internship Tracker

Monitors finance internship & graduate openings across **747 firms** (UK + EU
finance: IB, S&T, quant/trading, PE/HF, asset & wealth management, consulting,
insurance, accounting) and sends a **Telegram alert** the moment a new role
opens in one of your target cities:

> 💼 **Blackstone** posted **2026 Private Equity Off-Cycle Internship Frankfurt**
> 📍 Frankfurt · 🔗 link

## How it works

1. `tracker/registry.csv` maps each firm to its hiring platform (Greenhouse,
   Lever, Ashby, SmartRecruiters, Workday) and the token/tenant to query.
2. `tracker/run.py` fetches every firm's live postings, keeps only those that
   (a) sit in a **target city** and (b) match an **internship / graduate** role
   pattern, deduplicates against `tracker/state/seen.json`, and alerts on new ones.
3. A scheduler (GitHub Actions, every 30 min) runs it 24/7.

## Configure (no code changes needed)

Edit **`tracker/config.json`**:
- `cities` — target locations (currently London, Frankfurt, Düsseldorf, Cologne,
  Munich, Hamburg, Berlin, Zurich, Geneva, Luxembourg).
- `role_keywords` / `exclude_keywords` — what counts as a relevant role.
- `telegram` — bot token + chat id (better: set as env vars / GitHub secrets).

Add firms in **`tracker/registry.csv`** — one line each:
`Company,platform,token`. For Workday use `Company,workday,host|tenant|site`.

## Run locally

```bash
cd tracker
python3 run.py --dry-run   # show matches, send nothing
python3 run.py --seed      # mark all current openings as seen (no alerts)
python3 run.py             # send alerts for NEW openings only
```

## Deploy 24/7 (free, GitHub Actions)

1. Create a **private GitHub repo** and push this folder.
2. Repo → Settings → Secrets and variables → Actions → add:
   - `TG_BOT_TOKEN` = your bot token
   - `TG_CHAT_ID`   = your chat id
3. The workflow in `.github/workflows/tracker.yml` runs every 30 min and commits
   the updated `seen.json` back so state persists between runs.
4. (Optional) Remove the `telegram` block from `config.json` before pushing, so
   the token lives only in secrets.

Alternatively run on a €3.49/mo VPS via cron: `*/30 * * * * cd /path/tracker && python3 run.py`.

## Coverage status

- **208 firms live** across 11 connectors: Greenhouse, Lever, Ashby, SmartRecruiters, Workday,
  Oracle Recruiting Cloud, Eightfold, Workable, Breezy, Pinpoint, and **tal.net (Lumesse) Atom feed**.
- Covers the bulge bracket with an open feed (JPM, Citi, Morgan Stanley, Deutsche Bank, Barclays,
  HSBC, Jefferies, plus **Lazard, BNP Paribas, Bank of America** via tal.net once their cycles open),
  the full PE/HF/asset-management tier, all major trading shops, consulting, insurance, accounting,
  and a fintech/payments cluster.
- **tal.net firms (Lazard/BNP/BofA)** are wired via the campus Atom feed; those feeds are empty
  between recruiting cycles (e.g. summer) and populate when 2027 programs open — auto-seed handles it.
- **Still out of reach:** Goldman Sachs (active anti-bot — not circumvented by design); Nomura
  (SuccessFactors) and UBS (custom Avature) would each need a dedicated reverse-engineering pass.
- New-firm auto-seed: adding a firm to registry.csv never floods you.
