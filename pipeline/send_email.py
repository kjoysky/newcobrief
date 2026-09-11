"""Step 7. Push the Monday emails to Buttondown, one per city, to subscribers tagged with that city.

Safe by default: every email is created as a DRAFT in Buttondown (Emails page) for Kristina to open and
send. Pass --send to send them straight away; that is what the Monday workflow does once AUTO_SEND is on.
Needs BUTTONDOWN_API_KEY in pipeline/.env (local) or in the repo's Actions secrets.
Before building the audiences it enforces the free tier: a free subscriber (Buttondown type "regular")
keeps only their first city tag; paying subscribers (premium, gifted, trialed, unpaid) keep every city they
picked in the portal. Pass --no-enforce to skip that step.
Usage:
    python3 pipeline/send_email.py                 # drafts for every city
    python3 pipeline/send_email.py --city Denver   # one city
    python3 pipeline/send_email.py --send          # create and send
"""
import json
import os
import sys
import urllib.error
import urllib.request

from build_email import EMAIL_DIR, build_all
from config import load_env

API = "https://api.buttondown.com/v1"


def call(method: str, path: str, payload: dict | None = None, live: bool = False) -> dict:
    headers = {"Authorization": f"Token {os.environ['BUTTONDOWN_API_KEY']}", "Content-Type": "application/json"}
    if live:
        headers["X-Buttondown-Live-Dangerously"] = "true"   # required by Buttondown to send via the API
    req = urllib.request.Request(f"{API}{path}", method=method, headers=headers,
                                 data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Buttondown {method} {path} failed: {e.code} {e.read().decode()[:500]}")


def tag_ids() -> dict:
    """Buttondown filters want tag IDs, not names. Returns {name: id}, creating any missing city tag
    (named by city slug, the same value the website form posts) so the audience exists before anyone signs up."""
    from config import LAUNCH_CITIES
    from build_site import slug
    have = {t["name"]: t["id"] for t in call("GET", "/tags?page_size=100").get("results", [])}
    for city in LAUNCH_CITIES:
        name = slug(city)
        if name not in have:
            have[name] = call("POST", "/tags", {"name": name, "color": "#17754C",
                                                "description": f"Gets the Monday brief for {city}"})["id"]
            print(f"created tag {name}")
    return have


# Buttondown subscriber types that mean "has paid access" (docs.buttondown.com/api-subscribers-type).
PAID_TYPES = {"premium", "gifted", "trialed", "unpaid"}
FREE_TYPES = {"regular"}


def enforce_free_tier(city_tags: set) -> int:
    """The free plan is one city. Buttondown's portal lets any subscriber add tags, so before each send trim
    free subscribers to the first city tag they hold (non-city tags are left alone). Returns how many changed."""
    changed, page = 0, 1
    while True:
        data = call("GET", f"/subscribers?type=regular&page={page}&page_size=100")
        for sub in data.get("results", []):
            if (sub.get("subscriber_type") or sub.get("type")) not in FREE_TYPES:
                continue
            tags = sub.get("tags") or []
            cities = [t for t in tags if t in city_tags]
            if len(cities) > 1:
                keep = [t for t in tags if t not in city_tags] + cities[:1]
                call("PATCH", f"/subscribers/{sub['id']}", {"tags": keep})
                changed += 1
                print(f"free tier: {sub['email_address']} kept {cities[0]}, dropped {', '.join(cities[1:])}")
        if not data.get("next"):
            break
        page += 1
    return changed


def main() -> None:
    load_env()
    if not os.environ.get("BUTTONDOWN_API_KEY"):
        sys.exit("BUTTONDOWN_API_KEY is not set. Add it to pipeline/.env (see pipeline/README.md).")
    send = "--send" in sys.argv
    only = sys.argv[sys.argv.index("--city") + 1] if "--city" in sys.argv else None
    manifest = build_all(only) if "--no-build" not in sys.argv else json.loads((EMAIL_DIR / "manifest.json").read_text())

    ids = tag_ids()
    if "--no-enforce" not in sys.argv:
        n = enforce_free_tier(set(ids))
        print(f"free tier enforced: {n} subscriber(s) trimmed to one city")
    results = {}
    for city, m in manifest.items():
        if only and city.lower() != only.lower():
            continue
        # Audience = subscribers whose tags contain this city (Buttondown API 2026-04-01 "filters" shape).
        # archival_mode "disabled": not put in Buttondown's public archive; the city page on the site is the archive.
        email = call("POST", "/emails", {
            "subject": m["subject"], "body": m["body"], "status": "draft", "archival_mode": "disabled",
            "filters": {"predicate": "and", "groups": [],
                        "filters": [{"field": "subscriber.tags", "operator": "contains", "value": ids[m["tag"]]}]}})
        eid = email["id"]
        if send:
            call("PATCH", f"/emails/{eid}", {"status": "about_to_send"}, live=True)
        results[city] = {"id": eid, "status": "about_to_send" if send else "draft"}
        print(f"{city:17} {'SENT' if send else 'draft'}  tag={m['tag']}  id={eid}")
    (EMAIL_DIR / "last-send.json").write_text(json.dumps(results, indent=1))
    if not send:
        print("\nDrafts are on the Buttondown Emails page: https://buttondown.com/emails. Open one, check it, click Send.")


if __name__ == "__main__":
    main()
