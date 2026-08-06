"""
Entry point.

Usage:
  python main.py          → starts the scheduler (runs daily at 10:00 AM IST)
  python main.py --now    → run the brief immediately (for testing)
"""

import argparse
import logging
import sys

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

from config import REPORT_TIMEZONE, SCHEDULE_HOUR, SCHEDULE_MINUTE
from deliver import send_email, send_gchat
from metrics import compute
from mixpanel_client import fetch_all_windows, fetch_traffic_mau, fetch_traffic_30d, get_windows
from report import build

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("gc_brief.main")


def run_brief() -> None:
    log.info("=== GC Brief run started ===")

    # W0 (this week) + 6 baseline weeks for Z-scores (baseline starts Jun 17, 2026).
    # n_weeks=7: W0 + W1..W6 (Jun 18–Aug 5 as of Aug 2026, n_baseline=6).
    windows = get_windows(n_weeks=7)
    log.info("Report window: %s → %s", windows[0][0], windows[0][1])

    fetched = fetch_all_windows(windows)

    log.info("Fetching 30-day traffic window …")
    traffic_30d = fetch_traffic_30d()

    log.info("Fetching monthly traffic MAU …")
    monthly_traffic = fetch_traffic_mau()

    m = compute(fetched, monthly_traffic, traffic_30d)
    report = build(m)

    log.info("Sending Google Chat message …")
    send_gchat(report["chat_text"])

    log.info("Sending email …")
    send_email(report["subject"], report["html"])

    log.info("=== GC Brief run complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="GC Weekly Brief automation")
    parser.add_argument("--now", action="store_true",
                        help="Run the brief immediately instead of waiting for the schedule")
    args = parser.parse_args()

    if args.now:
        run_brief()
        sys.exit(0)

    tz = pytz.timezone(REPORT_TIMEZONE)
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        run_brief,
        trigger="cron",
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        name="gc_brief_daily",
    )
    log.info(
        "Scheduler started. GC Brief will run daily at %02d:%02d %s.",
        SCHEDULE_HOUR, SCHEDULE_MINUTE, REPORT_TIMEZONE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
