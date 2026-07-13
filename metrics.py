"""
Pure metric computation: aggregations, rates, Z-scores, anomaly detection.
Input:  list of window dicts from mixpanel_client.fetch_all_windows()
Output: single metrics dict consumed by report.py
"""

import numpy as np

from config import (
    PILLS_SHOWN, PILLS_CLICKED,
    OTHER_PILLS_SHOWN, OTHER_PILLS_VIEWED,
    ALERTS_SHOWN, ALERTS_CLICKED,
    PRICE_RECOS_SHOWN, PRICE_RECOS_APPLIED,
    REST_RECOS_SHOWN, REST_RECOS_APPLIED,
    ALERT_PAIRS, PRICE_RECO_PAIRS, REST_RECO_PAIRS,
    PRICE_RECO_LABELS, REST_RECO_LABELS, PILL_LABELS, OTHER_PILL_LABELS,
    TRAFFIC_EVENT, BASELINE_DATE,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _s(d: dict, k: str) -> int:
    return d.get(k, 0)

def _sum(d: dict, keys: list[str]) -> int:
    return sum(_s(d, k) for k in keys)

def _pct(num: float, den: float) -> float:
    return round(num / den * 100, 1) if den else 0.0

def _wow(curr: float, prev: float) -> float:
    return round((curr - prev) / prev * 100, 1) if prev else 0.0

def _eps(d: float, total: float) -> float:
    return round(total / d, 2) if d else 0.0

def _zscore(val: float, baseline: list[float]) -> float:
    arr = [x for x in baseline if x is not None]
    if len(arr) < 2:
        return 0.0
    m = np.mean(arr)
    s = np.std(arr, ddof=1)
    return round((val - m) / s, 2) if s else 0.0

def _status(z: float) -> str:
    return "🔴" if z < -2 else ("🟡" if z < -1.5 else "🟢")


# ── baseline helper ───────────────────────────────────────────────────────────

def _rate_baseline(baseline_windows: list[dict], num_keys, den_keys) -> list[float]:
    """Compute a rate metric across prior windows for Z-score baseline."""
    if isinstance(num_keys, str):
        num_keys = [num_keys]
    if isinstance(den_keys, str):
        den_keys = [den_keys]
    return [
        _pct(_sum(bw["unique"], num_keys), _sum(bw["unique"], den_keys))
        for bw in baseline_windows
    ]


# ── main computation ──────────────────────────────────────────────────────────

def compute(fetched: list[dict],
            monthly_traffic: dict[str, int] | None = None,
            traffic_30d: dict | None = None) -> dict:
    """
    fetched[0] = this week (W0), fetched[1] = prev week (W1),
    fetched[2+] = older weeks for Z-score baseline (if available).
    monthly_traffic = {YYYY-MM: unique_sellers} from fetch_traffic_mau()
    """
    w0 = fetched[0]
    w1 = fetched[1]
    baseline = fetched[1:]   # W1+ used as Z-score baseline

    u0, t0 = w0["unique"], w0["total"]
    u1      = w1["unique"]

    # ── Traffic Report Visits (7-day, for Z-score baseline only) ─────────────
    traffic_u0 = _s(u0, TRAFFIC_EVENT)
    traffic_e0 = _s(t0, TRAFFIC_EVENT)
    traffic_u1 = _s(u1, TRAFFIC_EVENT)

    # ── Traffic Report Visits (30-day, primary L0 display) ───────────────────
    t30 = traffic_30d or {}
    traffic_30d_u0      = t30.get("u0", 0)
    traffic_30d_u1      = t30.get("u1", 0)
    traffic_30d_from0   = t30.get("from0", "")
    traffic_30d_to0     = t30.get("to0", "")
    traffic_30d_from1   = t30.get("from1", "")
    traffic_30d_to1     = t30.get("to1", "")
    traffic_30d_wow_pct = round((traffic_30d_u0 - traffic_30d_u1) / traffic_30d_u1 * 100, 1) if traffic_30d_u1 else 0

    # MAU: complete months + current partial month (all from monthly_traffic)
    mau_months  = list((monthly_traffic or {}).keys())
    mau_values  = list((monthly_traffic or {}).values())
    # MAU average uses only complete calendar months (exclude the "so far" partial entry)
    complete_values = [v for k, v in (monthly_traffic or {}).items() if "so far" not in k]
    traffic_mau        = round(sum(complete_values) / len(complete_values)) if complete_values else 0
    traffic_mau_months = mau_months
    traffic_mau_values = mau_values

    # ── Pills ─────────────────────────────────────────────────────────────────
    PILL_CLICK_EVENTS = [
        "gc_losing_imp_listings_filter_click",
        "gc_losing_conv_listings_filter_click",
    ]

    pill_shown_rows = [
        {
            "name": "Losing Imp Pill",
            "shown_u": _s(u0, PILLS_SHOWN[0]),
            "shown_t": _s(t0, PILLS_SHOWN[0]),
            "prev_shown_u": _s(u1, PILLS_SHOWN[0]),
        },
        {
            "name": "Losing Conv Pill",
            "shown_u": _s(u0, PILLS_SHOWN[1]),
            "shown_t": _s(t0, PILLS_SHOWN[1]),
            "prev_shown_u": _s(u1, PILLS_SHOWN[1]),
        },
    ]
    pill_click_rows = [
        {
            "name":         PILL_LABELS[e],
            "clicked_u":    _s(u0, e),
            "clicked_t":    _s(t0, e),
            "prev_u":       _s(u1, e),
            "shown_u":      _s(u0, PILLS_SHOWN[i]),
            "prev_shown_u": _s(u1, PILLS_SHOWN[i]),
        }
        for i, e in enumerate(PILLS_CLICKED)
    ]

    # "Other listings" reach rows (shown after filter-pill; not in engagement rate)
    other_pill_rows = [
        {
            "name":      OTHER_PILL_LABELS.get(e, e),
            "shown_u":   _s(u0, e),
            "shown_t":   _s(t0, e),
            "prev_shown_u": _s(u1, e),
        }
        for e in OTHER_PILLS_SHOWN
    ] + [
        {
            "name":       OTHER_PILL_LABELS.get(e, e),
            "viewed_u":   _s(u0, e),
            "viewed_t":   _s(t0, e),
            "prev_viewed_u": _s(u1, e),
        }
        for e in OTHER_PILLS_VIEWED
    ]

    tot_pills_shown_u  = _sum(u0, PILLS_SHOWN)
    tot_pills_shown_t  = _sum(t0, PILLS_SHOWN)
    tot_pills_clicked_u = _sum(u0, PILL_CLICK_EVENTS)
    tot_pills_clicked_t = _sum(t0, PILL_CLICK_EVENTS)

    # supplementary reach totals (for report tables only — not part of engagement rate)
    tot_other_pills_shown_u  = _sum(u0, OTHER_PILLS_SHOWN)
    tot_other_pills_viewed_u = _sum(u0, OTHER_PILLS_VIEWED)

    prev_pills_shown_u   = _sum(u1, PILLS_SHOWN)
    prev_pills_clicked_u = _sum(u1, PILL_CLICK_EVENTS)

    pill_click_rate = _pct(tot_pills_clicked_u, tot_pills_shown_u)

    # ── Alerts ────────────────────────────────────────────────────────────────
    alert_rows = []
    for shown_ev, clicked_ev in ALERT_PAIRS:
        su  = _s(u0, shown_ev);  st  = _s(t0, shown_ev)
        cu  = _s(u0, clicked_ev); ct  = _s(t0, clicked_ev)
        su1 = _s(u1, shown_ev);  cu1 = _s(u1, clicked_ev)
        ctr      = _pct(cu, su)
        prev_ctr = _pct(cu1, su1)
        label = "Impressions Alert" if "imp" in shown_ev else "Conversion Alert"
        alert_rows.append({
            "name": label,
            "shown_u": su, "shown_t": st,
            "clicked_u": cu, "clicked_t": ct,
            "ctr": ctr, "prev_ctr": prev_ctr,
            "delta_pp": round(ctr - prev_ctr, 1),
        })

    tot_alert_shown_u   = _sum(u0, ALERTS_SHOWN)
    tot_alert_clicked_u = _sum(u0, ALERTS_CLICKED)
    tot_alert_shown_t   = _sum(t0, ALERTS_SHOWN)
    tot_alert_clicked_t = _sum(t0, ALERTS_CLICKED)
    tot_prev_shown_u    = _sum(u1, ALERTS_SHOWN)
    tot_prev_clicked_u  = _sum(u1, ALERTS_CLICKED)

    # ── Alerts & Pills combined (L0 Engagement Rate) ──────────────────────────
    ap_shown_u = tot_pills_shown_u + tot_alert_shown_u
    ap_click_u = tot_pills_clicked_u + tot_alert_clicked_u
    ap_eng_rate = _pct(ap_click_u, ap_shown_u)

    prev_ap_shown_u = prev_pills_shown_u + _sum(u1, ALERTS_SHOWN)
    prev_ap_click_u = prev_pills_clicked_u + _sum(u1, ALERTS_CLICKED)
    prev_ap_eng_rate = _pct(prev_ap_click_u, prev_ap_shown_u)
    ap_eng_delta = round(ap_eng_rate - prev_ap_eng_rate, 1)

    # ── Price recos ───────────────────────────────────────────────────────────
    price_sub = []
    for shown_ev, applied_ev in PRICE_RECO_PAIRS:
        su = _s(u0, shown_ev); st = _s(t0, shown_ev)
        au = _s(u0, applied_ev); at = _s(t0, applied_ev)
        su1 = _s(u1, shown_ev); au1 = _s(u1, applied_ev)
        price_sub.append({
            "name": PRICE_RECO_LABELS[shown_ev],
            "shown_u": su, "shown_t": st,
            "applied_u": au, "applied_t": at,
            "adoption": _pct(au, su),
            "prev_adoption": _pct(au1, su1),
            "wow_shown": _wow(su, su1),
        })

    price_shown_u   = _sum(u0, PRICE_RECOS_SHOWN)
    price_applied_u = _sum(u0, PRICE_RECOS_APPLIED)
    price_shown_t   = _sum(t0, PRICE_RECOS_SHOWN)
    price_applied_t = _sum(t0, PRICE_RECOS_APPLIED)
    prev_price_shown_u  = _sum(u1, PRICE_RECOS_SHOWN)
    prev_price_applied_u = _sum(u1, PRICE_RECOS_APPLIED)

    # ── Rest recos ────────────────────────────────────────────────────────────
    rest_reco_rows = []
    for shown_ev, applied_ev in REST_RECO_PAIRS:
        su = _s(u0, shown_ev); st = _s(t0, shown_ev)
        au = _s(u0, applied_ev); at = _s(t0, applied_ev)
        su1 = _s(u1, shown_ev); au1 = _s(u1, applied_ev)
        adp  = _pct(au, su)
        adp1 = _pct(au1, su1)
        rest_reco_rows.append({
            "name": REST_RECO_LABELS[shown_ev],
            "shown_u": su, "shown_t": st,
            "applied_u": au, "applied_t": at,
            "adoption": adp, "prev_adoption": adp1,
            "wow_applied": _wow(au, au1),
        })

    rest_shown_u   = _sum(u0, REST_RECOS_SHOWN)
    rest_applied_u = _sum(u0, REST_RECOS_APPLIED)

    # ── Totals (recos) ────────────────────────────────────────────────────────
    tot_reco_shown_u   = price_shown_u + rest_shown_u
    tot_reco_applied_u = price_applied_u + rest_applied_u
    tot_reco_shown_t   = price_shown_t + _sum(t0, REST_RECOS_SHOWN)
    tot_reco_applied_t = price_applied_t + _sum(t0, REST_RECOS_APPLIED)

    prev_reco_shown_u   = _sum(u1, PRICE_RECOS_SHOWN) + _sum(u1, REST_RECOS_SHOWN)
    prev_reco_applied_u = _sum(u1, PRICE_RECOS_APPLIED) + _sum(u1, REST_RECOS_APPLIED)

    # ── Z-scores ──────────────────────────────────────────────────────────────
    fa_ctr         = _pct(_s(u0, "gc_fa_recco_applied"), _s(u0, "gc_fa_recco_shown"))
    supp_ctr       = _pct(_s(u0, "gc_suppression_recco_clicked"), _s(u0, "gc_suppression_recco_shown"))
    overall_reco_ctr = _pct(tot_reco_applied_u, tot_reco_shown_u)

    def _ap_baseline(bws):
        """A&P Engagement Rate across baseline windows (unique basis)."""
        rates = []
        for bw in bws:
            bu = bw["unique"]
            num = _sum(bu, PILL_CLICK_EVENTS) + _sum(bu, ALERTS_CLICKED)
            den = _sum(bu, PILLS_SHOWN) + _sum(bu, ALERTS_SHOWN)
            rates.append(_pct(num, den))
        return rates

    zscore_specs = [
        ("A&P Engagement Rate", ap_eng_rate, _ap_baseline(baseline)),
        ("Pill Engagement Rate", pill_click_rate,
         _rate_baseline(baseline, PILL_CLICK_EVENTS, PILLS_SHOWN)),
        ("Alert Engagement Rate",
         _pct(tot_alert_clicked_u, tot_alert_shown_u),
         _rate_baseline(baseline, ALERTS_CLICKED, ALERTS_SHOWN)),
        ("Overall Reco Adoption", overall_reco_ctr,
         _rate_baseline(baseline, PRICE_RECOS_APPLIED + REST_RECOS_APPLIED,
                        PRICE_RECOS_SHOWN + REST_RECOS_SHOWN)),
        ("F-Assured CTR", fa_ctr,
         _rate_baseline(baseline, "gc_fa_recco_applied", "gc_fa_recco_shown")),
        ("Suppression CTR", supp_ctr,
         _rate_baseline(baseline, "gc_suppression_recco_clicked", "gc_suppression_recco_shown")),
    ]

    zscore_rows = []
    for name, val, bl in zscore_specs:
        z = _zscore(val, bl)
        zscore_rows.append({
            "name": name, "value": val,
            "mean": round(float(np.mean(bl)), 1) if bl else 0.0,
            "std":  round(float(np.std(bl, ddof=1)), 1) if len(bl) > 1 else 0.0,
            "z": z, "status": _status(z),
        })

    # ── Anomaly detection ─────────────────────────────────────────────────────
    anomalies = []
    for row in zscore_rows:
        if row["z"] < -2:
            anomalies.append({"type": "zscore", **row})
    for shown_ev, applied_ev in PRICE_RECO_PAIRS + REST_RECO_PAIRS:
        if _s(u0, shown_ev) > 0 and _s(u0, applied_ev) == 0:
            anomalies.append({"type": "tracking_risk", "event": shown_ev})
    for shown_ev, applied_ev in REST_RECO_PAIRS:
        if _s(u0, applied_ev) > _s(u0, shown_ev) > 0:
            anomalies.append({"type": "funnel_inversion", "event": shown_ev})

    try:
        from datetime import date as _date
        week_start = _date.fromisoformat(w0["from"])
        n_baseline = (week_start - BASELINE_DATE).days // 7
    except Exception:
        n_baseline = None

    return {
        "period_from": w0["from"],
        "period_to":   w0["to"],
        "n_baseline":  n_baseline,
        # traffic (7-day — for Z-score baseline)
        "traffic_u0":           traffic_u0,
        "traffic_e0":           traffic_e0,
        "traffic_u1":           traffic_u1,
        # traffic (30-day — L0 display)
        "traffic_30d_u0":       traffic_30d_u0,
        "traffic_30d_u1":       traffic_30d_u1,
        "traffic_30d_from0":    traffic_30d_from0,
        "traffic_30d_to0":      traffic_30d_to0,
        "traffic_30d_from1":    traffic_30d_from1,
        "traffic_30d_to1":      traffic_30d_to1,
        "traffic_30d_wow_pct":  traffic_30d_wow_pct,
        # MAU
        "traffic_mau":          traffic_mau,
        "traffic_mau_months":   traffic_mau_months,
        "traffic_mau_values":   traffic_mau_values,
        # A&P combined engagement
        "ap_shown_u":       ap_shown_u,
        "ap_click_u":       ap_click_u,
        "ap_eng_rate":      ap_eng_rate,
        "prev_ap_eng_rate": prev_ap_eng_rate,
        "ap_eng_delta":     ap_eng_delta,
        # pills
        "pill_shown_rows":         pill_shown_rows,
        "pill_click_rows":         pill_click_rows,
        "other_pill_rows":         other_pill_rows,
        "tot_other_pills_shown_u": tot_other_pills_shown_u,
        "tot_other_pills_viewed_u":tot_other_pills_viewed_u,
        "tot_pills_shown_u":     tot_pills_shown_u,
        "tot_pills_shown_t":     tot_pills_shown_t,
        "tot_pills_clicked_u":   tot_pills_clicked_u,
        "tot_pills_clicked_t":   tot_pills_clicked_t,
        "prev_pills_shown_u":    prev_pills_shown_u,
        "prev_pills_clicked_u":  prev_pills_clicked_u,
        "pill_click_rate":       pill_click_rate,
        # alerts
        "alert_rows":            alert_rows,
        "tot_alert_shown_u":     tot_alert_shown_u,
        "tot_alert_clicked_u":   tot_alert_clicked_u,
        "tot_alert_shown_t":     tot_alert_shown_t,
        "tot_alert_clicked_t":   tot_alert_clicked_t,
        "prev_alert_shown_u":    tot_prev_shown_u,
        "prev_alert_clicked_u":  tot_prev_clicked_u,
        # recos
        "price_sub":             price_sub,
        "rest_reco_rows":        rest_reco_rows,
        "price_shown_u":          price_shown_u,
        "price_applied_u":        price_applied_u,
        "prev_price_shown_u":     prev_price_shown_u,
        "prev_price_applied_u":   prev_price_applied_u,
        "tot_reco_shown_u":      tot_reco_shown_u,
        "tot_reco_applied_u":    tot_reco_applied_u,
        "tot_reco_shown_t":      tot_reco_shown_t,
        "tot_reco_applied_t":    tot_reco_applied_t,
        "prev_reco_shown_u":     prev_reco_shown_u,
        "prev_reco_applied_u":   prev_reco_applied_u,
        # z-scores + anomalies
        "zscore_rows":           zscore_rows,
        "anomalies":             anomalies,
    }
