"""Step 4. Write one Markdown sample page per launch city for Kristina's review.

Usage:
    python3 pipeline/build_sample.py
Writes data/sample/<city>.md and data/sample/00-summary.md
"""
import json
from collections import Counter, defaultdict
from datetime import date

from config import (CLASSIFIED_FILE, ENTITY_TYPE_LABELS, FILTERED_DIR, INDUSTRIES, LAUNCH_CITIES,
                    RAW_DIR, SAMPLE_DIR, STATE_RECORD_URL, worth_reading)

CONF_ORDER = {"high": 0, "medium": 1, "low": 2}


def fmt_date(s: str) -> str:
    y, m, d = s[:10].split("-")
    return date(int(y), int(m), int(d)).strftime("%b %-d")


def main() -> None:
    files = sorted(f for f in FILTERED_DIR.glob("*.json") if not f.name.endswith("-dropped.json"))
    rows = json.loads(files[-1].read_text())
    cache = json.loads(CLASSIFIED_FILE.read_text()) if CLASSIFIED_FILE.exists() else {}
    raw = json.loads((RAW_DIR / files[-1].name).read_text()) if (RAW_DIR / files[-1].name).exists() else rows
    filed_counts = Counter((r.get("principalcity") or "").upper() for r in raw)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    summary = ["# Sample week summary", "", f"Source file: {files[-1].name}", "",
               "| City | Filed | Cut | Worth reading | Trade not inferable | Unclassified |", "|---|---|---|---|---|---|"]

    for city in LAUNCH_CITIES:
        crows = [r for r in rows if (r.get("principalcity") or "").upper() == city.upper()]
        groups, aside, unknown, unclassified = defaultdict(list), [], [], []
        for r in crows:
            c = cache.get(r["entityid"])
            if not c:
                unclassified.append(r)
            elif not c["operating"]:
                aside.append((r, c))
            elif not worth_reading(c):
                unknown.append((r, c))
            else:
                groups[c["industry"]].append((r, c))
        listed = sum(len(v) for v in groups.values())
        filed = filed_counts.get(city.upper(), 0)
        summary.append(f"| {city} | {filed} | {filed - listed} | {listed} | {len(unknown)} | {len(unclassified)} |")

        dates = sorted(r["entityformdate"][:10] for r in crows)
        span = f"{fmt_date(dates[0])} to {fmt_date(dates[-1])}" if dates else ""
        filed = filed_counts.get(city.upper(), 0)
        out = [f"# New businesses in {city}", f"*{span}*", "",
               f"**{filed} filed · {filed - listed} cut · {listed} worth reading**  ", "Industries are inferred from the business name and labeled as inferred.", ""]
        for ind in INDUSTRIES:
            entries = groups.get(ind)
            if not entries:
                continue
            out += [f"## {ind} ({len(entries)})", ""]
            for r, c in sorted(entries, key=lambda rc: (CONF_ORDER[rc[1]["confidence"]], rc[0]["entityname"].lower())):
                detail = f"{c['detail']} (inferred)" if c["detail"] else "(inferred)"
                out += [f"**{r['entityname']}**  ",
                        f"{detail} · {city} {r.get('principalzipcode', '')} · "
                        f"{ENTITY_TYPE_LABELS.get(r.get('entitytype', ''), r.get('entitytype', ''))} · Filed {fmt_date(r['entityformdate'])} · confidence {c['confidence']}  "]
                if c["note"]:
                    out.append(f"{c['note']}  ")
                out += [f"[State record]({STATE_RECORD_URL.format(entityid=r['entityid'])}) · Source: Colorado Secretary of State", ""]
        if unknown:
            out += [f"## Trade not inferable from the name ({len(unknown)})", "", "*Real filings the name says nothing about. Listed so nothing real is quietly dropped.*", ""]
            out += [f"- {r['entityname']} · {ENTITY_TYPE_LABELS.get(r.get('entitytype', ''), '')} · {r.get('principalzipcode', '')} · Filed {fmt_date(r['entityformdate'])}" for r, _ in unknown] + [""]
        if aside:
            out += [f"## Set aside as not an operating business ({len(aside)}) — for review only, not published", ""]
            out += [f"- {r['entityname']}" for r, _ in aside] + [""]
        if unclassified:
            out += [f"## Not yet classified ({len(unclassified)}) — run classify.py", ""]
            out += [f"- {r['entityname']}" for r in unclassified] + [""]
        (SAMPLE_DIR / f"{city.lower().replace(' ', '-')}.md").write_text("\n".join(out))

    ind_counts = Counter(c["industry"] for c in cache.values())
    summary += ["", "## Industries across all classified names", ""] + [f"- {k}: {v}" for k, v in ind_counts.most_common()]
    (SAMPLE_DIR / "00-summary.md").write_text("\n".join(summary) + "\n")
    print("\n".join(summary[:len(LAUNCH_CITIES) + 6]))
    print(f"Wrote {len(LAUNCH_CITIES)} city pages to {SAMPLE_DIR}")


if __name__ == "__main__":
    main()
