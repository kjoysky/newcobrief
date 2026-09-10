"""Step 5. Generate the static website into docs/ (GitHub Pages serves that folder).

Follows 04-Design-Decisions.pdf: white page, one green hue, the state's record inside a tinted
field, everything we wrote outside it, Newsreader + Archivo, three figures on every city page.
Usage:
    python3 pipeline/build_site.py
"""
import html
import json
from collections import defaultdict
from datetime import date

from config import (CLASSIFIED_FILE, ENTITY_TYPE_LABELS, FILTERED_DIR, INDUSTRIES, LAUNCH_CITIES,
                    PROJECT_DIR, RAW_DIR, STATE_RECORD_URL, worth_reading)

SITE_DIR = PROJECT_DIR / "docs"
SITE_NAME = "NewCo Brief"
STRAPLINE = "New businesses. Earlier opportunities."
DESCRIPTION = ("NewCo Brief finds newly formed businesses, filters out the noise, and gives commercial "
               "professionals an earlier look at companies entering their market.")
THIN_WEEK = 20
CONF_ORDER = {"high": 0, "medium": 1, "low": 2}

FONTS = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@87.5,400..700;125,400..700"
         "&family=Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400&display=swap")

CSS = """
:root{--page:#FFFFFF;--ink:#16241D;--ink-2:#4A5A52;--ink-3:#7B8A82;--rule:#D5DDD6;--n-05:#F4F5F3;--n-10:#EAECE8;
--field:#E3EDE4;--field-line:#B7CCBB;--accent:#17754C;--accent-deep:#0E4E33;--stamp:#A33526;--stamp-05:#F7EEEC;
--serif:"Newsreader",Georgia,"Times New Roman",serif;--sans:"Archivo","Helvetica Neue",Arial,sans-serif;}
*{box-sizing:border-box}
html{color-scheme:light}
body{margin:0;background:var(--page);color:var(--ink);font-family:var(--serif);font-size:17px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration:none;text-underline-offset:.15em}a:hover{color:var(--accent-deep);text-decoration:underline}
.wrap{max-width:660px;margin:0 auto;padding:0 20px}
.sans{font-family:var(--sans);font-stretch:87.5%}
.masthead{padding:28px 0 0}
.wordmark{font-family:var(--sans);font-stretch:125%;letter-spacing:-.03em;font-size:26px;line-height:1;color:var(--ink);text-decoration:none}
.wordmark b{font-weight:700}.wordmark span{font-weight:400}
.wordmark:hover{text-decoration:none;color:var(--ink)}
.masthead-rule{border:0;border-top:2px solid var(--ink);margin:14px 0 8px}
.strap{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:13px;letter-spacing:.02em;color:var(--ink-2);margin:0}
nav.cities{font-family:var(--sans);font-stretch:87.5%;font-size:13px;font-weight:550;margin:18px 0 0;display:flex;flex-wrap:wrap;gap:6px 16px}
nav.cities a{color:var(--ink-2)}nav.cities a[aria-current]{color:var(--accent)}
.edition{background:var(--n-05);margin:28px -20px 0;padding:26px 20px 22px;border-bottom:3px solid var(--accent)}
.kicker{font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);margin:0 0 6px}
h1{font-family:var(--serif);font-weight:600;letter-spacing:-.02em;font-size:44px;line-height:1.05;margin:0}
.dateline{font-style:italic;font-weight:400;font-size:18px;color:var(--ink-2);margin:8px 0 0}
.figures{display:flex;gap:34px;margin:22px 0 0;flex-wrap:wrap}
.figures div{display:flex;flex-direction:column}
.figures b{font-family:var(--serif);font-weight:600;letter-spacing:-.02em;font-size:34px;line-height:1;color:var(--ink)}
.figures b.kept{color:var(--accent)}
.figures span{font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);margin-top:6px}
.notice{background:var(--stamp-05);padding:14px 18px;margin:26px 0 0;font-size:16px;color:var(--ink-2)}
section.industry{margin:44px 0 0}
section.industry>.kicker{color:var(--accent);border-bottom:1px solid var(--rule);padding-bottom:8px;margin-bottom:0}
article.entry{padding:26px 0;border-bottom:1px solid var(--rule)}
.entry h2{font-family:var(--serif);font-weight:500;letter-spacing:-.02em;font-size:24px;line-height:1.15;margin:0 0 12px}
.record{background:var(--field);border-left:2px solid var(--field-line);padding:10px 14px;font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:13.5px;line-height:1.5;color:var(--ink);font-variant-numeric:tabular-nums;display:flex;flex-wrap:wrap;gap:4px 18px}
.record span{white-space:nowrap}.record small{color:var(--ink-3);font-size:11px;letter-spacing:.06em;text-transform:uppercase;margin-right:5px}.record span{text-transform:none}
.inferred{margin:14px 0 0;font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:14px;color:var(--accent);display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.flag{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--stamp);font-weight:600;border:1px solid var(--stamp);padding:2px 6px 1px;line-height:1.3}
.entry p.note{font-size:18.5px;line-height:1.62;max-width:27em;margin:10px 0 0;color:var(--ink)}
.source{margin:12px 0 0;font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:12.5px;color:var(--ink-3)}
.source a{color:var(--accent)}
section.uninferable{margin:44px 0 0}
section.uninferable .lede{font-style:italic;color:var(--ink-2);margin:6px 0 0}
.plain{list-style:none;padding:0;margin:14px 0 0}
.plain li{padding:9px 0;border-bottom:1px solid var(--rule);font-size:16.5px;display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 14px}
.plain li .meta{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:12.5px;color:var(--ink-3);font-variant-numeric:tabular-nums;white-space:nowrap}
footer{margin:64px 0 40px;padding-top:16px;border-top:1px solid var(--rule);font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:12.5px;color:var(--ink-2);line-height:1.6}
footer p{margin:0 0 8px}
/* landing */
.hero{margin:44px 0 0}
.hero h1{font-size:40px;text-wrap:balance}
.hero .lede{font-size:21px;line-height:1.5;color:var(--ink-2);max-width:27em;margin:16px 0 0}
.hero .cta{display:inline-block;margin:18px 0 0;font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:14px;letter-spacing:.01em}
.transform{margin:40px 0 0;max-width:640px}
.transform .raw{background:var(--field);border-left:2px solid var(--field-line);padding:12px 14px;font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:13px;line-height:1.5;color:var(--ink)}
.transform .raw span{white-space:nowrap}
.transform .join{display:flex;align-items:center;gap:12px;margin-left:26px}
.transform .join .arm{width:2px;height:30px;background:var(--ink)}
.transform .join .kicker{margin:0}
.transform .entry{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.landing>h2{font-family:var(--serif);font-weight:600;letter-spacing:-.02em;font-size:28px;margin:52px 0 10px}
.landing>p{max-width:27em;font-size:18px;line-height:1.6}
.landing ul.cities-list{padding:0;margin:14px 0 0;list-style:none;columns:2;max-width:480px;font-size:17px}
.landing ul.cities-list li{padding:4px 0}
.signup{margin:40px 0 0;border-top:2px solid var(--ink);padding-top:20px;max-width:520px}
.signup label{display:block;font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);margin:14px 0 6px}
.signup input,.signup select{width:100%;font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:16px;padding:10px 12px;border:1px solid var(--field-line);background:var(--page);color:var(--ink);border-radius:0}
.signup button{margin-top:16px;font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:15px;letter-spacing:.02em;padding:12px 20px;background:var(--accent);color:#fff;border:0;cursor:pointer;border-radius:0}
.signup button:hover{background:var(--accent-deep)}
.signup .fine{font-family:var(--sans);font-stretch:87.5%;font-size:12.5px;color:var(--ink-3);margin:10px 0 0}
@media (max-width:600px){body{font-size:16px}h1{font-size:34px}.hero h1{font-size:32px}.figures{gap:22px}.figures b{font-size:28px}.entry h2{font-size:21px}.entry p.note{font-size:17px}.landing ul.cities-list{columns:1}}
"""


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


KEEP_UPPER = {"LLC", "L.L.C.", "INC", "INC.", "PC", "P.C.", "LLP", "LLLP", "LP", "CO", "CO.", "PLLC", "DBA", "USA", "US", "HVAC", "CPA", "MD", "DDS", "RN", "IT", "AI", "CBD", "ATV", "RV", "LTD", "LTD."}


SUFFIX_UPPER = {"LLC", "L.L.C.", "PLLC", "LLP", "LLLP", "LP", "PC", "P.C.", "LTD", "LTD."}


def display_name(name: str) -> str:
    """Names filed in ALL CAPS are shown in title case; mixed-case names are left as filed,
    except that entity suffixes are always shown the standard way (llc -> LLC, inc -> Inc)."""
    if name != name.upper():
        return " ".join(w.upper() if w.upper() in SUFFIX_UPPER else (w.capitalize() if w.upper() in ("INC", "INC.", "CORP", "CORP.", "CO", "CO.") else w) for w in name.split())
    words = []
    for w in name.split():
        if w.upper() in KEEP_UPPER or (len(w) <= 3 and w.isalpha() and w not in ("THE", "AND", "OF")):
            words.append(w.upper())
        else:
            words.append(w.capitalize())
    return " ".join(words)


def slug(city: str) -> str:
    return city.lower().replace(" ", "-")


def fmt_date(s: str) -> str:
    y, m, d = s[:10].split("-")
    return date(int(y), int(m), int(d)).strftime("%B %-d, %Y")


def short_date(s: str) -> str:
    y, m, d = s[:10].split("-")
    return date(int(y), int(m), int(d)).strftime("%b %-d")


def page(title: str, body: str, root: str, current: str = "", desc: str = DESCRIPTION) -> str:
    nav = ""
    for c in LAUNCH_CITIES:
        current_attr = ' aria-current="page"' if c == current else ""
        nav += f'<a href="{root}{slug(c)}/"{current_attr}>{esc(c)}</a>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}"><link rel="stylesheet" href="{root}style.css"></head>
<body><div class="wrap">
<header class="masthead"><a class="wordmark" href="{root}"><b>NewCo</b> <span>Brief</span></a>
<hr class="masthead-rule"><p class="strap">{esc(STRAPLINE)}</p>
<nav class="cities" aria-label="Cities">{nav}</nav></header>
{body}
<footer><p>{esc(DESCRIPTION)}</p>
<p>Business records are published by the Colorado Secretary of State and are in the public domain. Industry and commentary are inferred from the business name by NewCo Brief and are labeled as inferred. City and ZIP only; no street addresses, owner names, or phone numbers are published. Entries are shown for 90 days. No export.</p>
<p>&copy; {date.today().year} NewCo Brief</p></footer>
</div></body></html>"""


def type_label(r: dict) -> str:
    return ENTITY_TYPE_LABELS.get(r.get("entitytype", ""), r.get("entitytype", ""))


def record_field(r: dict) -> str:
    """The state's record, four fields on one row. The name is the headline above, so it is not repeated."""
    return (f'<div class="record"><span><small>City</small>{esc((r.get("principalcity") or "").title())} {esc(r.get("principalzipcode", ""))}</span>'
            f'<span><small>Type</small>{esc(type_label(r))}</span>'
            f'<span><small>Formed</small>{esc(short_date(r["entityformdate"]))}, {esc(r["entityformdate"][:4])}</span>'
            f'<span><small>ID</small>{esc(r["entityid"])}</span></div>')


def source_line(r: dict) -> str:
    return (f'<p class="source"><a href="{esc(STATE_RECORD_URL.format(entityid=r["entityid"]))}" rel="noopener">'
            f'Colorado Secretary of State record {esc(r["entityid"])}</a></p>')


def entry(r: dict, c: dict, city: str) -> str:
    trade = esc(c["industry"]) + (f': {esc(c["detail"])}' if c.get("detail") else "")
    note = f'<p class="note">{esc(c["note"])}</p>' if c.get("note") else ""
    return (f'<article class="entry"><h2>{esc(display_name(r["entityname"]))}</h2>{record_field(r)}'
            f'<div class="inferred"><span>{trade}</span><span class="flag">Inferred from the name</span></div>'
            f'{note}{source_line(r)}</article>')


def city_page(city: str, crows: list, filed: int, cache: dict, root: str) -> str:
    groups, unknown = defaultdict(list), []
    for r in crows:
        c = cache.get(r["entityid"])
        if not c or not c["operating"]:
            continue
        (groups[c["industry"]] if worth_reading(c) else unknown).append((r, c))
    kept = sum(len(v) for v in groups.values())
    cut = filed - kept   # the plain list below counts as cut; it is shown so nothing real is hidden
    dates = sorted(r["entityformdate"][:10] for r in crows) or [date.today().isoformat()]
    body = [f'<div class="edition"><p class="kicker">This week in</p><h1>{esc(city)}</h1>'
            f'<p class="dateline">New businesses formed {fmt_date(dates[0])} to {fmt_date(dates[-1])}</p>'
            f'<div class="figures"><div><b>{filed}</b><span>Filed</span></div><div><b>{cut}</b><span>Cut</span></div>'
            f'<div><b class="kept">{kept}</b><span>Worth reading</span></div></div></div>']
    if kept < THIN_WEEK:
        body.append(f'<p class="notice">A thin week in {esc(city)}. The state recorded {filed} new entities here; after removing holding companies, registered-agent addresses, and names that reveal nothing, {kept} were worth a broker\'s time. We would rather show a short list than pad it.</p>')
    for ind in INDUSTRIES:
        entries = groups.get(ind)
        if not entries:
            continue
        body.append(f'<section class="industry"><p class="kicker">{esc(ind)} · {len(entries)}</p>')
        for r, c in sorted(entries, key=lambda rc: (CONF_ORDER[rc[1]["confidence"]], rc[0]["entityname"].lower())):
            body.append(entry(r, c, city))
        body.append('</section>')
    if unknown:
        body.append(f'<section class="uninferable"><p class="kicker">Trade not inferable from the name · {len(unknown)}</p>'
                    f'<p class="lede">Real filings whose names say little or nothing about the business. Listed so nothing real is quietly dropped.</p><ul class="plain">')
        for r, _ in sorted(unknown, key=lambda rc: rc[0]["entityname"].lower()):
            body.append(f'<li><span>{esc(display_name(r["entityname"]))}</span>'
                        f'<span class="meta">{esc((r.get("principalcity") or "").title())} {esc(r.get("principalzipcode", ""))} · {esc(type_label(r))} · {esc(short_date(r["entityformdate"]))} · '
                        f'<a href="{esc(STATE_RECORD_URL.format(entityid=r["entityid"]))}" rel="noopener">record {esc(r["entityid"])}</a></span></li>')
        body.append('</ul></section>')
    if not kept and not unknown:
        body.append('<p style="color:var(--ink-3);font-style:italic;margin:32px 0 0">Entries appear here after the first classification run.</p>')
    return page(f"New businesses in {city} this week — {SITE_NAME}", "".join(body), root, current=city,
                desc=f"Newly formed businesses in {city}, Colorado this week, filtered to real operating companies and tagged by industry. {STRAPLINE}")


def landing(sample: tuple, totals: dict, root: str) -> str:
    r, c = sample
    raw_row = " | ".join(f"<span>{esc(r.get(k, ''))}</span>" for k in ("entityid", "entityname", "principalcity", "principalstate", "principalzipcode", "entitytype", "entitystatus", "jurisdictonofformation", "entityformdate"))
    cities = "".join(f'<li><a href="{root}{slug(ct)}/">{esc(ct)}</a> <span class="sans" style="color:var(--ink-3);font-size:13px">{totals.get(ct, 0)} worth reading</span></li>' for ct in LAUNCH_CITIES)
    options = "".join(f'<option>{esc(ct)}</option>' for ct in LAUNCH_CITIES)
    body = f"""<main class="landing">
<div class="hero"><h1>New businesses, sorted for the people who sell to them.</h1>
<p class="lede">Every week the state records about two thousand new companies. Most are holding companies, shells, and names that say nothing. NewCo Brief cuts those, infers the trade from what is left, and writes one line for a commercial insurance broker on each.</p>
<a class="cta" href="{root}denver/">See this week in Denver</a></div>
<div class="transform"><p class="kicker">What the state records</p><div class="raw">{raw_row}</div><div class="join"><div class="arm"></div><p class="kicker">What we publish</p></div>{entry(r, c, r.get("principalcity", "")).replace('<article class="entry">', '<article class="entry" style="padding-top:18px">')}</div>
<h2>Who it is for</h2>
<p>Commercial insurance brokers first. A new roofing company needs general liability and workers' compensation before it can take most jobs, and it has not chosen a broker yet. Bankers, accountants, and payroll providers read the same list for the same reason.</p>
<h2>This week's city pages</h2>
<p>Free, public, and refreshed nightly. Each shows the last seven days, grouped by industry, with a link to the official state record on every entry.</p>
<ul class="cities-list">{cities}</ul>
<h2>Get one city by email, free</h2>
<p>Every Monday morning. No card. One city is always free; paid plans will add the whole state and the whole office.</p>
<form class="signup" action="#" method="post" data-todo="wire to an email service before launch">
<label for="email">Email</label><input id="email" name="email" type="email" required placeholder="you@agency.com">
<label for="city">City</label><select id="city" name="city">{options}</select>
<button type="submit">Send me the Monday brief</button>
<p class="fine">We publish city and ZIP only, never street addresses, owner names, or phone numbers. Unsubscribe in one click.</p></form>
</main>"""
    return page(f"{SITE_NAME} — {STRAPLINE}", body, root)


def main() -> None:
    files = sorted(f for f in FILTERED_DIR.glob("*.json") if not f.name.endswith("-dropped.json"))
    rows = json.loads(files[-1].read_text())
    raw = json.loads((RAW_DIR / files[-1].name).read_text()) if (RAW_DIR / files[-1].name).exists() else rows
    cache = json.loads(CLASSIFIED_FILE.read_text()) if CLASSIFIED_FILE.exists() else {}
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS.strip() + "\n")
    (SITE_DIR / ".nojekyll").write_text("")

    totals = {}
    for city in LAUNCH_CITIES:
        crows = [r for r in rows if (r.get("principalcity") or "").upper() == city.upper()]
        filed = sum(1 for r in raw if (r.get("principalcity") or "").upper() == city.upper())
        out = SITE_DIR / slug(city)
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(city_page(city, crows, filed, cache, "../"))
        totals[city] = sum(1 for r in crows if worth_reading(cache.get(r["entityid"])))

    # Landing sample: a roofing entry, so the demo and the "Who it is for" paragraph make one argument.
    # Falls back to any high-confidence trade, then to a fixed placeholder until classification runs.
    def pick(pred):
        return next((r for r in rows if worth_reading(cache.get(r["entityid"])) and cache[r["entityid"]]["confidence"] == "high"
                     and cache[r["entityid"]]["note"] and pred(cache[r["entityid"]])), None)
    best = (pick(lambda c: "roof" in (c["detail"] + " " + c["note"]).lower())
            or pick(lambda c: c["industry"] == "Construction and trades")
            or pick(lambda c: True))
    if best:
        sample = (best, cache[best["entityid"]])
    else:
        sample = ({"entityid": "20268112354", "entityname": "GTO ROOFING LLC", "principalcity": "Denver", "principalstate": "CO",
                   "principalzipcode": "80236", "entitytype": "DLLC", "entitystatus": "Good Standing",
                   "jurisdictonofformation": "CO", "entityformdate": "2026-09-02T00:00:00.000"},
                  {"industry": "Construction and trades", "detail": "roofing", "operating": True, "confidence": "high",
                   "note": "A new roofing contractor usually needs general liability and workers' compensation before a general contractor or property manager will hire the crew, and a work truck means commercial auto."})
    (SITE_DIR / "index.html").write_text(landing(sample, totals, "./"))
    print(f"Wrote landing page + {len(LAUNCH_CITIES)} city pages to {SITE_DIR}")


if __name__ == "__main__":
    main()
