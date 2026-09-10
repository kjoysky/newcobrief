# Pipeline — how to run it

Four steps, each its own script, all in this folder:

| Step | Script | What it does | Needs Claude? |
|---|---|---|---|
| 1 | fetch.py | Pulls the last 7 days of new Colorado entities from data.colorado.gov into data/raw/ | No |
| 2 | filter.py | Drops non-launch cities, holding/property names, and registered-agent addresses. Writes data/filtered/ plus a "-dropped" file with the reason for each drop | No |
| 3 | classify.py | Sends each surviving name to Claude for an inferred industry and a one-line note. Caches results in data/classified.json | Yes |
| 4 | build_sample.py | Writes one Markdown page per city into data/sample/ for weekly review | No |
| 5 | build_site.py | Generates the public website into docs/ (landing page + ten city pages), following 04-Design-Decisions.pdf | No |

run.py runs all five in order.

To preview the site, open docs/index.html in a browser. GitHub Pages will serve the docs/ folder once the repo is pushed.

## One-time setup

**1. Get an API key (about two minutes)**

1. Go to https://console.anthropic.com and sign in (or create an account) with colorcrayonart@gmail.com.
2. If asked, add a payment method under Settings, then Billing. Put $10 on it; a full week of classification costs a few dollars.
3. Click "API Keys" in the left sidebar, then the "Create Key" button.
4. Name it `business-brief`, click Create, then click Copy. It starts with `sk-ant-`. You will only see it once.

**2. Save the key where the scripts look for it**

In Terminal, paste this, replacing the part after the equals sign with your key:

```
echo 'ANTHROPIC_API_KEY=sk-ant-PASTE-YOUR-KEY-HERE' > ~/Desktop/"Business Brief Project"/pipeline/.env
```

The .env file is ignored by git and never leaves this Mac.

**3. Activate the Python environment** (already created by Claude; do this once per Terminal window)

```
cd ~/Desktop/"Business Brief Project" && source .venv/bin/activate
```

## Nightly, automatically

GitHub Actions runs the whole pipeline every night at about 4 AM Denver time (`.github/workflows/nightly.yml`), commits the new `data/classified.json` and `docs/`, and GitHub Pages redeploys newcobrief.com. The API key lives in the repo's Actions secrets as `ANTHROPIC_API_KEY`, never in the code. To run it by hand: GitHub repo, Actions tab, "Nightly refresh", "Run workflow".

Because the robot commits to main every night, always pull before running anything locally:

```
cd ~/Desktop/"Business Brief Project" && git pull
```

## Running it by hand on the Mac

```
cd ~/Desktop/"Business Brief Project" && git pull && source .venv/bin/activate && python pipeline/run.py
```

Then open data/sample/00-summary.md and the city page you want to review. Flag anything wrong and tell Claude; the fix goes into filter.py or the prompt in classify.py.

To test cheaply first, classify one batch only:

```
python pipeline/classify.py --limit 40
```

## Settings

Everything adjustable is in config.py: launch cities, the industry list, days back, batch size, model, effort.
