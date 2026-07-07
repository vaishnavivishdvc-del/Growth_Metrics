"""
Mixpanel REST API client.

Uses JQL (JavaScript Query Language) for true deduplicated weekly unique counts.
Two batch calls per window:
  - totals_jql  → raw event counts per event name
  - uniques_jql → deduplicated seller counts per event name
"""

import json
import logging
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

import requests

from config import MX_PROJECT_ID, MX_SA_USERNAME, MX_SA_SECRET, ALL_EVENTS, LAUNCH_DATE, TRAFFIC_EVENT

log = logging.getLogger(__name__)

AUTH    = (MX_SA_USERNAME, MX_SA_SECRET)
JQL_URL = "https://eu.mixpanel.com/api/2.0/jql"

_SELECTORS = json.dumps([{"event": e} for e in ALL_EVENTS])


_MAX_RETRIES = 4
_RETRY_WAIT  = 70   # seconds — just over Mixpanel's 60-s rolling window


def _jql(script: str) -> list:
    for attempt in range(_MAX_RETRIES):
        resp = requests.post(
            JQL_URL,
            auth=AUTH,
            data={"script": script, "project_id": MX_PROJECT_ID},
            timeout=90,
        )
        if resp.status_code == 429:
            wait = _RETRY_WAIT * (attempt + 1)
            log.warning("Rate limited (429). Waiting %ds then retrying (attempt %d/%d)…",
                        wait, attempt + 1, _MAX_RETRIES - 1)
            time.sleep(wait)
            continue
        if not resp.ok:
            log.error("JQL API error %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        result = resp.json()
        log.info("JQL returned %d rows", len(result) if isinstance(result, list) else -1)
        return result
    raise RuntimeError("Mixpanel JQL rate limit not resolved after %d retries" % _MAX_RETRIES)


def _totals_jql(from_date: str, to_date: str) -> dict[str, int]:
    """Total event count per event name."""
    script = f"""
function main() {{
  return Events({{
    from_date: '{from_date}',
    to_date: '{to_date}',
    event_selectors: {_SELECTORS}
  }}).groupBy(['name'], mixpanel.reducer.count());
}}"""
    rows = _jql(script)
    return {r["key"][0]: r["value"] for r in rows}


def _uniques_jql(from_date: str, to_date: str) -> dict[str, int]:
    """
    Deduplicated unique seller count per event name.
    groupByUser(['name']) produces key=[distinct_id, event_name].
    We then groupBy key.1 (event_name) and count → unique users per event.
    """
    script = f"""
function main() {{
  return Events({{
    from_date: '{from_date}',
    to_date: '{to_date}',
    event_selectors: {_SELECTORS}
  }}).groupByUser(['name'], mixpanel.reducer.any())
  .groupBy(['key.1'], mixpanel.reducer.count());
}}"""
    rows = _jql(script)
    return {r["key"][0]: r["value"] for r in rows}


def fetch_traffic_mau() -> dict[str, int]:
    """
    Unique sellers for Traffic_Report_Visit per complete calendar month since
    LAUNCH_DATE, up to (but not including) the current partial month.
    Returns e.g. {"2026-04": 50794, "2026-05": 72665, "2026-06": 77279}.
    """
    today = date.today()
    selector = json.dumps([{"event": TRAFFIC_EVENT}])
    script_tpl = """
function main() {{
  return Events({{
    from_date: '{from_date}',
    to_date:   '{to_date}',
    event_selectors: {sel}
  }}).groupByUser(['name'], mixpanel.reducer.any())
  .groupBy(['key.1'], mixpanel.reducer.count());
}}"""

    monthly: dict[str, int] = {}
    yr, mo = LAUNCH_DATE.year, LAUNCH_DATE.month

    while (yr, mo) < (today.year, today.month):
        start = LAUNCH_DATE if (yr == LAUNCH_DATE.year and mo == LAUNCH_DATE.month) else date(yr, mo, 1)
        end   = date(yr, mo, monthrange(yr, mo)[1])
        rows  = _jql(script_tpl.format(from_date=start, to_date=end, sel=selector))
        monthly[f"{yr}-{mo:02d}"] = next(
            (r["value"] for r in rows if r["key"][0] == TRAFFIC_EVENT), 0
        )
        log.info("Traffic MAU %s-%02d: %d unique sellers", yr, mo, monthly[f"{yr}-{mo:02d}"])
        mo += 1
        if mo > 12:
            yr, mo = yr + 1, 1

    return monthly


def get_windows(n_weeks: int = 5) -> list[tuple[str, str]]:
    """
    Returns n_weeks windows, most-recent first.
    W0 = last 7 days ending yesterday (the report window).
    W1-W4 = prior 7-day windows used for Z-score baseline.
    """
    yesterday = date.today() - timedelta(days=1)
    windows = []
    for i in range(n_weeks):
        to = yesterday - timedelta(weeks=i)
        fr = to - timedelta(days=6)
        windows.append((str(fr), str(to)))
    return windows


def fetch_all_windows(windows: list[tuple[str, str]]) -> list[dict]:
    """
    Fetch totals + uniques for every window in parallel.
    Returns a list aligned with the input windows list.
    """
    results: list[dict | None] = [None] * len(windows)

    def _fetch(idx: int, from_date: str, to_date: str):
        log.info("Fetching window %s → %s", from_date, to_date)
        tot  = _totals_jql(from_date, to_date)
        uniq = _uniques_jql(from_date, to_date)
        return idx, {"total": tot, "unique": uniq, "from": from_date, "to": to_date}

    # max_workers=2 → at most 2 windows fetched in parallel = max 2 concurrent JQL
    # queries at a time (totals + uniques inside each thread run sequentially).
    # Mixpanel allows 5 concurrent and 60/hour; this keeps us comfortably under both.
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {
            ex.submit(_fetch, i, f, t): i
            for i, (f, t) in enumerate(windows)
        }
        for fut in as_completed(futures):
            idx, data = fut.result()   # raises immediately on any API failure
            results[idx] = data

    return results
