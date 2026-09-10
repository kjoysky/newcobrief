# NewCo Brief

New businesses. Earlier opportunities.

A weekly brief of newly formed businesses, filtered to real operating companies and tagged by industry, for commercial insurance brokers and other people who sell to new companies. Colorado first.

- `pipeline/` fetches the public Colorado Secretary of State feed, filters the noise, classifies names with Claude, and generates the site.
- `docs/` is the generated static site, served by GitHub Pages.
- `data/classified.json` caches every name already classified so re-runs only send new ones.

Business records are published by the Colorado Secretary of State and are in the public domain. Industry and commentary are inferred from the business name and labeled as inferred. City and ZIP only; no street addresses, owner names, or phone numbers are published.
