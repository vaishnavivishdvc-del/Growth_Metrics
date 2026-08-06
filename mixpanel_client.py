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

from config import MX_PROJECT_ID, MX_SA_USERNAME, MX_SA_SECRET, ALL_EVENTS, LAUNCH_DATE, TRAFFIC_EVENT, OR_QUERY_GROUPS

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


def fetch_traffic_30d() -> dict:
    """
    Fetch unique sellers for Traffic_Report_Visit for:
      - current 30-day window  (yesterday − 29 days → yesterday)
      - prior   30-day window  (yesterday − 59 days → yesterday − 30 days)
    Returns {"from0", "to0", "u0", "from1", "to1", "u1"}.
    """
    yesterday = date.today() - timedelta(days=1)
    to0 = yesterday
    fr0 = to0 - timedelta(days=29)
    to1 = fr0 - timedelta(days=1)
    fr1 = to1 - timedelta(days=29)

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

    def _uniq(fr, to):
        rows = _jql(script_tpl.format(from_date=fr, to_date=to, sel=selector))
        return next((r["value"] for r in rows if r["key"][0] == TRAFFIC_EVENT), 0)

    u0 = _uniq(fr0, to0)
    u1 = _uniq(fr1, to1)
    log.info("Traffic 30d: %d sellers (%s–%s) vs %d sellers (%s–%s)",
             u0, fr0, to0, u1, fr1, to1)
    return {
        "from0": str(fr0), "to0": str(to0), "u0": u0,
        "from1": str(fr1), "to1": str(to1), "u1": u1,
    }


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

    # Current partial month — from 1st of this month to yesterday
    yesterday = today - timedelta(days=1)
    partial_start = date(today.year, today.month, 1)
    if partial_start <= yesterday:
        rows = _jql(script_tpl.format(from_date=partial_start, to_date=yesterday, sel=selector))
        partial_count = next((r["value"] for r in rows if r["key"][0] == TRAFFIC_EVENT), 0)
        partial_key = f"{today.year}-{today.month:02d} (so far, {yesterday.strftime('%b %-d')})"
        monthly[partial_key] = partial_count
        log.info("Traffic partial month so far (%s): %d unique sellers", partial_key, partial_count)

    return monthly


# Bitmask assignments for OR groups — each group gets a dedicated bit.
# All 8 groups are resolved in a SINGLE JQL call per window to stay within
# Mixpanel's rolling rate limit.
_OR_BITMASK: dict[str, int] = {
    "pill_shown_or":    1,
    "pill_click_or":    2,
    "alert_shown_or":   4,
    "alert_click_or":   8,
    "ap_shown_or":     16,   # derived: pill_shown_or | alert_shown_or
    "ap_click_or":     32,   # derived: pill_click_or | alert_click_or
    "recco_shown_or":  64,
    "recco_applied_or":128,
}


def _or_uniques_jql(from_date: str, to_date: str) -> dict[str, int]:
    """
    Compute OR-deduplicated unique sellers for ALL 8 OR groups in ONE JQL call.

    Each seller is assigned a bitmask integer encoding which OR groups they belong
    to.  `groupBy` returns a frequency histogram of bitmasks; Python then sums
    counts across every bitmask that has a given group's bit set.

    This replaces 8 separate JQL calls with 1, keeping total requests per run
    well within Mixpanel's rolling rate limit.
    """
    def _js_arr(events: list[str]) -> str:
        return "[" + ",".join(f"'{e}'" for e in events) + "]"

    pill_shown_js  = _js_arr(OR_QUERY_GROUPS["pill_shown_or"])
    pill_click_js  = _js_arr(OR_QUERY_GROUPS["pill_click_or"])
    alert_shown_js = _js_arr(OR_QUERY_GROUPS["alert_shown_or"])
    alert_click_js = _js_arr(OR_QUERY_GROUPS["alert_click_or"])
    recco_shown_js = _js_arr(OR_QUERY_GROUPS["recco_shown_or"])
    recco_appl_js  = _js_arr(OR_QUERY_GROUPS["recco_applied_or"])

    # Union of all events across all OR groups (deduped, used as event_selectors)
    all_or_events = list(dict.fromkeys(
        e for evts in OR_QUERY_GROUPS.values() for e in evts
    ))
    selectors = json.dumps([{"event": e} for e in all_or_events])

    script = f"""
function containsAny(seen, names) {{
  for (var i = 0; i < names.length; i++) {{
    if (seen[names[i]]) return true;
  }}
  return false;
}}
function main() {{
  return Events({{
    from_date: '{from_date}',
    to_date: '{to_date}',
    event_selectors: {selectors}
  }}).groupByUser([function(events) {{
    var seen = {{}};
    events.forEach(function(e) {{ seen[e.name] = true; }});
    var b = 0;
    if (containsAny(seen, {pill_shown_js}))  b |= 1;
    if (containsAny(seen, {pill_click_js}))  b |= 2;
    if (containsAny(seen, {alert_shown_js})) b |= 4;
    if (containsAny(seen, {alert_click_js})) b |= 8;
    if (b & 5)  b |= 16;
    if (b & 10) b |= 32;
    if (containsAny(seen, {recco_shown_js})) b |= 64;
    if (containsAny(seen, {recco_appl_js}))  b |= 128;
    return b;
  }}], mixpanel.reducer.any())
  .groupBy(['key.0'], mixpanel.reducer.count());
}}"""

    rows = _jql(script)
    log.info("OR-dedup bitmask histogram: %d distinct bitmasks (%s → %s)",
             len(rows), from_date, to_date)

    # Decode histogram → per-group counts
    result = {k: 0 for k in _OR_BITMASK}
    for row in rows:
        bitmask = row.get("key", [0])[0]
        count   = row.get("value", 0)
        for key, bit in _OR_BITMASK.items():
            if bitmask & bit:
                result[key] += count
    return result


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
        tot     = _totals_jql(from_date, to_date)
        uniq    = _uniques_jql(from_date, to_date)
        or_uniq = _or_uniques_jql(from_date, to_date)   # 1 call for all 8 OR groups
        return idx, {"total": tot, "unique": uniq, "or": or_uniq, "from": from_date, "to": to_date}

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
