"""Step 6. Build the Monday email for each launch city from the same data as the city pages.

One column, tables and inline styles only, so it reads the same in Gmail and Outlook (02-Design-Brief.md,
item 3). Palette and type follow 04-Design-Decisions.pdf with email-safe fallbacks: Georgia for the serif,
Arial for the sans. Gmail clips messages over ~102 KB, so each email is kept under EMAIL_BUDGET bytes by
showing the first N entries per industry and linking to the full city page for the rest.

Writes data/email/<city>.html (a full page for previewing in a browser) and data/email/manifest.json
(subject + body fragment per city, read by send_email.py).
Usage:
    python3 pipeline/build_email.py            # all cities
    python3 pipeline/build_email.py --city Denver
"""
import json
import sys
from collections import defaultdict
from datetime import date

from build_site import (CONF_ORDER, SITE_DIR, SITE_NAME, STRAPLINE, THIN_WEEK, WEEK, display_name, esc, fmt_date,
                        next_monday, page, short_date, slug, span_label, type_label)
from config import (CLASSIFIED_FILE, DATA_DIR, FILTERED_DIR, INDUSTRIES, LAUNCH_CITIES, RAW_DIR,
                    STATE_RECORD_URL, worth_reading)

EMAIL_DIR = DATA_DIR / "email"
SITE_URL = "https://newcobrief.com"
EMAIL_BUDGET = 66_000          # bytes of HTML body. Gmail clips the HTML part at ~102 KB. Measured 2026-09-11 on the first
                               # real send: Buttondown adds ~21 KB of wrapper/styles, and its "UTM information" setting added
                               # ~117 bytes to each of the 108 links (12.6 KB); quoted-printable encoding adds ~6% on top.
                               # A 88.7 KB body went out at 123 KB and Gmail clipped it. Every entry carries a link, so UTM
                               # costs ~12.6 KB at any budget: 66 + 21 + 12.6 = 99.6 KB (~105 KB encoded) would still clip.
                               # UTM information must stay OFF in Buttondown (Settings -> Tracking): 66 + 21 = 87 KB, ~92 KB
                               # encoded. Click tracking was already off.

# Colours from 04-Design-Decisions.pdf
INK, INK2, INK3 = "#16241D", "#4A5A52", "#7B8A82"
RULE, N05, FIELD, FIELD_LINE = "#D5DDD6", "#F4F5F3", "#E3EDE4", "#B7CCBB"
ACCENT, STAMP = "#17754C", "#A33526"
SERIF = "Georgia,serif"
SANS = "Arial,sans-serif"


def row(inner: str, pad: str = "0") -> str:
    return f'<tr><td style="padding:{pad};">{inner}</td></tr>'


def kicker(text: str, color: str = INK3) -> str:
    return (f'<p style="margin:0;font-family:{SANS};font-size:11px;font-weight:bold;letter-spacing:1px;'
            f'text-transform:uppercase;color:{color};">{text}</p>')


def entry_html(r: dict, c: dict) -> str:
    trade = esc(c["industry"]) + (f': {esc(c["detail"])}' if c.get("detail") else "")
    note = (f'<p style="margin:8px 0 0;font-family:{SERIF};font-size:16px;line-height:1.55;color:{INK};">{esc(c["note"])}</p>'
            if c.get("note") else "")
    src = STATE_RECORD_URL.format(entityid=r["entityid"])
    return (
        f'<tr><td style="padding:18px 0;border-bottom:1px solid {RULE};">'
        f'<p style="margin:0 0 8px;font-family:{SERIF};font-size:20px;line-height:1.2;color:{INK};">{esc(display_name(r["entityname"]))}</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="background:{FIELD};border-left:2px solid {FIELD_LINE};padding:7px 10px;font-family:{SANS};font-size:12px;line-height:1.6;color:{INK};">'
        f'<span style="color:{INK3};font-size:10px;letter-spacing:.5px;">CITY</span> {esc((r.get("principalcity") or "").title())} {esc(r.get("principalzipcode", ""))}'
        f'&nbsp;&nbsp;&nbsp;<span style="color:{INK3};font-size:10px;letter-spacing:.5px;">TYPE</span> {esc(type_label(r))}'
        f'&nbsp;&nbsp;&nbsp;<span style="color:{INK3};font-size:10px;letter-spacing:.5px;">FORMED</span> {esc(short_date(r["entityformdate"]))}'
        f'&nbsp;&nbsp;&nbsp;<span style="color:{INK3};font-size:10px;letter-spacing:.5px;">ID</span> {esc(r["entityid"])}'
        f'</td></tr></table>'
        f'<p style="margin:10px 0 0;font-family:{SANS};font-size:13px;font-weight:bold;color:{ACCENT};">{trade}'
        f'&nbsp;&nbsp;<span style="font-size:9px;font-weight:bold;letter-spacing:.5px;color:{STAMP};border:1px solid {STAMP};padding:1px 4px;">INFERRED FROM THE NAME</span></p>'
        f'{note}'
        f'<p style="margin:8px 0 0;font-family:{SANS};font-size:12px;color:{INK3};"><a href="{esc(src)}" style="color:{ACCENT};text-decoration:none;">Colorado Secretary of State record {esc(r["entityid"])}</a></p>'
        f'</td></tr>')


def compact_line(r: dict, c: dict) -> str:
    """One line per entry, used past the per-industry cap so long weeks still list every name.
    Kept lean (about 300 bytes) because Denver can have 170 of these in a week."""
    detail = esc(c["detail"]) if c.get("detail") else esc(c["industry"].lower())
    src = STATE_RECORD_URL.format(entityid=r["entityid"])
    return (f'{esc(display_name(r["entityname"]))} <span style="font:12px {SANS};color:{ACCENT};">{detail}</span> '
            f'<a href="{esc(src)}" style="font:11px {SANS};color:{INK3};text-decoration:none;">record</a>')


def compact_block(entries: list) -> str:
    lines = "<br>".join(compact_line(r, c) for r, c in entries)
    return f'<p style="margin:0;font-family:{SERIF};font-size:15px;line-height:1.7;color:{INK};">{lines}</p>'


def city_email(city: str, crows: list, filed: int, cache: dict, sample_n: int | None = None) -> tuple[str, str]:
    """Returns (subject, body fragment). The fragment is what goes to Buttondown; it has no <html> wrapper.
    sample_n builds the public sample issue instead: the first n entries in full, the rest as counts."""
    groups = defaultdict(list)
    for r in crows:
        c = cache.get(r["entityid"])
        if c and worth_reading(c):
            groups[c["industry"]].append((r, c))
    for ind in groups:
        groups[ind].sort(key=lambda rc: (CONF_ORDER[rc[1]["confidence"]], rc[0]["entityname"].lower()))
    kept = sum(len(v) for v in groups.values())
    cut = filed - kept
    dates = sorted(r["entityformdate"][:10] for r in crows) or [date.today().isoformat()]
    page_url = f"{SITE_URL}/{slug(city)}/"
    end = short_date(dates[-1]).split()[1] if dates[0][:7] == dates[-1][:7] else short_date(dates[-1])
    span = short_date(dates[0]) if dates[0] == dates[-1] else f"{short_date(dates[0])}–{end}"
    subject = f"{city}: {kept} new businesses worth reading, {span}"

    # Round-robin order for full entries: the best entry in every industry first, then the second in every
    # industry, and so on. Long weeks show the first n of these in full and the rest as one-liners.
    order = []
    for i in range(max((len(v) for v in groups.values()), default=0)):
        order += [groups[ind][i][0]["entityid"] for ind in INDUSTRIES if ind in groups and i < len(groups[ind])]

    def render(n_full: int, compact: bool = True) -> str:
        full_ids = set(order[:n_full])
        # The marker tells Buttondown to keep this as raw HTML instead of converting it into its rich editor.
        parts = ['<!-- buttondown-editor-mode: plaintext -->', f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;margin:0 auto;">']
        # Masthead
        parts.append(row(
            f'<p style="margin:0;font-family:{SANS};font-size:22px;line-height:1;color:{INK};letter-spacing:-.5px;"><b>NewCo</b> Brief</p>'
            f'<div style="border-top:2px solid {INK};margin:12px 0 6px;"></div>'
            f'<p style="margin:0;font-family:{SANS};font-size:12px;color:{INK2};">{esc(STRAPLINE)}</p>', "8px 0 0"))
        # Edition block
        parts.append(row(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background:{N05};border-bottom:3px solid {ACCENT};padding:20px 18px 18px;">'
            f'{kicker("This week in")}'
            f'<p style="margin:4px 0 0;font-family:{SERIF};font-size:36px;line-height:1.05;color:{INK};font-weight:bold;">{esc(city)}</p>'
            f'<p style="margin:6px 0 0;font-family:{SERIF};font-style:italic;font-size:16px;color:{INK2};">New businesses formed {fmt_date(dates[0])} to {fmt_date(dates[-1])}</p>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-top:16px;"><tr>'
            f'<td style="padding-right:28px;"><p style="margin:0;font-family:{SERIF};font-size:28px;font-weight:bold;color:{INK};">{filed}</p>{kicker("Filed")}</td>'
            f'<td style="padding-right:28px;"><p style="margin:0;font-family:{SERIF};font-size:28px;font-weight:bold;color:{INK};">{cut}</p>{kicker("Cut")}</td>'
            f'<td><p style="margin:0;font-family:{SERIF};font-size:28px;font-weight:bold;color:{ACCENT};">{kept}</p>{kicker("Worth reading")}</td>'
            f'</tr></table></td></tr></table>', "22px 0 0"))
        if kept < THIN_WEEK:
            parts.append(row(f'<p style="margin:0;background:#F7EEEC;padding:12px 16px;font-family:{SERIF};font-size:15px;color:{INK2};">A thin week in {esc(city)}. The state recorded {filed} new entities here; after removing holding companies, registered-agent addresses, and names that reveal nothing, {kept} were worth a broker\'s time. We would rather show a short list than pad it.</p>', "18px 0 0"))
        # Industries
        for ind in INDUSTRIES:
            entries = groups.get(ind)
            if not entries:
                continue
            shown = [rc for rc in entries if rc[0]["entityid"] in full_ids]
            rest = [rc for rc in entries if rc[0]["entityid"] not in full_ids]
            parts.append(row(f'<div style="border-bottom:1px solid {RULE};padding-bottom:6px;">{kicker(f"{esc(ind)} · {len(entries)}", ACCENT)}</div>', "32px 0 0"))
            parts.append('<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">' + "".join(entry_html(r, c) for r, c in shown) + '</table></td></tr>')
            if rest and compact:
                parts.append(row(f'<p style="margin:0 0 4px;font-family:{SANS};font-size:11px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:{INK3};">Also this week · {len(rest)}</p>'
                                 + compact_block(rest), "14px 0 0"))
            elif rest:
                where = "in the full email" if sample_n is not None else "this week"
                parts.append(row(f'<p style="margin:0;font-family:{SANS};font-size:13px;color:{INK2};">and {len(rest)} more in {esc(ind.lower())}, {where}.</p>', "12px 0 0"))
        if not kept:
            parts.append(row(f'<p style="margin:0;font-family:{SERIF};font-style:italic;color:{INK3};">Nothing to report this week.</p>', "24px 0 0"))
        # Footer
        parts.append(row(
            f'<p style="margin:0 0 8px;font-family:{SANS};font-size:12px;line-height:1.6;color:{INK2};">Business records are published by the Colorado Secretary of State and are in the public domain. Industry and commentary are inferred from the business name by NewCo Brief and are labeled as inferred. City and ZIP only; no street addresses, owner names, or phone numbers.</p>'
            f'<p style="margin:0;font-family:{SANS};font-size:12px;line-height:1.6;color:{INK2};"><a href="{esc(page_url)}" style="color:{ACCENT};text-decoration:none;">{esc(city)} this week on newcobrief.com</a> &nbsp;·&nbsp; &copy; {date.today().year} NewCo Brief</p>',
            "40px 0 24px"))
        parts.append('</table>')
        return "".join(parts)

    if sample_n is not None:
        return subject, render(sample_n, compact=False)

    # Fit the budget, in order: everything in full; fewer full entries with the rest as one-liners;
    # as a last resort, drop the one-liners and show counts instead.
    def fits(b: str) -> bool:
        return len(b.encode()) <= EMAIL_BUDGET

    def largest(compact: bool) -> str:
        lo, hi, best = 0, len(order), render(0, compact)
        while lo <= hi:                       # binary search the most full entries that still fit
            mid = (lo + hi) // 2
            b = render(mid, compact)
            if fits(b):
                best, lo = b, mid + 1
            else:
                hi = mid - 1
        return best

    body = render(len(order))
    if not fits(body):
        body = largest(True)
    if not fits(body):
        body = largest(False)
    return subject, body


def preview_page(subject: str, body: str) -> str:
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(subject)}</title></head><body style="margin:0;padding:16px;background:#ffffff;">{body}</body></html>')


SAMPLE_CITY = "Denver"
SAMPLE_FULL = 6


def sample_page(subject: str, body: str, kept: int, root: str) -> str:
    """docs/sample/: the current city email as it goes out Monday, cut to the first few entries."""
    email = body.replace("<!-- buttondown-editor-mode: plaintext -->", "")
    intro = (f'<main class="prose"><h1>A sample issue</h1>'
             f'<p>This is the {esc(SAMPLE_CITY)} edition for the week of {esc(WEEK["span"])}, as it goes out on Monday, cut to the first '
             f'{SAMPLE_FULL} entries. Subscribers get all {kept}, in the same form, every Monday morning. '
             f'<a href="{root}#top">One city is free.</a></p>'
             f'<p class="kicker" style="margin-top:28px">Subject line</p><p style="margin:4px 0 0;font-size:17px">{esc(subject)}</p>'
             f'<div class="sample-email">{email}</div>'
             f'<p style="margin-top:28px"><a href="{root}#top">Get {esc(SAMPLE_CITY)} or any other city by email, free &rarr;</a></p></main>')
    return page(f"Sample issue — {SITE_NAME}", intro, root, desc=f"What the Monday email looks like: the {SAMPLE_CITY} edition, first {SAMPLE_FULL} entries.")


def build_all(only_city: str | None = None) -> dict:
    files = sorted(f for f in FILTERED_DIR.glob("*.json") if not f.name.endswith("-dropped.json"))
    rows = json.loads(files[-1].read_text())
    raw = json.loads((RAW_DIR / files[-1].name).read_text()) if (RAW_DIR / files[-1].name).exists() else rows
    cache = json.loads(CLASSIFIED_FILE.read_text()) if CLASSIFIED_FILE.exists() else {}
    EMAIL_DIR.mkdir(exist_ok=True)
    dates = sorted(r["entityformdate"][:10] for r in rows) or [date.today().isoformat()]
    WEEK["span"], WEEK["next_send"] = span_label(dates[0], dates[-1]), next_monday(date.today()).strftime("%B %-d")
    manifest = {}
    for city in LAUNCH_CITIES:
        if only_city and city.lower() != only_city.lower():
            continue
        crows = [r for r in rows if (r.get("principalcity") or "").upper() == city.upper()]
        filed = sum(1 for r in raw if (r.get("principalcity") or "").upper() == city.upper())
        subject, body = city_email(city, crows, filed, cache)
        (EMAIL_DIR / f"{slug(city)}.html").write_text(preview_page(subject, body))
        manifest[city] = {"tag": slug(city), "subject": subject, "body": body, "bytes": len(body.encode()),
                          "worth_reading": sum(1 for r in crows if worth_reading(cache.get(r["entityid"])))}
        print(f"{city:17} {manifest[city]['worth_reading']:4} worth reading  {manifest[city]['bytes']//1000:3} KB  {subject}")
    (EMAIL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1))
    if not only_city or only_city.lower() == SAMPLE_CITY.lower():
        crows = [r for r in rows if (r.get("principalcity") or "").upper() == SAMPLE_CITY.upper()]
        filed = sum(1 for r in raw if (r.get("principalcity") or "").upper() == SAMPLE_CITY.upper())
        subject, body = city_email(SAMPLE_CITY, crows, filed, cache, sample_n=SAMPLE_FULL)
        (SITE_DIR / "sample").mkdir(exist_ok=True)
        (SITE_DIR / "sample" / "index.html").write_text(sample_page(subject, body, manifest[SAMPLE_CITY]["worth_reading"], "../"))
        print(f"Wrote sample issue to {SITE_DIR / 'sample'}")
    print(f"Wrote {len(manifest)} emails to {EMAIL_DIR}")
    return manifest


if __name__ == "__main__":
    build_all(sys.argv[sys.argv.index("--city") + 1] if "--city" in sys.argv else None)
