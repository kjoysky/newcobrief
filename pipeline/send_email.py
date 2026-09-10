"""Step 7. Push the Monday emails to Buttondown, one per city, to subscribers tagged with that city.

Safe by default: every email is created as a DRAFT in Buttondown (Emails page) for Kristina to open and
send. Pass --send to send them straight away; that is what the Monday workflow does once AUTO_SEND is on.
Needs BUTTONDOWN_API_KEY in pipeline/.env (local) or in the repo's Actions secrets.
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


def main() -> None:
    load_env()
    if not os.environ.get("BUTTONDOWN_API_KEY"):
        sys.exit("BUTTONDOWN_API_KEY is not set. Add it to pipeline/.env (see pipeline/README.md).")
    send = "--send" in sys.argv
    only = sys.argv[sys.argv.index("--city") + 1] if "--city" in sys.argv else None
    manifest = build_all(only) if "--no-build" not in sys.argv else json.loads((EMAIL_DIR / "manifest.json").read_text())

    results = {}
    for city, m in manifest.items():
        if only and city.lower() != only.lower():
            continue
        # email_type "private": not added to Buttondown's public archive; the city page on the site is the archive.
        email = call("POST", "/emails", {"subject": m["subject"], "body": m["body"], "status": "draft",
                                        "email_type": "private", "included_tags": [m["tag"]]})
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
