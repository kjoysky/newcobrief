# Pipeline — how to run it

Four steps, each its own script, all in this folder:

| Step | Script | What it does | Needs Claude? |
|---|---|---|---|
| 1 | fetch.py | Pulls the last 7 days of new Colorado entities from data.colorado.gov into data/raw/ | No |
| 2 | filter.py | Drops non-launch cities, holding/property names, and registered-agent addresses. Writes data/filtered/ plus a "-dropped" file with the reason for each drop | No |
| 3 | classify.py | Sends each surviving name to Claude for an inferred industry and a one-line note. Caches results in data/classified.json | Yes |
| 4 | build_sample.py | Writes one Markdown page per city into data/sample/ for weekly review | No |
| 5 | build_site.py | Generates the public website into docs/ (landing page + ten city pages), following 04-Design-Decisions.pdf | No |

| 6 | build_email.py | Builds the Monday email for each city into data/email/ (open a .html there to preview). Same data as the city pages, one column, tables and inline styles so Gmail and Outlook agree. Long weeks show the first entries in full and the rest as one-liners, to stay under Gmail's 102 KB clip | No |
| 7 | send_email.py | Pushes the emails to Buttondown, one per city, to subscribers tagged with that city. Creates DRAFTS unless run with `--send` | No (needs the Buttondown key) |
| 8 | first_issue.py | Nightly. Sends this week's issue, with a welcome block on top, to anyone who subscribed since the last run, so they don't wait for Monday. Tags them `first-issue`, sends one real email per city to "city tag AND first-issue", and strips the tag on the next run (Buttondown's draft-preview send would stamp [PREVIEW] on the subject, so it is a real send). Skips Mondays. Records who got it in data/first-issue.json. `--dry-run` lists, `--to you@x.com` sends a test to one address | No (needs the Buttondown key) |

run.py runs steps 1 to 6 in order. The nightly workflow then runs step 8. Step 7 runs on Mondays (see below).

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

## Buttondown key (one time)

1. Sign in at https://buttondown.com with kjoysky31@gmail.com. Click **API** in the left sidebar, then **Create API key** (or copy the key shown). 
2. Add it to the .env file on this Mac, one line under the Anthropic key:

```
echo 'BUTTONDOWN_API_KEY=PASTE-YOUR-KEY-HERE' >> ~/Desktop/"Business Brief Project"/pipeline/.env
```

3. Add the same key to GitHub: repo, Settings, Secrets and variables, Actions, **New repository secret**, name `BUTTONDOWN_API_KEY`.

## Monday email, automatically

`.github/workflows/monday-email.yml` runs every Monday at about 7 AM Denver time: fetch, filter, classify anything new, build the ten emails, push them to Buttondown as **drafts**. Open https://buttondown.com/emails, read one, click Send. When the drafts have looked right for a few weeks, set the repo variable `AUTO_SEND` to `true` (repo, Settings, Secrets and variables, Actions, Variables tab) and the workflow sends them itself.

To run it by hand: GitHub repo, Actions tab, "Monday email", "Run workflow". Tick "Send immediately" only if you mean it. Locally:

```
cd ~/Desktop/"Business Brief Project" && git pull && source .venv/bin/activate && python pipeline/send_email.py
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

- `SHARED_ADDRESS_MIN` (config.py): a street shared by this many filings in one week is treated as a registered-agent or virtual-office mailbox and dropped. The agent-address rule also compares streets without suite numbers now.
- `FULL_PER_INDUSTRY` and `LEAD_INDUSTRY` (build_site.py): public city pages show one trade in full (construction and trades, up to 3 entries) and every other trade as a count. The Monday email carries everything.
- `AUTHOR`, `CONTACT_EMAIL`, `PRICE_LINE` (build_site.py): the About page, the contact links, and the "Paid plans from $49/mo" line.
- `SAMPLE_CITY` / `SAMPLE_FULL` (build_email.py): the public sample issue at /sample/ is the Denver email cut to the first 6 entries; run.py builds it after the site.
