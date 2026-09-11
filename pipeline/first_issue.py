"""Step 8 (nightly). Send this week's issue to anyone who subscribed since the last run, so a new
subscriber gets their city's list overnight instead of waiting for Monday.

How it works: reads data/email/manifest.json (built by build_email.py in run.py), lists Buttondown
subscribers, picks the ones created on or after LAUNCH that are not yet in data/first-issue.json, and for
each city keeps ONE standing draft in Buttondown (subject/body refreshed each night, audience = that city's
tag) and sends that draft to just those subscribers with Buttondown's send-draft endpoint. The draft itself
is never published. On Mondays nothing is sent (the real issue goes out three hours later); new
subscribers are just recorded so they are not sent a duplicate on Tuesday.
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
from config import DATA_DIR, LAUNCH_CITIES, load_env
from send_email import FREE_TYPES, PAID_TYPES, call, tag_ids

STATE = DATA_DIR / "first-issue.json"
LAUNCH = "2026-09-11"   # subscribers created before this day are not back-filled


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"sent": {}, "drafts": {}}


def subscribers() -> list:
    out, page = [], 1
    while True:
        data = call("GET", f"/subscribers?page={page}&page_size=100")
        out.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1
    return out


def standing_draft(state: dict, city_slug: str, m: dict, tag_id: str) -> str:
    """The one draft per city that first issues are sent from. Reused night after night; body refreshed."""
    eid = state["drafts"].get(city_slug)
    payload = {"subject": m["subject"], "body": m["body"]}
    if eid:
        try:
            current = call("GET", f"/emails/{eid}")
        except SystemExit:
            current = None
        if current and current.get("status") == "draft":
            call("PATCH", f"/emails/{eid}", payload)
            return eid
    email = call("POST", "/emails", {
        **payload, "status": "draft", "archival_mode": "disabled",
        "filters": {"predicate": "and", "groups": [],
                    "filters": [{"field": "subscriber.tags", "operator": "contains", "value": tag_id}]}})
    state["drafts"][city_slug] = email["id"]
    return email["id"]


def main() -> None:
    load_env()
    if not os.environ.get("BUTTONDOWN_API_KEY"):
        sys.exit("BUTTONDOWN_API_KEY is not set. Add it to pipeline/.env (see pipeline/README.md).")
    dry = "--dry-run" in sys.argv
    only_to = sys.argv[sys.argv.index("--to") + 1].lower() if "--to" in sys.argv else None
    manifest_path = EMAIL_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else build_all()
    by_slug = {m["tag"]: m for m in manifest.values()}

    state = load_state()
    ids = tag_ids()
    city_slugs = set(by_slug)
    monday = datetime.now(timezone.utc).weekday() == 0
    today = date.today().isoformat()

    todo = {}   # city slug -> [(subscriber id, email)]
    for s in subscribers():
        kind = s.get("subscriber_type") or s.get("type")
        if kind not in FREE_TYPES | PAID_TYPES:
            continue
        email = s["email_address"].lower()
        if only_to and email != only_to:
            continue
        if not only_to and (s["id"] in state["sent"] or (s.get("creation_date") or "")[:10] < LAUNCH):
            continue
        cities = [t for t in (s.get("tags") or []) if t in city_slugs]
        if not cities:
            continue
        if kind in FREE_TYPES:
            cities = cities[:1]
        for c in cities:
            todo.setdefault(c, []).append((s["id"], email))

    if not todo:
        print("No new subscribers since the last run.")
        return
    for c, subs in todo.items():
        who = ", ".join(e for _, e in subs)
        if dry:
            print(f"{c:17} would send to {who}")
            continue
        if monday and not only_to:
            print(f"{c:17} Monday: skipping {who} (the Monday issue goes out this morning)")
        else:
            eid = standing_draft(state, c, by_slug[c], ids[c])
            call("POST", f"/emails/{eid}/send-draft", {"subscribers": [sid for sid, _ in subs]}, live=True)
            print(f"{c:17} sent first issue to {who}  (draft {eid})")
        for sid, _ in subs:
            state["sent"][sid] = today
    if not dry:
        STATE.write_text(json.dumps(state, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
