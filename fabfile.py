"""
Fabric deployment for the standalone seo_agents service.

Assumes an SSH host alias `dev47` in ~/.ssh/config and that the repo is already
cloned at /var/www/seo_agents on the server (see DEPLOY.md for first-time setup).

    fab deploy        # git push + pull on dev47 + restart the service
    fab live          # tail the task log on dev47
    fab restart       # restart the service only
"""

from fabric import Connection, task

HOST = "dev47"
REMOTE_DIR = "/var/www/seo_agents"
SERVICE = "seo_agents"


@task
def deploy(c):
    """Push local main, pull on dev47, sync deps, restart the service."""
    c.run("git push origin main")
    conn = Connection(HOST)
    with conn.cd(REMOTE_DIR):
        conn.run("git pull")
        # Sync dependencies (safe to run every deploy; no-op if unchanged).
        conn.run('bash -lc "uv sync"', warn=True)
    conn.run(f"systemctl --user restart {SERVICE}")
    print(f"Deployed and restarted {SERVICE} on {HOST}")


@task
def restart(c):
    """Restart the service on dev47 without pulling."""
    Connection(HOST).run(f"systemctl --user restart {SERVICE}")


@task
def live(c):
    """Tail the task log on dev47."""
    conn = Connection(HOST)
    with conn.cd(REMOTE_DIR):
        conn.run("tail -f logs/tasks.log")


@task
def status(c):
    """Show the service status on dev47."""
    Connection(HOST).run(f"systemctl --user status {SERVICE} --no-pager", warn=True)
