# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this is

**seo_agents (standalone)** is a slimmed-down clone of the `src/seo_agents/` module
from the `jg_agents` project (sibling directory `../jg_agents`). It runs exactly two
scheduled tasks for **one website**:

1. **`write_articles_task`** — reads a Google Sheet ("SEO Flow"), and for each keyword
   row marked `Write`, runs the CrewAI pipeline (research → outline → write → SEO edit →
   image prompts) to produce a full article, writes it back into a per-keyword worksheet,
   then renders it into a Google Doc. Sets the row status to `Review`.
2. **`publish_article_task`** — for rows marked `Publish` (with a Google Doc), converts the
   doc to HTML and publishes it to WordPress via the REST API. Sets status to `Done`.

It was split out so it can be maintained and deployed independently of `jg_agents`.

## Why it's separate / how it differs from jg_agents

The original module was entangled with the jg_agents database (Tortoise ORM / MySQL),
`settings.py`, and `utils/`. This clone removes all of that:

| Concern | jg_agents original | Here |
|---|---|---|
| Package path | `src.seo_agents.*` | top-level `seo_agents.*` |
| Task logging | `utils.task_logger` → MySQL `task_execution_log` | `seo_agents.task_logger` → **file** (`logs/tasks.log`) |
| DB | `models.db.init_db/close_db` (MySQL) | **none** — publish uses WP REST only |
| Settings | large `settings.py` | minimal root `settings.py` (just `BASE_DIR` + env) |
| Scheduler | `scheduler.py` + `crons/seo.yaml` (also inits DB + ES) | lean `scheduler.py` + `crons.yaml` (no DB/ES) |
| Target site | hardcoded jobsgo sheet IDs | **env-configurable** (`SEO_SHEET_ID`, `WP_URL`, …) |
| `gen_links_task` | present | **omitted** (it needs the jg_agents DB/models) |

**Do not re-introduce `models`/`utils`/`init_db` imports here** — keeping this DB-free is
the whole point.

## Layout

```
seo_agents/                 (project root = /var/www/seo_agents on dev47)
├── scheduler.py            # APScheduler entrypoint; python scheduler.py --config crons.yaml
├── crons.yaml              # the 2 interval jobs
├── settings.py             # minimal: BASE_DIR + env loading (image_generator needs BASE_DIR)
├── pyproject.toml          # trimmed dependency set (uv)
├── fabfile.py              # fab deploy / live / restart / status  → dev47
├── seo_agents.service      # systemd --user unit
├── .env                    # secrets (gitignored) — copy from .env.example
├── env/dashboard-gcloud.json   # Google service-account key (gitignored — copy in manually)
├── logs/                   # tasks.log + publish_articles.log (gitignored)
├── images/                 # generated article images (gitignored)
└── seo_agents/             # the package
    ├── write_articles.py   # write_articles_task  (entrypoint)
    ├── publish_articles.py # publish_article_task (entrypoint)
    ├── article_writer.py   # orchestrates one article end-to-end
    ├── crew.py             # CrewAI agents/tasks (config/agents.yaml, config/tasks.yaml)
    ├── doc_generator.py    # article text/HTML → Google Doc
    ├── doc_to_wp_api.py    # Google Doc → WordPress via REST (/wp-json/wp/v2)
    ├── image_generator.py  # Gemini/Vertex image generation
    ├── task_logger.py      # file-based @task_logger decorator (no DB)
    ├── utils.py            # setup_logger, limit_words, prepare_worksheets
    ├── config/*.yaml       # CrewAI agent + task definitions
    └── parsers/            # BeautifulSoup/Selenium source-URL scrapers
```

## Running locally

```bash
uv sync                                        # install deps
cp .env.example .env                           # then fill in the values
cp /path/to/dashboard-gcloud.json env/         # Google service-account key

# One-shot manual runs (no scheduler):
uv run python -m seo_agents.write_articles     # scan sheet, write pending articles
uv run python -m seo_agents.publish_articles   # publish rows marked "Publish"

# Or run the scheduler (loops the 2 tasks on interval):
uv run python scheduler.py --config crons.yaml
```

## Configuration (env)

All site-specific values are env vars (see `.env.example`). The important ones:

- `WP_URL` / `WP_USERNAME` / `WP_PASSWORD` — the target WordPress site. `WP_URL` is the
  **site root** (REST base is derived as `{WP_URL}/wp-json/wp/v2`). Use a WordPress
  *Application Password*.
- `SEO_SHEET_ID` — the Google Sheet key of this site's "SEO Flow" control sheet. Make a
  copy of the original sheet layout (see below) for the new site.
- `GEMINI_API_KEY` — CrewAI agents run on `gemini/gemini-2.5-flash`; image gen uses Gemini too.
- `OPENAI_API_KEY` — one agent (the writer) uses `openai/gpt-4.1-mini`. Required unless you
  switch that agent to Gemini in `seo_agents/config/agents.yaml`.

## The control sheet ("SEO Flow")

`Sheet1` is the queue. Columns the code reads (0-indexed → A,B,…):

| Col | Field | Used by |
|---|---|---|
| A | keyword (also the per-keyword worksheet name) | both |
| B | WordPress target URL (blank = create new post) | publish |
| C–E | reference/competitor URLs | write |
| F | **status**: `Write` → `Processing` → `Review` → `Publish` → `Done`/`Failed` | both |
| G | link to the per-keyword worksheet (auto) | write |
| H | Google Doc URL (auto) | both |
| I | sub-keywords | write |
| J | suggested outline | write |
| N | tag | publish |

Columns L (category) and M (job role) are no longer read by `publish_articles.py` — they were
JobsGo-specific (WP categories + the `nganh_nghe_chuc_vu_lien_quan` ACF field) and don't apply
to this site's content.

Flow: set a row to `Write` → `write_articles_task` produces the article + Google Doc and
flips it to `Review` → a human reviews the Doc → set it to `Publish` → `publish_article_task`
posts it to WordPress and flips it to `Done`.

## Deployment (dev47)

See `DEPLOY.md` for first-time setup. After that: `fab deploy` (push + pull + restart).
The service runs as a `systemctl --user` unit named `seo_agents`.

## Gotchas / known site-coupling

1. **Updating existing posts is jobsgo-specific.** `publish_articles.publish_to_wordpress`
   only treats col-B as an existing post when it contains `https://jobsgo.vn/blog/`
   (with a `/blog/`↔`/wp/` permalink swap). For any other site, col-B is ignored and a
   **new** post is always created — which is the correct default for a fresh blog. If the
   new site needs in-place updates, generalize that check in `publish_articles.py`.
2. **`env/dashboard-gcloud.json` is required** for all Google Sheets/Docs/Drive access and
   is gitignored — it must be copied to the server manually (not via git). The service
   account also needs write access to the target spreadsheet + Drive folder.
3. **`import settings`** in `image_generator.py` resolves to the **root** `settings.py`
   (project root is on `sys.path` when the scheduler runs from the project dir).
4. Keep this project **DB-free**. If a future task needs the jg_agents DB, it belongs in
   jg_agents, not here.

## Conventions

- Scheduled functions are `async def` and decorated with `@task_logger('name')`.
- Absolute imports from the `seo_agents` package (e.g. `from seo_agents.doc_to_wp_api
  import publish_doc`); entrypoints also carry a relative-import fast path.
