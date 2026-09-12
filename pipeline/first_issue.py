"""Step 8 (nightly). Send this week's issue to anyone who subscribed since the last run, so a new
subscriber gets their city's list overnight instead of waiting for Monday.

How it works: reads data/email/manifest.json (built by build_email.py in run.py), lists Buttondown
subscribers, and picks the ones created on or after LAUNCH that are not yet in data/first-issue.json.
Each of them is given the Buttondown tag "first-issue"; then one REAL email per city is created and sent
to the audience "has the city tag AND has first-issue", with a short welcome block above the usual issue.
(Buttondown's draft-preview endpoint prefixes the subject with [PREVIEW], so a real send it is.)
The first-issue tag is stripped at the start of the NEXT run, not right after sending, because Buttondown
works out the audience a little after the send call. On Mondays nothing is sent (the real issue goes out
three hours later); new subscribers are just recorded so they are not sent a duplicate on Tuesday.
Free subscribers get their first city tag; paying subscribers get every city they hold.
Usage:
    python3 pipeline/first_issue.py                   # what the nightly workflow runs
    python3 pipeline/first_issue.py --dry-run         # list who would get what, send nothing
    python3 pipeline/first_issue.py --to you@x.com    # send only to that address, even if already sent
"""
import json
import os
import sys
from datetime import date, datetime, timezone

from build_email import EMAIL_DIR, build_all
from config import DATA_DIR, load_env
from send_email import FREE_TYPES, PAID_TYPES, call, tag_ids

STATE = DATA_DIR / "first-issue.json"
LAUNCH = "2026-09-11"      # subscribers created before this day are not back-filled
MARK = "first-issue"       # temporary tag that makes a subscriber part of tonight's audience
PLANS_URL = "https://newcobrief.com/plans/"

WELCOME_HTML = (
    '<tr><td style="padding:18px 0 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
    '<tr><td style="border-left:3px solid #17754C;padding:2px 0 2px 14px;">'
    '<p style="margin:0 0 8px;font-family:Georgia,serif;font-size:17px;line-height:1.45;color:#16241D;">'
    '<b>Welcome to NewCo Brief.</b> Here is this week\'s {city} list, so you don\'t wait for Monday.</p>'
    '<p style="margin:0 0 8px;font-family:Georgia,serif;font-size:15px;line-height:1.45;color:#4A5A52;">'
    'Every Monday from now on: the newly formed businesses in {city} worth reading, cut from the state\'s raw filings, '
    'sorted by trade, with a note on each and the state record linked. Monday\'s issue covers the whole week, so it '
    'will repeat some of these; after that, each Monday is new.</p>'
    '<p style="margin:0;font-family:Arial,sans-serif;font-size:13px;line-height:1.4;color:#4A5A52;">'
    f'One city is free. <a href="{PLANS_URL}" style="color:#17754C;font-weight:bold;">Statewide covers all ten Colorado cities, $49 a month</a></p>'
    '</td></tr></table></td></tr>'
)


def with_welcome(body: str, city: str) -> str:
    """Insert the welcome block right after the masthead row of the issue."""
    cut = body.find("</td></tr>")
    if cut < 0:
        return body
    cut += len("</td></tr>")
    return body[:cut] + WELCOME_HTML.format(city=city) + body[cut:]


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"sent": {}}


def subscribers() -> list:
    out, page = [], 1
    while True:
        data = call("GET", f"/subscribers?page={page}&page_size=100")
        out.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1
    return out


def set_mark(sub: dict, on: bool) -> None:
    tags = [t for t in (sub.get("tags") or []) if t != MARK]
    if on:
        tags.append(MARK)
    call("PATCH", f"/subscribers/{sub['id']}", {"tags": tags})


def main() -> None:
    load_env()
    if not os.environ.get("BUTTONDOWN_API_KEY"):
        sys.exit("BUTTONDOWN_API_KEY is not set. Add it to pipeline/.env (see pipeline/README.md).")
    dry = "--dry-run" in sys.argv
    only_to = sys.argv[sys.argv.index("--to") + 1].lower() if "--to" in sys.argv else None
    manifest_path = EMAIL_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else build_all()
    by_slug = {m["tag"]: m for m in manifest.values()}
    city_name = {m["tag"]: city for city, m in manifest.items()}

    state = load_state()
    ids = tag_ids()
    if MARK not in ids:
        ids[MARK] = call("POST", "/tags", {"name": MARK, "color": "#7B8A82",
                                           "description": "Temporary: gets tonight's first issue"})["id"]
    monday = datetime.now(timezone.utc).weekday() == 0
    today = date.today().isoformat()

    subs = subscribers()
    # Last night's audience is done with; take the mark off before building tonight's.
    if not dry:
        for s in subs:
            if MARK in (s.get("tags") or []):
                set_mark(s, False)
                s["tags"] = [t for t in s["tags"] if t != MARK]

    todo = {}   # city slug -> [subscriber dicts]
    for s in subs:
        kind = s.get("subscriber_type") or s.get("type")
        if kind not in FREE_TYPES | PAID_TYPES:
            continue
        email = s["email_address"].lower()
        if only_to and email != only_to:
            continue
        if not only_to and (s["id"] in state["sent"] or (s.get("creation_date") or "")[:10] < LAUNCH):
            continue
        cities = [t for t in (s.get("tags") or []) if t in by_slug]
        if not cities:
            continue
        if kind in FREE_TYPES:
            cities = cities[:1]
        for c in cities:
            todo.setdefault(c, []).append(s)

    if not todo:
        print("No new subscribers since the last run.")
        return
    for c, group in todo.items():
        who = ", ".join(s["email_address"] for s in group)
        if dry:
            print(f"{c:17} would send to {who}")
            continue
        if monday and not only_to:
            print(f"{c:17} Monday: skipping {who} (the Monday issue goes out this morning)")
        else:
            for s in group:
                set_mark(s, True)
            m = by_slug[c]
            email = call("POST", "/emails", {
                "subject": m["subject"], "body": with_welcome(m["body"], city_name[c]),
                "status": "draft", "archival_mode": "disabled",
                "filters": {"predicate": "and", "groups": [], "filters": [
                    {"field": "subscriber.tags", "operator": "contains", "value": ids[c]},
                    {"field": "subscriber.tags", "operator": "contains", "value": ids[MARK]}]}})
            call("PATCH", f"/emails/{email['id']}", {"status": "about_to_send"}, live=True)
            print(f"{c:17} sent first issue to {who}  (email {email['id']})")
        for s in group:
            state["sent"][s["id"]] = today
    if not dry:
        STATE.write_text(json.dumps(state, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
