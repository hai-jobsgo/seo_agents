# Deploying seo_agents to dev47

The service runs as a **user** systemd unit (`systemctl --user`) at
`/var/www/seo_agents` on dev47 — mirroring how `jg_agents` runs there.

Prereqs on your machine: an SSH host alias `dev47` in `~/.ssh/config`, and `uv`
installed on dev47 (already the case for jg_agents).

## First-time setup (once)

### 1. Create the git repo & push

```bash
cd /Users/hai/Websites/seo_agents
git init && git add -A && git commit -m "init standalone seo_agents"
# create the remote (GitHub or wherever), then:
git remote add origin <your-remote-url>
git push -u origin main
```

### 2. Clone on dev47

```bash
ssh dev47
sudo mkdir -p /var/www/seo_agents && sudo chown $USER /var/www/seo_agents
git clone <your-remote-url> /var/www/seo_agents
cd /var/www/seo_agents
bash -lc "uv sync"        # bash -lc so uv is on PATH in non-interactive SSH
mkdir -p logs images env
```

### 3. Copy secrets (NOT in git)

From your machine:

```bash
scp .env dev47:/var/www/seo_agents/.env
scp env/dashboard-gcloud.json dev47:/var/www/seo_agents/env/dashboard-gcloud.json
```

> The Google service account (in `dashboard-gcloud.json`) must have edit access to the
> target "SEO Flow" spreadsheet and the Drive folder where Docs are created. Share the
> sheet with the service account's email.

### 4. Install the systemd user service

```bash
ssh dev47
mkdir -p ~/.config/systemd/user
cp /var/www/seo_agents/seo_agents.service ~/.config/systemd/user/seo_agents.service
systemctl --user daemon-reload
systemctl --user enable --now seo_agents
# so the service keeps running after you log out:
loginctl enable-linger $USER
```

### 5. Verify

```bash
systemctl --user status seo_agents --no-pager
journalctl --user -u seo_agents -f
tail -f /var/www/seo_agents/logs/tasks.log
```

## Routine deploys

From your machine, after committing changes:

```bash
fab deploy      # git push origin main + git pull on dev47 + uv sync + restart
```

Other commands:

```bash
fab live        # tail logs/tasks.log on dev47
fab restart     # restart without pulling
fab status      # systemctl --user status
```

## Rollback

```bash
ssh dev47
cd /var/www/seo_agents
git log --oneline -5
git checkout <good-commit>
systemctl --user restart seo_agents
```

## Notes

- This service is **independent** of `jg_agents` — deploying/restarting it does not touch
  the jg_agents service, and vice-versa. That isolation is the reason it was split out.
- No database is involved; if the service is down, nothing else is affected.
- Logs: systemd journal (`journalctl --user -u seo_agents`) + `logs/tasks.log`
  (rotating) + `logs/publish_articles.log`.
- **Selenium/ChromeDriver**: `parsers/base_parser.py` uses Selenium (via `webdriver-manager`)
  to scrape competitor source URLs during `write_articles_task`. `webdriver-manager` auto-downloads
  the ChromeDriver build matching whatever Chrome/Chromium is installed and caches it under
  `~/.wdm` — no manual chromedriver install/pinning needed, and it re-resolves automatically
  if Chrome is later updated. Requirements on dev47: **Chrome or Chromium must be installed**
  (`google-chrome --version` / `chromium --version`), and the box needs outbound internet
  access to `googlechromelabs.github.io` / `storage.googleapis.com` the first time it runs
  (or whenever Chrome's version changes) to fetch the matching driver.
