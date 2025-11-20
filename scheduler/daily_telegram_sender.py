"""
Standalone scheduler for daily Telegram messages.

This script is intentionally isolated from the Flask/Gunicorn process. Run it
as its own systemd service so that web availability does not affect scheduled
Telegram notifications.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from dotenv import load_dotenv

from common.telegram_client import send_telegram_message

# Load local .env files for development. Production should supply environment
# variables via systemd or the shell.
load_dotenv()

try:  # Python 3.9+ standard library
    from zoneinfo import ZoneInfo

    SEOUL_TZ = ZoneInfo("Asia/Seoul")
except Exception:  # pragma: no cover - fallback for environments without zoneinfo
    import pytz

    SEOUL_TZ = pytz.timezone("Asia/Seoul")

LOGGER_NAME = "daily_telegram_sender"


def setup_logging() -> None:
    """Configure logging for console and file output."""
    base_dir = Path(__file__).resolve().parent.parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scheduler.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
        force=True,
    )


logger = logging.getLogger(LOGGER_NAME)


def build_daily_message(now: datetime | None = None) -> str:
    """Create the daily message contents."""
    now = now or datetime.now(SEOUL_TZ)
    date_label = now.strftime("%Y-%m-%d (%a)")
    header = f"[자동 알림] {date_label} 시장 링크"
    body = [
        "오늘의 경제 링크 모음",
        "- 경제달력: https://kr.investing.com/economic-calendar/",
        "- 중앙은행 기준금리: https://kr.investing.com/central-banks/",
        "\n#bot01 #daily",
    ]
    return "\n".join([header, ""] + body)


def run_daily_send() -> None:
    """Send the daily Telegram message."""
    message = build_daily_message()
    logger.info("Dispatching daily Telegram message")
    success = send_telegram_message(message, timeout=10, retries=1)
    if success:
        logger.info("Telegram message sent successfully")
    else:
        logger.error("Telegram message failed to send")


def create_scheduler(test_mode: bool = False) -> BlockingScheduler:
    """Configure the APScheduler instance."""
    scheduler = BlockingScheduler(timezone=SEOUL_TZ, job_defaults={"max_instances": 1})

    if test_mode:
        run_date = datetime.now(SEOUL_TZ) + timedelta(seconds=30)
        trigger = DateTrigger(run_date=run_date, timezone=SEOUL_TZ)
        logger.info("Scheduler test mode enabled; job will run once at %s", run_date)
    else:
        trigger = CronTrigger(hour=8, minute=20, timezone=SEOUL_TZ)
        logger.info("Scheduler configured for daily 08:20 Asia/Seoul")

    scheduler.add_job(
        run_daily_send,
        trigger=trigger,
        id="daily_telegram",
        max_instances=1,
        replace_existing=True,
        coalesce=True,
    )
    return scheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Telegram sender scheduler")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Send a single Telegram message immediately and exit",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    test_mode = os.environ.get("SCHEDULER_TEST_MODE", "").lower() == "true"

    if args.run_once:
        logger.info("Running in run-once mode; no scheduler will start")
        run_daily_send()
        return

    logger.info("Starting APScheduler (test_mode=%s)", test_mode)
    scheduler = create_scheduler(test_mode=test_mode)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down")


if __name__ == "__main__":
    main()
