"""Step 1. Pull the last DAYS_BACK days of new Colorado entities and save the raw rows.

Runs on plain Python 3 with no extra packages. Usage:
    python3 pipeline/fetch.py
Writes data/raw/YYYY-MM-DD.json (today's date) and prints a count.
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

from config import DATASET_URL, DAYS_BACK, RAW_DIR

FIELDS = (
    "entityid,entityname,principalcity,principalstate,principalzipcode,principaladdress1,"
    "entitytype,entitystatus,jurisdictonofformation,entityformdate,"
    "agentorganizationname,agentfirstname,agentlastname,agentprincipaladdress1,agentprincipalcity"
)


def fetch_since(since: date) -> list:
    rows, offset, page = [], 0, 5000
    while True:
        params = {
            "$select": FIELDS,
            "$where": f"entityformdate >= '{since.isoformat()}T00:00:00' AND principalstate = 'CO'",
            "$order": "entityformdate DESC, entityid DESC",
            "$limit": page,
            "$offset": offset,
        }
        url = DATASET_URL + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=60) as resp:
            chunk = json.load(resp)
        rows.extend(chunk)
        if len(chunk) < page:
            return rows
        offset += page


def main() -> None:
    since = date.today() - timedelta(days=DAYS_BACK)
    rows = fetch_since(since)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / f"{date.today().isoformat()}.json"
    out.write_text(json.dumps(rows, indent=1))
    newest = max((r.get("entityformdate", "") for r in rows), default="")[:10]
    print(f"Fetched {len(rows)} Colorado entities formed since {since} (newest {newest}) -> {out.name}")


if __name__ == "__main__":
    sys.exit(main())
