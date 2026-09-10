"""Settings shared by every pipeline step. Edit here, not in the scripts."""
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
FILTERED_DIR = DATA_DIR / "filtered"
SAMPLE_DIR = DATA_DIR / "sample"
CLASSIFIED_FILE = DATA_DIR / "classified.json"   # cache of every name Claude has classified

# Colorado Secretary of State, "Business Entities in Colorado", public domain.
DATASET_URL = "https://data.colorado.gov/resource/4ykn-tg5h.json"
STATE_RECORD_URL = "https://www.coloradosos.gov/biz/BusinessEntityDetail.do?quitButtonDestination=BusinessEntityResults&fileId={entityid}"

# How many days back to pull on each run. 7 for the weekly brief; the site shows the last 7.
DAYS_BACK = 7

# Launch cities. Matching is case-insensitive on the principal city field.
LAUNCH_CITIES = [
    "Denver", "Colorado Springs", "Aurora", "Fort Collins", "Boulder",
    "Lakewood", "Littleton", "Pueblo", "Arvada", "Thornton",
]

# Fixed industry list. Claude must pick from this list, nothing else.
INDUSTRIES = [
    "Construction and trades",
    "Home and property services",        # cleaning, landscaping, handyman, pest control
    "Restaurants and food",
    "Retail",
    "Professional services",             # consulting, marketing, legal, accounting, staffing
    "Health and medical",
    "Beauty and personal care",
    "Fitness, sports and recreation",
    "Transportation and logistics",      # trucking, moving, delivery, dispatch
    "Automotive",
    "Technology and software",
    "Manufacturing",
    "Agriculture and animals",
    "Arts, media and entertainment",
    "Education and childcare",
    "Finance and insurance",
    "Hospitality, travel and events",
    "Real estate and property",          # most of these are filtered out before Claude sees them
    "Nonprofit and community",
    "Other",
    "Not inferable",
]

# What counts as "worth reading" on the site and in the email. Low-confidence guesses
# ("Cloud Haven LLC -> cloud services") are listed plainly with the not-inferable names instead.
# Decided 2026-09-10 after reviewer feedback: Denver went from 259 to 172 of 542 filed.
LISTED_CONFIDENCE = ("high", "medium")


def worth_reading(c: dict) -> bool:
    """True when a classified entry gets a full entry with industry and commentary."""
    return bool(c) and c["operating"] and c["industry"] != "Not inferable" and c["confidence"] in LISTED_CONFIDENCE


# Claude settings
MODEL = "claude-opus-5"
BATCH_SIZE = 40          # names per request
EFFORT = "medium"


def load_env() -> None:
    """Read pipeline/.env (KEY=value lines) into the environment if the file exists.
    Keeps the API key out of the code and out of git."""
    import os
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


ENTITY_TYPE_LABELS = {
    "DLLC": "Colorado LLC", "DPC": "Colorado corporation", "DNC": "Colorado nonprofit",
    "DLLP": "Colorado LLP", "DLP": "Colorado LP", "DLLLP": "Colorado LLLP",
    "DCOOP": "Colorado cooperative", "DPCA": "Colorado professional corp.",
    "FLLC": "Out-of-state LLC", "FPC": "Out-of-state corporation", "FNC": "Out-of-state nonprofit",
    "FLP": "Out-of-state LP", "FLLP": "Out-of-state LLP",
}
