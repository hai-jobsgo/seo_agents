"""
Lightweight, file-based task execution logger for APScheduler tasks.

This is a self-contained replacement for jg_agents' DB-backed `utils.task_logger`.
It keeps the same public API — the `@task_logger(name, timeout=None)` decorator —
but logs to a file (and stdout) instead of a MySQL `task_execution_log` table, so
this standalone project has no database dependency.

Log destination: $LOG_DIR/tasks.log (LOG_DIR defaults to <project>/logs).
"""

import os
import asyncio
import logging
import traceback
from functools import wraps
from datetime import datetime
from logging.handlers import RotatingFileHandler

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_LOG_DIR = os.getenv("LOG_DIR", os.path.join(_BASE_DIR, "logs"))
os.makedirs(_LOG_DIR, exist_ok=True)

_logger = logging.getLogger("seo_agents.tasks")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = RotatingFileHandler(
        os.path.join(_LOG_DIR, "tasks.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    _logger.addHandler(_handler)
    # Also mirror to stdout so systemd journal / console captures it.
    _stream = logging.StreamHandler()
    _stream.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    _logger.addHandler(_stream)


async def log_task_execution(task_name, func, timeout, *args, **kwargs):
    start_time = datetime.now()
    _logger.info(f"[{task_name}] started")

    try:
        if timeout:
            try:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Task exceeded timeout of {timeout}s")
        else:
            result = await func(*args, **kwargs)

        duration = (datetime.now() - start_time).total_seconds()
        _logger.info(f"[{task_name}] success in {duration:.2f}s")
        return result

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        _logger.error(f"[{task_name}] error after {duration:.2f}s: {e}")
        _logger.error(traceback.format_exc())
        raise


def task_logger(task_name, timeout=None):
    """
    Decorator to log task execution to a file.

    Usage:
        @task_logger("my_task_name", timeout=600)
        async def my_task():
            pass

    Args:
        task_name: Name to use for logging this task
        timeout: Optional seconds before the task is cancelled and logged as error
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await log_task_execution(task_name, func, timeout, *args, **kwargs)
        return wrapper
    return decorator
