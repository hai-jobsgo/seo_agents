"""
Lean APScheduler entrypoint for the standalone seo_agents service.

Loads job definitions from a YAML file (default: crons.yaml) and runs them.
Unlike jg_agents' scheduler this has NO database or Elasticsearch setup — the
SEO write/publish tasks only need Google Sheets + WordPress REST + LLM APIs.

Usage:
    python scheduler.py                 # loads crons.yaml
    python scheduler.py --config crons.yaml
"""

import os
import yaml
import asyncio
import inspect
import argparse
from importlib import import_module

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

import settings  # noqa: F401  (loads .env on import)


async def load_jobs_from_yaml(scheduler, yaml_file):
    with open(yaml_file, "r") as file:
        config = yaml.safe_load(file)

    jobs = config.get("jobs", [])
    print(f'jobs defined in YAML: {len(jobs)}', flush=True)
    for job in jobs:
        try:
            module_name, func_name = job["func"].split(":")
            func = getattr(import_module(module_name), func_name)

            if not inspect.iscoroutinefunction(func):
                raise TypeError(f"{func_name} in {module_name} must be an async function")

            if job.get("trigger") == "cron":
                trigger = CronTrigger(
                    hour=job.get("hour"), minute=job.get("minute"),
                    day=job.get("day"), day_of_week=job.get("day_of_week"),
                )
                print(f'{func_name} scheduled cron {job.get("hour")}:{job.get("minute")}', flush=True)
            elif job.get("trigger") == "date":
                trigger = DateTrigger(run_date=job.get("run_date"))
                print(f'{func_name} scheduled at {job.get("run_date")}', flush=True)
            else:
                trigger = IntervalTrigger(minutes=job["minutes"])
                print(f'{func_name} every {job["minutes"]} min', flush=True)

            scheduler.add_job(
                func,
                trigger=trigger,
                id=job["id"],
                max_instances=job.get("max_instances", 1),
                misfire_grace_time=job.get("misfire_grace_time", 30),
                coalesce=job.get("coalesce", True),
            )

            if job.get("start_now", False):
                asyncio.create_task(func())
        except Exception as e:
            print(f"Error loading job {job.get('id')}: {e}", flush=True)


async def main(yaml_file="crons.yaml"):
    print(f'Starting scheduler: {yaml_file}', flush=True)
    if not os.path.exists(yaml_file):
        raise SystemExit(f"Config file not found: {yaml_file}")

    scheduler = AsyncIOScheduler()
    scheduler.configure(misfire_grace_time=10)
    await load_jobs_from_yaml(scheduler, yaml_file)
    scheduler.start()
    print("Scheduler started", flush=True)

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("Scheduler shut down", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEO Agents scheduler")
    parser.add_argument("--config", "-c", default="crons.yaml",
                        help="YAML config file (default: crons.yaml)")
    args = parser.parse_args()
    asyncio.run(main(args.config))
