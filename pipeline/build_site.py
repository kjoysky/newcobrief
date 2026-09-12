"""Step 5. Generate the static website into docs/ (GitHub Pages serves that folder).

Follows 04-Design-Decisions.pdf: white page, one green hue, the state's record inside a tinted
field, everything we wrote outside it, Newsreader + Archivo, three figures on every city page.
Usage:
    python3 pipeline/build_site.py
"""
import html
import json
from collections import defaultdict
from datetime import date, timedelta

from config import (CLASSIFIED_FILE, ENTITY_TYPE_LABELS, FILTERED_DIR, INDUSTRIES, LAUNCH_CITIES,
                    PROJECT_DIR, RAW_DIR, STATE_RECORD_URL, worth_reading)

SITE_DIR = PROJECT_DIR / "docs"
SITE_NAME = "NewCo Brief"
STRAPLINE = "New businesses. Earlier opportunities."
DESCRIPTION = ("NewCo Brief finds newly formed businesses, filters out the noise, and gives commercial "
               "professionals an earlier look at companies entering their market.")
HOME_TITLE = "New Colorado business filings, weekly — NewCo Brief"
HOME_DESCRIPTION = ("A weekly brief of newly formed Colorado businesses: the state's filings, filtered to real "
                    "operating companies, tagged by trade, with one line for a commercial insurance broker on each. "
                    "One city is free.")
AUTHOR = "Kristina Nelson"
CONTACT_EMAIL = "brief@newcobrief.com"     # forwards to kjoysky31@gmail.com via ImprovMX (MX + SPF at GoDaddy, 2026-09-10)
BUY_URL = "https://buttondown.com/newcobrief/buy"   # Buttondown's hosted Stripe checkout for the Statewide plan
FIRM_BUY_URL = BUY_URL + "?product_id=prod_VF6nXdrVgo1vFw"   # same, for the Firm product (Stripe product id; verified 2026-09-11)
PRICE_LINE = "Statewide is $49 a month for every city you choose. Firm plans cover the whole office."
PRICE_HTML = (f'Statewide is <a href="{BUY_URL}">$49 a month</a> for every city you choose. '
              f'<a href="{{root}}plans/">Firm plans</a> cover the whole office.')
THIN_WEEK = 20
# Public city pages show ONE trade in full (the lead trade, up to this many entries) and every other trade
# as a count. Decided 2026-09-10 after reviewer feedback: the name lists let a broker prospect straight off
# the free page, so the email added nothing. The Monday email and paid plans carry every entry in full.
FULL_PER_INDUSTRY = 3
LEAD_INDUSTRY = "Construction and trades"
# Set in main() from the data: the formation-date span shown under the masthead on every page.
WEEK = {"span": "", "next_send": ""}
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
.plain li .trade{font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:13px;color:var(--accent)}
.gate{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:14px;color:var(--ink-2);margin:18px 0 0;max-width:40em}
.gate a{font-weight:600}
section.industry .kicker.also{color:var(--ink-3);border:0;margin:22px 0 4px;padding:0}
.plain li .meta{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:12.5px;color:var(--ink-3);font-variant-numeric:tabular-nums;white-space:nowrap}
.week{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:12.5px;color:var(--ink-3);margin:14px 0 0;font-variant-numeric:tabular-nums}
.week b{font-weight:600;color:var(--ink-2)}
.counts{list-style:none;padding:0;margin:14px 0 0;max-width:480px}
.counts li{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;border-bottom:1px solid var(--rule);font-size:17px}
.counts li .n{font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:14px;color:var(--accent);font-variant-numeric:tabular-nums}
.signup.top{margin-top:26px}
.signup .row{display:flex;gap:10px;align-items:stretch;margin-top:6px}
.signup .row input{flex:1;min-width:0}
.signup .row button{margin:0;white-space:nowrap}
.signup .next{font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:12.5px;color:var(--accent);margin:12px 0 0}
.signup .alt{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:13px;color:var(--ink-3);margin:8px 0 0}
.landing ul.cities-list{columns:1;max-width:520px}
.landing ul.cities-list li{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;border-bottom:1px solid var(--rule)}
.landing ul.cities-list .fig{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:13px;color:var(--ink-3);font-variant-numeric:tabular-nums;white-space:nowrap}
.landing ul.cities-list .fig b{font-weight:600;color:var(--accent)}
.hero .figures{margin-top:26px}
.prose{max-width:34em;font-size:18px;line-height:1.6}
.prose h1{font-size:36px;margin:40px 0 8px}.prose h2{font-family:var(--serif);font-weight:600;letter-spacing:-.02em;font-size:24px;margin:36px 0 8px}
.prose p{margin:12px 0 0}
.plans .plan{border-top:1px solid var(--rule);padding:22px 0 26px;margin-top:28px}.plans .plan .kicker{margin:0 0 4px}
.plans .price{font-family:var(--serif);font-weight:600;font-size:32px;letter-spacing:-.02em;margin:0}.plans .price span{font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:14px;letter-spacing:0;color:var(--ink-2)}
.plans a.cta{font-family:var(--sans);font-stretch:87.5%;font-weight:600}
.sample-email{border:1px solid var(--rule);padding:8px 16px 0;margin:24px 0 0;overflow-x:auto}
footer nav{margin:0 0 12px;display:flex;flex-wrap:wrap;gap:6px 16px;font-weight:600}
footer nav a{color:var(--ink-2)}
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
.landing ul.cities-list{padding:0;margin:14px 0 0;list-style:none;font-size:17px}
.signup{margin:40px 0 0;border-top:2px solid var(--ink);padding-top:20px;max-width:520px}
.signup label{display:block;font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);margin:14px 0 6px}
.signup input,.signup select{width:100%;font-family:var(--sans);font-stretch:87.5%;font-weight:550;font-size:16px;padding:10px 12px;border:1px solid var(--field-line);background:var(--page);color:var(--ink);border-radius:0}
.signup button{margin-top:16px;font-family:var(--sans);font-stretch:87.5%;font-weight:600;font-size:15px;letter-spacing:.02em;padding:12px 20px;background:var(--accent);color:#fff;border:0;cursor:pointer;border-radius:0}
.signup button:hover{background:var(--accent-deep)}
.signup .fine{font-family:var(--sans);font-stretch:87.5%;font-size:12.5px;color:var(--ink-3);margin:10px 0 0}
@media (max-width:600px){body{font-size:16px}h1{font-size:34px}.hero h1{font-size:32px}.figures{gap:22px}.figures b{font-size:28px}.entry h2{font-size:21px}.entry p.note{font-size:17px}.signup .row{flex-direction:column}}
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


# Buttondown embedded form. The city <select> is named "tag" so each subscriber
# is tagged with a city slug (needs the Basic plan; tags are ignored on Free).
SIGNUP_ACTION = "https://buttondown.com/api/emails/embed-subscribe/newcobrief"


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
<nav class="cities" aria-label="Cities">{nav}</nav>
<p class="week">Week of <b>{esc(WEEK["span"])}</b> · Refreshed nightly · Next email <b>Monday, {esc(WEEK["next_send"])}</b></p></header>
{body}
<footer><nav aria-label="About"><a href="{root}about/">About</a><a href="{root}plans/">Plans</a><a href="{root}sample/">Sample issue</a><a href="{root}privacy/">Privacy and terms</a><a href="mailto:{CONTACT_EMAIL}">Contact</a></nav>
<p>{esc(DESCRIPTION)} Written and run by {esc(AUTHOR)}.</p>
<p>Business records are published by the Colorado Secretary of State and are in the public domain. Industry and commentary are inferred from the business name by NewCo Brief and are labeled as inferred. City and ZIP only; no street addresses, owner names, or phone numbers are published. Entries are shown for 90 days. No export.</p>
<p>&copy; {date.today().year} NewCo Brief</p></footer>
</div></body></html>"""


def signup_form(selected: str = "", top: bool = False, heading: str = "", root: str = "../") -> str:
    """The email signup box. On city pages the city is a hidden field (they already chose it);
    on the home page it is a <select> defaulting to Denver."""
    if selected:
        city_field = f'<input type="hidden" name="tag" value="{slug(selected)}">'
        title = heading or f"Get {esc(selected)} by email, free"
    else:
        options = "".join(f'<option value="{slug(ct)}"{" selected" if ct == LAUNCH_CITIES[0] else ""}>{esc(ct)}</option>' for ct in LAUNCH_CITIES)
        city_field = f'<label for="city">City</label><select id="city" name="tag">{options}</select>'
        title = heading or "Get one city by email, free"
    uid = "top" if top else "signup"
    return f"""<h2 id="{uid}">{title}</h2>
<p>Every Monday morning, every entry in full. No card. One city is always free. {PRICE_HTML.format(root=root)}</p>
<form class="signup{" top" if top else ""}" action="{SIGNUP_ACTION}" method="post">
{city_field}
<label for="email-{uid}">Email</label><div class="row"><input id="email-{uid}" name="email" type="email" required placeholder="you@agency.com">
<button type="submit">Send me the Monday brief</button></div>
<p class="next">Next issue: Monday, {esc(WEEK["next_send"])}</p>
<p class="fine">We publish city and ZIP only, never street addresses, owner names, or phone numbers. Unsubscribe in one click.</p></form>"""


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
    groups = defaultdict(list)
    for r in crows:
        c = cache.get(r["entityid"])
        if c and worth_reading(c):
            groups[c["industry"]].append((r, c))
    kept = sum(len(v) for v in groups.values())
    cut = filed - kept   # everything not shown in full is cut: holding companies, mailbox addresses, low-confidence guesses
    dates = sorted(r["entityformdate"][:10] for r in crows) or [date.today().isoformat()]
    present = [ind for ind in INDUSTRIES if groups.get(ind)]
    lead = LEAD_INDUSTRY if LEAD_INDUSTRY in present else (present[0] if present else "")
    lead_entries = sorted(groups.get(lead, []), key=lambda rc: (CONF_ORDER[rc[1]["confidence"]], rc[0]["entityname"].lower()))
    shown = lead_entries[:FULL_PER_INDUSTRY]
    remaining = kept - len(shown)
    gate = (f'This page shows {esc(lead.lower())} in full. The Monday email carries all {kept}, every trade. <a href="#top">One city is free.</a>'
            if shown else "")
    body = [f'<div class="edition"><p class="kicker">This week in</p><h1>{esc(city)}</h1>'
            f'<p class="dateline">New businesses formed {fmt_date(dates[0])} to {fmt_date(dates[-1])}</p>'
            f'<div class="figures"><div><b>{filed}</b><span>Filed</span></div><div><b>{cut}</b><span>Cut</span></div>'
            f'<div><b class="kept">{kept}</b><span>Worth reading</span></div></div>'
            + (f'<p class="gate">{gate}</p>' if gate else "") + '</div>']
    if kept < THIN_WEEK:
        body.append(f'<p class="notice">A thin week in {esc(city)}. The state recorded {filed} new entities here; after removing holding companies, registered-agent addresses, and names that reveal nothing, {kept} were worth a broker\'s time. We would rather show a short list than pad it.</p>')
    body.append(f'<div class="landing">{signup_form(city, top=True)}</div>')
    if shown:
        body.append(f'<section class="industry"><p class="kicker">{esc(lead)} · {len(lead_entries)}</p>')
        for r, c in shown:
            body.append(entry(r, c, city))
        body.append('</section>')
    if remaining:
        body.append(f'<section class="industry"><p class="kicker">In Monday\'s email · {remaining} more</p><ul class="counts">')
        if len(lead_entries) > len(shown):
            body.append(f'<li><span>{esc(lead)}</span><span class="n">{len(lead_entries) - len(shown)} more</span></li>')
        for ind in present:
            if ind != lead:
                body.append(f'<li><span>{esc(ind)}</span><span class="n">{len(groups[ind])}</span></li>')
        body.append('</ul></section>')
        body.append(f'<div class="landing" style="margin-top:8px">{signup_form(city, heading=f"The other {remaining} come Monday")}</div>')
    elif not shown:
        body.append('<p style="color:var(--ink-3);font-style:italic;margin:32px 0 0">Entries appear here after the first classification run.</p>')
    return page(f"New businesses in {city} this week — {SITE_NAME}", "".join(body), root, current=city,
                desc=f"Newly formed businesses in {city}, Colorado this week, filtered to real operating companies and tagged by industry. {STRAPLINE}")


def landing(sample: tuple, totals: dict, statewide: int, root: str) -> str:
    r, c = sample
    raw_row = " | ".join(f"<span>{esc(r.get(k, ''))}</span>" for k in ("entityid", "entityname", "principalcity", "principalstate", "principalzipcode", "entitytype", "entitystatus", "jurisdictonofformation", "entityformdate"))
    cities = "".join(f'<li><a href="{root}{slug(ct)}/">{esc(ct)}</a> <span class="fig">{t["filed"]} filed · {t["cut"]} cut · <b>{t["kept"]} worth reading</b></span></li>'
                     for ct in LAUNCH_CITIES for t in [totals.get(ct, {"filed": 0, "cut": 0, "kept": 0})])
    filed = sum(t["filed"] for t in totals.values())
    kept = sum(t["kept"] for t in totals.values())
    body = f"""<main class="landing">
<div class="hero"><h1>New businesses, sorted for the people who sell to them.</h1>
<p class="lede">This week Colorado recorded {statewide:,} new companies. Most are holding companies, mailbox registrations, and names that say nothing. NewCo Brief cuts those, infers the trade from what is left, and writes one line for a commercial insurance broker on each.</p>
<p class="kicker" style="margin-top:26px">This week in our ten cities</p>
<div class="figures" style="margin-top:8px"><div><b>{filed}</b><span>Filed</span></div><div><b>{filed - kept}</b><span>Cut</span></div><div><b class="kept">{kept}</b><span>Worth reading</span></div></div></div>
<div class="transform"><p class="kicker">What the state records</p><div class="raw">{raw_row}</div><div class="join"><div class="arm"></div><p class="kicker">What we publish</p></div>{entry(r, c, r.get("principalcity", "")).replace('<article class="entry">', '<article class="entry" style="padding-top:18px">')}</div>
{signup_form(top=True, root=root)}
<p class="alt sans" style="color:var(--ink-3);font-size:13px;margin:10px 0 0"><a href="{root}sample/">See a sample issue</a> · <a href="{root}denver/">See this week in Denver</a></p>
<h2>Who it is for</h2>
<p>Commercial insurance brokers. The entry above is the kind of account that has not chosen a broker yet, and it arrives here days after filing, before the company has a website or a listing.</p>
<p>Not yet for bankers, accountants, or payroll providers. Every line of commentary is written for insurance; editions for those desks come later. Not for consumer marketing: we publish city and ZIP only, never owner names, phones, or street addresses.</p>
<h2>This week's city pages</h2>
<p>Free, public, and refreshed nightly. Each shows this week's figures and the lead trade in full. The Monday email carries every entry.</p>
<ul class="cities-list">{cities}</ul>
</main>"""
    return page(HOME_TITLE, body, root, desc=HOME_DESCRIPTION)


def about_page(root: str) -> str:
    body = f"""<main class="prose">
<h1>About NewCo Brief</h1>
<p>NewCo Brief is a weekly brief of newly formed Colorado businesses, written for the people who sell to them. Every night it reads the Colorado Secretary of State's public list of new entities, removes holding companies, mailbox registrations, and names that say nothing, infers the trade from the name, and writes one line for a commercial insurance broker on each. The email goes out Monday morning. One city is free. {PRICE_HTML.format(root=root)}</p>
<h2>Who makes it</h2>
<p>NewCo Brief is written and run by {esc(AUTHOR)}. The filtering rules, the industry list, and the decisions about what to cut and what to publish are hers. Names are sorted against the industry list with the help of an AI model, and every inferred label is marked as inferred so you can judge it yourself. The state record is linked on every entry.</p>
<h2>What we publish, and what we don't</h2>
<p>Business name, city and ZIP, entity type, formation date, and the state's record number. Never street addresses, owner names, registered-agent names, phone numbers, or email addresses, even though some of those are in the public record. Entries stay on the site for 90 days. There is no export.</p>
<h2>Contact</h2>
<p>Questions, corrections, or a request to remove an entry: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. Replies to the Monday email reach the same desk.</p>
</main>"""
    return page(f"About — {SITE_NAME}", body, root, desc="Who makes NewCo Brief, what it publishes, and how to reach us.")


def plans_page(root: str) -> str:
    n = len(LAUNCH_CITIES)
    body = f"""<main class="prose plans">
<h1>Plans</h1>
<p>Every plan is the same Monday email: newly formed Colorado businesses, filtered to real operating companies, tagged by trade, one line for a broker on each, every entry in full. Plans differ only in how many cities and how many people.</p>
<div class="plan"><p class="kicker">Free</p><p class="price">$0</p>
<p>One city of your choice, every Monday. Pick it at signup; change it any time from the link at the bottom of any issue.</p>
<p><a href="{root}#top">Get one city free &rarr;</a></p></div>
<div class="plan"><p class="kicker">Statewide</p><p class="price">$49 <span>a month, or $490 a year</span></p>
<p>Every city you choose, as many as you like, from the {n} we cover. Add or drop cities yourself from the same link. Billed by Stripe; cancel any time. One new account can pay for months of NewCo Brief.</p>
<p><a class="cta" href="{BUY_URL}">Subscribe to Statewide &rarr;</a></p></div>
<div class="plan"><p class="kicker">Firm</p><p class="price">$199 <span>a month for up to five people</span></p>
<p>Statewide for the whole office: five addresses at one agency, each choosing their own cities. $1,990 a year at checkout. Larger offices, ask. Search across past issues is coming and will be added to Firm plans first.</p>
<p><a class="cta" href="{FIRM_BUY_URL}">Subscribe to Firm &rarr;</a> After checkout, email the other four addresses to <a href="mailto:{CONTACT_EMAIL}?subject=Firm%20plan%20seats">{CONTACT_EMAIL}</a> and they are added the same day.</p></div>
<h2>Questions</h2>
<p><b>Is there a trial?</b> The free city is the trial. It is the same email, the same week, in full.</p>
<p><b>Can I pay yearly?</b> Yes. Statewide is $490 a year, two months free. Choose yearly at checkout.</p>
<p><b>What about sales tax?</b> Stripe adds it at checkout where your state requires it, and the receipt shows it separately.</p>
<p><b>How do I cancel?</b> From the link at the bottom of any issue. The plan runs to the end of the period you paid for.</p>
<p>Anything else: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
</main>"""
    return page(f"Plans — {SITE_NAME}", body, root, desc=f"One city free. Statewide $49 a month for every city you choose. Firm plans for the whole office.")


def check_email_page(root: str) -> str:
    """Where Buttondown sends people right after the signup form (subscription_redirect_url)."""
    body = f"""<main class="prose">
<h1>One more step: check your email</h1>
<p>We just sent a confirmation link to the address you entered. Click it and you're on the list. If it isn't there in a minute or two, look in spam or promotions and move it to your inbox so the brief lands where you'll see it.</p>
<p>Once you confirm, your first issue arrives overnight with this week's list for your city. After that it comes every Monday morning.</p>
<p>Don't want to wait? This week's entries are already on the site: <a href="{root}">pick a city</a>.</p>
</main>"""
    return page(f"Check your email — {SITE_NAME}", body, root, desc="Confirm your NewCo Brief subscription from the email we just sent.")


def welcome_page(root: str) -> str:
    """Where Buttondown sends people after they click the confirmation link (subscription_confirmation_redirect_url)."""
    cities = " · ".join(f'<a href="{root}{slug(c)}/">{esc(c)}</a>' for c in LAUNCH_CITIES)
    body = f"""<main class="prose">
<h1>You're in</h1>
<p><b>This week's entries are on the site right now.</b> Pick your city: {cities}.</p>
<p>The site shows the lead trade in full and counts the rest. <b>Your first issue arrives overnight</b> with every entry for your city, in full, with the one-line note on each. Then it comes every Monday morning from <b>brief@newcobrief.com</b>. Monday's issue covers the whole week, so it will repeat some of what you get tonight; after that, each Monday is new.</p>
<p>Want to see exactly what lands in your inbox? <a href="{root}sample/">Here is a sample issue.</a></p>
<p>Every city, not just one? <a href="{root}plans/">Statewide is $49 a month</a>, and you can add it any time from the link at the bottom of an issue. No rush.</p>
<p>Reply to any issue and it reaches {esc(AUTHOR)} directly.</p>
</main>"""
    return page(f"You're in — {SITE_NAME}", body, root, desc="Welcome to NewCo Brief. Your first issue arrives overnight; this week's entries are on the site now.")


def privacy_page(root: str) -> str:
    body = f"""<main class="prose">
<h1>Privacy and terms</h1>
<p class="dateline">Last updated {fmt_date(date.today().isoformat())}</p>
<h2>Your email address</h2>
<p>When you subscribe we store your email address and the city you chose, nothing else. We use them only to send you the Monday brief and to answer your replies. We never sell, rent, or share subscriber addresses. Every email has a one-click unsubscribe, and unsubscribing deletes you from the list. Sending is handled by Buttondown, whose own <a href="https://buttondown.com/legal/privacy" rel="noopener">privacy policy</a> applies to the delivery.</p>
<h2>The site</h2>
<p>The site sets no cookies and runs no analytics or advertising scripts. Fonts are loaded from Google Fonts, which receives your IP address when the page loads.</p>
<h2>The business data</h2>
<p>Business records come from the Colorado Secretary of State and are in the public domain. Industry and commentary are inferred from the business name by NewCo Brief and are labeled as inferred; they can be wrong. We publish city and ZIP only, never street addresses, owner names, or phone numbers. If you own a business listed here and want the entry removed, email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> and we will remove it.</p>
<h2>Terms of use</h2>
<p>The site and the free email are for your own professional use. You may not scrape, export, republish, or resell the lists. NewCo Brief is provided as is, with no warranty that any entry is accurate or complete; verify against the linked state record before you act on it. Paid plans are billed by Stripe, monthly or yearly, with sales tax added where the law requires it; cancel any time from the link at the bottom of any issue and the plan ends at the close of the period already paid for. A Firm plan is for the named people at one office; sharing issues outside that office is not permitted.</p>
<p>Questions: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
</main>"""
    return page(f"Privacy and terms — {SITE_NAME}", body, root, desc="How NewCo Brief handles subscriber email addresses and public business data.")


def span_label(a: str, b: str) -> str:
    """'September 3–7, 2026', 'August 30 – September 7, 2026', or one date."""
    if a == b:
        return fmt_date(a)
    da, db = date.fromisoformat(a[:10]), date.fromisoformat(b[:10])
    if da.year == db.year and da.month == db.month:
        return f"{da.strftime('%B')} {da.day}–{db.day}, {db.year}"
    if da.year == db.year:
        return f"{da.strftime('%B')} {da.day} – {db.strftime('%B')} {db.day}, {db.year}"
    return f"{fmt_date(a)} – {fmt_date(b)}"


def next_monday(d: date) -> date:
    return d + timedelta(days=(0 - d.weekday()) % 7)


def main() -> None:
    files = sorted(f for f in FILTERED_DIR.glob("*.json") if not f.name.endswith("-dropped.json"))
    rows = json.loads(files[-1].read_text())
    raw = json.loads((RAW_DIR / files[-1].name).read_text()) if (RAW_DIR / files[-1].name).exists() else rows
    cache = json.loads(CLASSIFIED_FILE.read_text()) if CLASSIFIED_FILE.exists() else {}
    SITE_DIR.mkdir(exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS.strip() + "\n")
    (SITE_DIR / ".nojekyll").write_text("")
    (SITE_DIR / "CNAME").write_text("newcobrief.com\n")   # custom domain for GitHub Pages

    dates = sorted(r["entityformdate"][:10] for r in rows) or [date.today().isoformat()]
    WEEK["span"] = span_label(dates[0], dates[-1])
    WEEK["next_send"] = next_monday(date.today()).strftime("%B %-d")

    totals = {}
    for city in LAUNCH_CITIES:
        crows = [r for r in rows if (r.get("principalcity") or "").upper() == city.upper()]
        filed = sum(1 for r in raw if (r.get("principalcity") or "").upper() == city.upper())
        out = SITE_DIR / slug(city)
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(city_page(city, crows, filed, cache, "../"))
        kept = sum(1 for r in crows if worth_reading(cache.get(r["entityid"])))
        totals[city] = {"filed": filed, "cut": filed - kept, "kept": kept}
    for name, fn in (("about", about_page), ("plans", plans_page), ("privacy", privacy_page), ("check-email", check_email_page), ("welcome", welcome_page)):
        (SITE_DIR / name).mkdir(exist_ok=True)
        (SITE_DIR / name / "index.html").write_text(fn("../"))

    # Landing sample: a Denver roofing entry, so the demo matches the Denver link and the lead trade.
    # Falls back to any roofer, any high-confidence trade, then a fixed placeholder until classification runs.
    def pick(pred, city=""):
        return next((r for r in rows if worth_reading(cache.get(r["entityid"])) and cache[r["entityid"]]["confidence"] == "high"
                     and cache[r["entityid"]]["note"] and pred(cache[r["entityid"]])
                     and (not city or (r.get("principalcity") or "").upper() == city)), None)
    roof = lambda c: "roof" in (c["detail"] + " " + c["note"]).lower()
    best = (pick(roof, "DENVER") or pick(roof)
            or pick(lambda c: c["industry"] == LEAD_INDUSTRY, "DENVER")
            or pick(lambda c: c["industry"] == LEAD_INDUSTRY)
            or pick(lambda c: True))
    if best:
        sample = (best, cache[best["entityid"]])
    else:
        sample = ({"entityid": "20268112354", "entityname": "GTO ROOFING LLC", "principalcity": "Denver", "principalstate": "CO",
                   "principalzipcode": "80236", "entitytype": "DLLC", "entitystatus": "Good Standing",
                   "jurisdictonofformation": "CO", "entityformdate": "2026-09-02T00:00:00.000"},
                  {"industry": "Construction and trades", "detail": "roofing", "operating": True, "confidence": "high",
                   "note": "A new roofing contractor usually needs general liability and workers' compensation before a general contractor or property manager will hire the crew, and a work truck means commercial auto."})
    (SITE_DIR / "index.html").write_text(landing(sample, totals, len(raw), "./"))
    print(f"Wrote landing page, about, privacy + {len(LAUNCH_CITIES)} city pages to {SITE_DIR}")


if __name__ == "__main__":
    main()
