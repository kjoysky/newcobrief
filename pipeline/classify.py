"""Step 3. Ask Claude to infer an industry and write one line for each surviving business.

Results are cached in data/classified.json by entity id, so re-running only sends new names.
Needs the anthropic package (see README) and an API key in pipeline/.env.
Usage:
    python pipeline/classify.py            # newest file in data/filtered
    python pipeline/classify.py --limit 40 # first batch only, for a cheap test
"""
import json
import sys

import anthropic

from config import (BATCH_SIZE, CLASSIFIED_FILE, EFFORT, ENTITY_TYPE_LABELS, FILTERED_DIR,
                    INDUSTRIES, MODEL, load_env)

SYSTEM = f"""You are the editor of a weekly brief about newly formed businesses in Colorado. The readers are commercial insurance brokers who prospect new businesses. All you have for each business is the name the founders filed with the Secretary of State, the entity type, and the city.

For each business, decide:
- industry: exactly one value from this list: {json.dumps(INDUSTRIES)}. Use "Not inferable" when the name gives no real clue. Never guess a specific industry from a name that could be anything.
- detail: two to five words naming the specific line of work when the name shows it (for example "roofing", "mobile dog grooming", "food truck"). Empty string if not inferable.
- operating: true if this looks like a business that will sell goods or services; false if the name suggests a holding company, a property or investment vehicle, a family or estate entity, or a shell formed for one transaction.
- confidence: "high" when the name states the trade plainly, "medium" when it strongly suggests it, "low" when it is a reasonable reading of a vague name.
- note: one plain-English sentence, written for a commercial insurance broker, about what a business like this typically needs and when. Base it only on the industry and entity type. Do not invent facts about this particular company, do not mention owners, and do not repeat the business name. For "Not inferable" or non-operating entities, use an empty string.

Nothing you write will be presented as reported by the state. Everything is labeled as inferred from the name.

Return JSON matching the schema, one result per input, in the same order, with the same ids."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "industry": {"type": "string", "enum": INDUSTRIES},
                    "detail": {"type": "string"},
                    "operating": {"type": "boolean"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "note": {"type": "string"},
                },
                "required": ["id", "industry", "detail", "operating", "confidence", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def classify_batch(client: anthropic.Anthropic, rows: list) -> tuple:
    """Send one batch. Returns (results list, usage). Raises on API errors."""
    items = [{"id": r["entityid"], "name": r["entityname"],
              "entity_type": ENTITY_TYPE_LABELS.get(r.get("entitytype", ""), r.get("entitytype", "")),
              "city": (r.get("principalcity") or "").title()} for r in rows]
    kwargs = dict(
        model=MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": json.dumps(items)}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
    )
    try:
        # Server-side refusal fallback: if the model declines, the API re-runs on a fallback model.
        response = client.beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except anthropic.BadRequestError as e:
        if "fallback" not in str(e).lower():
            raise
        response = client.messages.create(**kwargs)
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise RuntimeError(f"Claude declined this batch: {detail}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Response cut off at max_tokens; lower BATCH_SIZE in config.py")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["results"], response.usage


def main() -> None:
    load_env()
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    files = sorted(f for f in FILTERED_DIR.glob("*.json") if not f.name.endswith("-dropped.json"))
    if not files:
        sys.exit("No filtered file found. Run filter.py first.")
    rows = json.loads(files[-1].read_text())
    cache = json.loads(CLASSIFIED_FILE.read_text()) if CLASSIFIED_FILE.exists() else {}
    todo = [r for r in rows if r["entityid"] not in cache]
    done = len(rows) - len(todo)
    if limit:
        todo = todo[:limit]
    print(f"{len(rows)} businesses in {files[-1].name}; {done} already classified; {len(todo)} to send")
    if not todo:
        return

    import os
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit("No API key found. Put ANTHROPIC_API_KEY=sk-ant-... in pipeline/.env (steps in pipeline/README.md).")
    client = anthropic.Anthropic()
    in_tok = out_tok = cached_tok = 0
    for i in range(0, len(todo), BATCH_SIZE):
        batch = todo[i:i + BATCH_SIZE]
        try:
            results, usage = classify_batch(client, batch)
        except anthropic.AuthenticationError:
            sys.exit("API key missing or invalid. Put ANTHROPIC_API_KEY=... in pipeline/.env (see README).")
        except anthropic.RateLimitError:
            sys.exit("Rate limited. Wait a minute and run again; finished batches are already saved.")
        except anthropic.APIStatusError as e:
            sys.exit(f"API error {e.status_code}: {e.message}. Finished batches are saved; run again.")
        except anthropic.APIConnectionError:
            sys.exit("Network error. Check the connection and run again.")
        by_id = {r["id"]: r for r in results}
        for r in batch:
            res = by_id.get(r["entityid"])
            if res:
                cache[r["entityid"]] = {k: res[k] for k in ("industry", "detail", "operating", "confidence", "note")}
        CLASSIFIED_FILE.write_text(json.dumps(cache, indent=1))
        in_tok += usage.input_tokens
        out_tok += usage.output_tokens
        cached_tok += getattr(usage, "cache_read_input_tokens", 0) or 0
        print(f"  batch {i // BATCH_SIZE + 1}: {len(results)} classified")

    # Claude Opus 5 list price: $5 per million input, $25 per million output; cache reads are cheaper.
    cost = in_tok / 1e6 * 5 + out_tok / 1e6 * 25
    print(f"Done. Tokens in {in_tok:,} (cache hits {cached_tok:,}), out {out_tok:,}. About ${cost:.2f}.")


if __name__ == "__main__":
    main()
