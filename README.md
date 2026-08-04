# seo_agents (standalone)

Standalone SEO content service for **one website**. A slimmed-down clone of the
`src/seo_agents/` module from `jg_agents`, running only two scheduled tasks:

- **write** — Google Sheet keyword → CrewAI article → Google Doc
- **publish** — Google Doc → WordPress (REST API)

No database. See [`CLAUDE.md`](CLAUDE.md) for architecture and [`DEPLOY.md`](DEPLOY.md)
for deploying to dev47.

## Quick start

```bash
uv sync
cp .env.example .env                      # fill in WP_*, SEO_SHEET_ID, GEMINI_API_KEY, OPENAI_API_KEY
cp /path/to/dashboard-gcloud.json env/    # Google service-account key (gitignored)

# manual one-shot runs
uv run python -m seo_agents.write_articles
uv run python -m seo_agents.publish_articles

# or run the scheduler (both tasks on interval)
uv run python scheduler.py --config crons.yaml
```

## Configuration

Everything site-specific is an environment variable (`.env`):

| Var | Meaning |
|---|---|
| `WP_URL` | Target WordPress site root (REST base = `{WP_URL}/wp-json/wp/v2`) |
| `WP_USERNAME` / `WP_PASSWORD` | WordPress user + **Application Password** |
| `SEO_SHEET_ID` | Google Sheet key of this site's "SEO Flow" control sheet |
| `SEO_MULTI_SHEET_ID` | Optional second "multi blog" flow (blank = off) |
| `GEMINI_API_KEY` | CrewAI agents + image generation |
| `OPENAI_API_KEY` | One writer agent (`gpt-4.1-mini`) |

## Tasks

| Task | Schedule | Does |
|---|---|---|
| `write_articles_task` | every 6 min | writes articles for rows marked `Write`, → `Review` |
| `publish_article_task` | every 7 min | publishes rows marked `Publish`, → `Done` |

Edit cadence in [`crons.yaml`](crons.yaml).

## Deploy

```bash
fab deploy    # git push + pull on dev47 + restart service
fab live      # tail logs/tasks.log on dev47
fab status    # systemctl --user status
```
