"""Step 2. Remove the noise. Keep only entities in launch cities that look like real operating businesses.

Every dropped row is kept in a separate file with the reason, so Kristina can review the rules.
Usage:
    python3 pipeline/filter.py            # uses the newest file in data/raw
Writes data/filtered/YYYY-MM-DD.json and data/filtered/YYYY-MM-DD-dropped.json
"""
import json
import re
import sys
from collections import Counter

from config import FILTERED_DIR, LAUNCH_CITIES, RAW_DIR, SHARED_ADDRESS_MIN

CITY_SET = {c.upper() for c in LAUNCH_CITIES}

# Registered-agent and formation companies filing their own entities. They are the ones selling to
# new businesses, not prospects. Reviewer feedback 2026-09-10.
AGENT_NAME_RE = re.compile(r"\b(registered|resident|statutory|business)\s+agents?\b|\bregistered agent\b", re.I)

# Street normalisation for address comparison: "1500 N Grant St Ste R" and "1500 N GRANT ST" are the
# same building. Everything from a unit marker on is dropped; common suffixes are shortened.
UNIT_RE = re.compile(r"\b(ste|suite|unit|apt|apartment|fl|floor|rm|room|pmb|box|bldg|building|#)\b.*$", re.I)
STREET_WORDS = {"street": "st", "avenue": "ave", "boulevard": "blvd", "drive": "dr", "road": "rd", "lane": "ln",
                "court": "ct", "place": "pl", "parkway": "pkwy", "circle": "cir", "highway": "hwy", "north": "n",
                "south": "s", "east": "e", "west": "w", "terrace": "ter", "trail": "trl", "way": "way"}


def norm_street(addr: str) -> str:
    """Lower-case street number + name, without unit, punctuation, or long-form suffixes."""
    a = re.sub(r"[.,]", " ", (addr or "").lower())
    a = re.sub(r"#.*$", "", a)
    a = UNIT_RE.sub("", a)
    words = [STREET_WORDS.get(w, w) for w in a.split()]
    while len(words) > 2 and words[-1].isdigit():   # trailing mailbox numbers: "1500 n grant st 5656"
        words.pop()
    return " ".join(words)

# Name patterns that almost always mean a holding, property, or one-transaction entity.
# Kept deliberately narrow: ambiguous words (family, capital, ventures, estate) are left for
# Claude to judge in classify.py, which flags non-operating entities. Reviewed weekly.
PASSIVE_PATTERNS = [
    r"\bholdings?\b",
    r"\bpropert(y|ies)\b(?!\s+(services?|management|maintenance|care|solutions|group|preservation|inspections?))",
    r"\brealty\b", r"\breal estate\b", r"\brentals?\b(?!\s+(equipment|tools?|services?))", r"\bapartments?\b",
    r"\btrust\b", r"\binvestments?\b", r"\bacquisitions?\b", r"\bportfolio\b",
    r"\bseries\b",                     # series LLC cells
    # looks like a street address: "1119 Sarah St LLC", "4200 E Colfax Ave LLC"
    r"\b\d{1,5}\s+(n|s|e|w|north|south|east|west)?\.?\s*\w+\s+(st|street|ave|avenue|blvd|dr|drive|rd|road|ln|lane|ct|court|way|pl|place|pkwy|cir|circle)\b",
]
PASSIVE_RE = [re.compile(p, re.I) for p in PASSIVE_PATTERNS]

# Commercial registered-agent services. If the agent is one of these AND the principal address
# is the agent's address, the city tells us nothing about where the business really is.
AGENT_SERVICES = [
    "registered agent", "registered agents", "northwest registered agent", "legalzoom",
    "zenbusiness", "incfile", "bizee", "harvard business services", "ct corporation",
    "corporation service company", "csc", "incorp services", "cogency global",
    "united states corporation agents", "corporate creations", "national registered agents",
    "paracorp", "vcorp", "business filings", "sundoc", "doola", "firstbase", "stripe atlas",
    "clerky", "swyft filings", "mycorporation", "rocket lawyer", "tailor brands",
]


def drop_reason(row: dict, address_counts: Counter | None = None) -> str:
    """Return '' to keep the row, or a short reason to drop it."""
    city = (row.get("principalcity") or "").strip().upper()
    if city not in CITY_SET:
        return "not a launch city"
    if (row.get("entitystatus") or "").lower() not in ("good standing", "exists", ""):
        return "status not good standing"
    name = row.get("entityname") or ""
    if AGENT_NAME_RE.search(name):
        return "registered-agent company"
    for rx in PASSIVE_RE:
        if rx.search(name):
            return f"passive name pattern ({rx.pattern})"
    street = norm_street(row.get("principaladdress1"))
    agent_org = (row.get("agentorganizationname") or "").lower()
    if agent_org and any(s in agent_org for s in AGENT_SERVICES):
        if street and street == norm_street(row.get("agentprincipaladdress1")):
            return "registered-agent service address"
    # A mailbox shared by many filings in one week is a registered-agent or virtual-office address,
    # whatever the agent field says. The business is not really in that city.
    if address_counts and street and address_counts[street] >= SHARED_ADDRESS_MIN:
        return f"shared mailbox address ({address_counts[street]} filings this week)"
    return ""


def main() -> None:
    raw_files = sorted(RAW_DIR.glob("*.json"))
    if not raw_files:
        sys.exit("No raw file found. Run fetch.py first.")
    src = raw_files[-1]
    rows = json.loads(src.read_text())
    kept, dropped, reasons = [], [], Counter()
    address_counts = Counter(norm_street(r.get("principaladdress1")) for r in rows)
    for r in rows:
        why = drop_reason(r, address_counts)
        if why:
            reasons[why.split(" (")[0]] += 1
            dropped.append({"entityid": r.get("entityid"), "entityname": r.get("entityname"),
                            "principalcity": r.get("principalcity"), "reason": why})
        else:
            kept.append(r)
    FILTERED_DIR.mkdir(parents=True, exist_ok=True)
    (FILTERED_DIR / src.name).write_text(json.dumps(kept, indent=1))
    (FILTERED_DIR / src.name.replace(".json", "-dropped.json")).write_text(json.dumps(dropped, indent=1))

    print(f"{len(rows)} raw -> {len(kept)} kept, {len(dropped)} dropped")
    for why, n in reasons.most_common():
        print(f"  dropped, {why}: {n}")
    by_city = Counter((r.get("principalcity") or "").title() for r in kept)
    print("Kept per launch city:")
    for c in LAUNCH_CITIES:
        print(f"  {c:17s} {by_city.get(c, 0)}")


if __name__ == "__main__":
    main()
