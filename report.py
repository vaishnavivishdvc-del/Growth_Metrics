"""
Report builder.
build(m)  → {"subject": str, "html": str, "chat_text": str}
"""

from __future__ import annotations
from datetime import date as _date

from config import BASELINE_DATE


# ── helpers ───────────────────────────────────────────────────────────────────

def _wow(curr: float, prev: float) -> str:
    if not prev:
        return "—"
    v = round((curr - prev) / prev * 100, 1)
    arrow = "▲" if v > 0 else ("▼" if v < 0 else "—")
    return f"{arrow} {abs(v)}%"

def _eps(total: float, uniq: float) -> str:
    return f"{round(total / uniq, 1)}x" if uniq else "—"

def _fmt(n) -> str:
    return f"{int(n):,}" if n else "0"

def _pct(v: float) -> str:
    return f"{v}%"


# ── anomaly text helpers ──────────────────────────────────────────────────────

_ANOMALY_ACTIONS = {
    "Conversion Alert CTR":    "Audit `gc_conversion_alert_cta_click`; check if alert threshold or CTA copy changed in last release.",
    "Impressions Alert CTR":   "Audit `gc_impressions_alert_cta_click`; check alert rendering and trigger logic.",
    "Pill Click Rate":         "Check for UI changes to pill rendering; segment by Channel to isolate.",
    "Overall Reco CTR":        "Cross-check each reco type's applied event; check release log for last 7 days.",
    "Price Reco CTR":          "Verify price reco applied events are firing; check for UI changes to apply CTA.",
    "F-Assured CTR":           "Verify `gc_fa_recco_applied` instrumentation; check if F-Assured eligibility criteria changed.",
}

_TRACKING_ACTIONS = {
    "tracking_risk":    "Verify event instrumentation — shown > 0 but applied = 0 suggests a broken apply CTA or missing event.",
    "funnel_inversion": "Segment shown event by Channel to isolate the tracking gap (applied > shown is impossible organically).",
}


def _anomaly_blocks(anomalies: list[dict]) -> str:
    if not anomalies:
        return ""
    blocks = []
    for a in anomalies:
        if a["type"] == "zscore":
            action = _ANOMALY_ACTIONS.get(a["name"], "Investigate metric drop.")
            blocks.append(
                f"<p><b>🔴 {a['name']} — CRITICAL (Z = {a['z']})</b><br>"
                f"This week: {_pct(a['value'])} | 3-wk avg: {_pct(a['mean'])} ± {_pct(a['std'])}<br>"
                f"<b>Action:</b> {action}</p>"
            )
        elif a["type"] == "tracking_risk":
            label = a["event"].replace("gc_", "").replace("_recco", " reco").replace("_", " ")
            blocks.append(
                f"<p><b>⚠️ Tracking Risk — {label}</b><br>"
                f"Shown &gt; 0 but applied = 0 this week.<br>"
                f"<b>Action:</b> {_TRACKING_ACTIONS['tracking_risk']}</p>"
            )
        elif a["type"] == "funnel_inversion":
            label = a["event"].replace("gc_", "").replace("_recco", " reco").replace("_", " ")
            blocks.append(
                f"<p><b>⚠️ Funnel Inversion — {label}</b><br>"
                f"Applied &gt; Shown — impossible organically.<br>"
                f"<b>Action:</b> {_TRACKING_ACTIONS['funnel_inversion']}</p>"
            )
    return "\n".join(blocks)


# ── table builder ─────────────────────────────────────────────────────────────

def _tbl(headers: list[str], rows: list[list]) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
    return (
        "<table>"
        f"<thead><tr>{th}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
    )


# ── per-section callout helpers ───────────────────────────────────────────────

def _pill_callout(m: dict) -> str:
    pcr      = m["pill_click_rate"]
    prev_pcr = round(m["prev_pills_clicked_u"] / m["prev_pills_shown_u"] * 100, 1) if m["prev_pills_shown_u"] else 0
    delta    = round(pcr - prev_pcr, 1)
    wow_u    = round((m["tot_pills_shown_u"] - m["prev_pills_shown_u"]) / m["prev_pills_shown_u"] * 100, 1) if m["prev_pills_shown_u"] else 0
    lines = []
    if abs(wow_u) > 5:
        dir_ = "up" if wow_u > 0 else "down"
        lines.append(f"Pill reach is {dir_} {abs(wow_u):.1f}% WoW — monitor for sustained {'growth' if wow_u > 0 else 'decline'}.")
    if abs(delta) >= 1:
        dir_ = "improved" if delta > 0 else "dropped"
        lines.append(f"Pill click rate {dir_} {abs(delta):.1f} pp to {_pct(pcr)} — {'healthy engagement trend.' if delta > 0 else 'check pill UI or copy for changes.'}")
    else:
        lines.append(f"Pill click rate stable at {_pct(pcr)} (Δ {'+' if delta >= 0 else ''}{delta} pp vs last week).")
    return "<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"


def _alert_callout(m: dict) -> str:
    alert_ctr      = round(m["tot_alert_clicked_u"] / m["tot_alert_shown_u"] * 100, 1) if m["tot_alert_shown_u"] else 0
    prev_alert_ctr = round(m["prev_alert_clicked_u"] / m["prev_alert_shown_u"] * 100, 1) if m["prev_alert_shown_u"] else 0
    delta          = round(alert_ctr - prev_alert_ctr, 1)
    imp_ctr  = round(m["alert_rows"][0]["ctr"], 1) if m.get("alert_rows") else 0
    conv_ctr = round(m["alert_rows"][1]["ctr"], 1) if len(m.get("alert_rows", [])) > 1 else 0
    lines = []
    lines.append(
        f"Impressions Alert CTR {_pct(imp_ctr)} vs Conversion Alert CTR {_pct(conv_ctr)} — "
        f"{'conversion alert under-performing; consider copy refresh.' if conv_ctr < imp_ctr - 1 else 'both alert types performing comparably.'}"
    )
    if abs(delta) >= 1:
        dir_ = "improved" if delta > 0 else "dropped"
        lines.append(f"Overall alert CTR {dir_} {abs(delta):.1f} pp WoW to {_pct(alert_ctr)}.")
    return "<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"


def _reco_callout(m: dict) -> str:
    reco_ctr      = round(m["tot_reco_applied_u"] / m["tot_reco_shown_u"] * 100, 1) if m["tot_reco_shown_u"] else 0
    prev_reco_ctr = round(m["prev_reco_applied_u"] / m["prev_reco_shown_u"] * 100, 1) if m.get("prev_reco_shown_u") else 0
    delta         = round(reco_ctr - prev_reco_ctr, 1)
    all_recos = m["rest_reco_rows"] + [{"name": "Price Recos", "applied_u": m["price_applied_u"],
                                        "shown_u": m["price_shown_u"],
                                        "adoption": round(m["price_applied_u"] / m["price_shown_u"] * 100, 1) if m["price_shown_u"] else 0}]
    top   = max(all_recos, key=lambda r: r["applied_u"], default=None)
    lines = []
    if top:
        lines.append(f"{top['name']} leads with {_fmt(top['applied_u'])} sellers applied ({_pct(top['adoption'])} adoption rate).")
    if abs(delta) >= 1:
        dir_ = "improved" if delta > 0 else "dropped"
        lines.append(f"Overall reco adoption {dir_} {abs(delta):.1f} pp WoW to {_pct(reco_ctr)} — {'momentum building.' if delta > 0 else 'investigate which reco types are softening.'}")
    no_apply = [r["name"] for r in m["rest_reco_rows"] if r["shown_u"] > 0 and r["applied_u"] == 0]
    if no_apply:
        lines.append(f"⚠️ Tracking risk: {', '.join(no_apply)} shown to sellers but 0 applied — verify instrumentation.")
    return "<ul>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul>"


# ── KPI summary cards ─────────────────────────────────────────────────────────

def _status_icon(d: float, is_pct_change: bool = False) -> tuple[str, str]:
    """Return (emoji, css_class) for a WoW delta. is_pct_change=True for traffic %."""
    if is_pct_change:
        if d < -15: return ("🔴", "red")
        if d < -5:  return ("🟡", "warn")
        return ("🟢", "ok")
    if d < -3: return ("🔴", "red")
    if d < -1: return ("🟡", "warn")
    return ("🟢", "ok")


def _kpi_cards(m: dict) -> str:
    ap_eng        = m["ap_eng_rate"]
    prev_ap_eng   = m["prev_ap_eng_rate"]
    ap_delta      = m["ap_eng_delta"]

    reco_adoption      = round(m["tot_reco_applied_u"] / m["tot_reco_shown_u"] * 100, 1) if m["tot_reco_shown_u"] else 0
    prev_reco_adoption = round(m["prev_reco_applied_u"] / m["prev_reco_shown_u"] * 100, 1) if m.get("prev_reco_shown_u") else 0
    reco_delta         = round(reco_adoption - prev_reco_adoption, 1)

    traffic_u0  = m["traffic_u0"]
    traffic_u1  = m["traffic_u1"]
    traffic_wow = m["traffic_wow_pct"]
    traffic_mau = m["traffic_mau"]
    mau_label   = f"MAU ({', '.join(m['traffic_mau_months'])})" if m.get("traffic_mau_months") else "MAU"

    def _dp(d: float) -> str:
        return f"{'+' if d >= 0 else ''}{d} pp"

    t_icon, t_cls = _status_icon(traffic_wow, is_pct_change=True)
    a_icon, a_cls = _status_icon(ap_delta)
    r_icon, r_cls = _status_icon(reco_delta)

    c  = "border:1px solid #e0e0e0;padding:8px 12px;font-size:13px;"
    ch = "background:#f0f4ff;padding:8px 12px;border:1px solid #d0d7e8;text-align:center;"

    card = (
        '<table style="width:100%;border-collapse:collapse;margin-bottom:16px;font-size:13px;">'
        '<thead><tr>'
        f'<th style="background:#f0f4ff;padding:8px 12px;border:1px solid #d0d7e8;width:18%;"></th>'
        f'<th style="{ch}">Traffic Report Visits</th>'
        f'<th style="{ch}">A&amp;P Engagement Rate</th>'
        f'<th style="{ch}">Reco Adoption Rate</th>'
        '</tr></thead><tbody>'
        f'<tr><td style="{c}font-weight:bold;">This week</td>'
        f'<td style="{c}text-align:center;font-weight:bold;">{_fmt(traffic_u0)} sellers</td>'
        f'<td style="{c}text-align:center;font-weight:bold;">{_pct(ap_eng)}</td>'
        f'<td style="{c}text-align:center;font-weight:bold;">{_pct(reco_adoption)}</td></tr>'
        f'<tr><td style="{c}font-weight:bold;">Last week</td>'
        f'<td style="{c}text-align:center;">{_fmt(traffic_u1)} sellers</td>'
        f'<td style="{c}text-align:center;">{_pct(prev_ap_eng)}</td>'
        f'<td style="{c}text-align:center;">{_pct(prev_reco_adoption)}</td></tr>'
        f'<tr><td style="{c}font-weight:bold;">WoW change</td>'
        f'<td style="{c}text-align:center;">{traffic_wow:+.1f}%</td>'
        f'<td style="{c}text-align:center;">{_dp(ap_delta)}</td>'
        f'<td style="{c}text-align:center;">{_dp(reco_delta)}</td></tr>'
        f'<tr><td style="{c}font-weight:bold;">Status</td>'
        f'<td style="{c}text-align:center;"><span class="{t_cls}">{t_icon}</span></td>'
        f'<td style="{c}text-align:center;"><span class="{a_cls}">{a_icon}</span></td>'
        f'<td style="{c}text-align:center;"><span class="{r_cls}">{r_icon}</span></td></tr>'
        '</tbody></table>'
    )

    mau_months_list  = m.get("traffic_mau_months", [])
    mau_values_list  = m.get("traffic_mau_values", [])
    mau_months_str   = " | ".join(
        f"{mo}: {_fmt(val)}"
        for mo, val in zip(mau_months_list, mau_values_list)
    ) if mau_values_list else "—"
    card += (
        f'<p style="font-size:13px;margin:4px 0 12px;">📊 Traffic MAU ({mau_label}): '
        f'<b>{_fmt(traffic_mau)} sellers/month</b> — {mau_months_str}</p>'
        '<p style="font-size:11px;color:#888;">Definitions: A&amp;P Engagement = (unique alert clickers + unique pill clickers) ÷ (unique alert viewers + unique pill viewers). '
        'Reco Adoption = unique sellers applied any reco ÷ unique sellers shown any reco. All rates: unique sellers basis.</p>'
    )

    rca_parts = []

    if ap_delta < -1:
        # Identify whether alerts or pills drove the drop
        alert_ctr      = round(m["tot_alert_clicked_u"] / m["tot_alert_shown_u"] * 100, 1) if m["tot_alert_shown_u"] else 0
        prev_alert_ctr = round(m["prev_alert_clicked_u"] / m["prev_alert_shown_u"] * 100, 1) if m["prev_alert_shown_u"] else 0
        pill_ctr       = m["pill_click_rate"]
        prev_pill_ctr  = round(m["prev_pills_clicked_u"] / m["prev_pills_shown_u"] * 100, 1) if m["prev_pills_shown_u"] else 0

        # Denominator vs Numerator analysis
        shown_wow  = round((m["ap_shown_u"] - (m["prev_pills_shown_u"] + m["prev_alert_shown_u"])) / (m["prev_pills_shown_u"] + m["prev_alert_shown_u"]) * 100, 1) if (m["prev_pills_shown_u"] + m["prev_alert_shown_u"]) else 0
        click_wow  = round((m["ap_click_u"] - (m["prev_pills_clicked_u"] + m["prev_alert_clicked_u"])) / (m["prev_pills_clicked_u"] + m["prev_alert_clicked_u"]) * 100, 1) if (m["prev_pills_clicked_u"] + m["prev_alert_clicked_u"]) else 0

        if shown_wow < -10:
            driver = f"Denominator-driven (reach): shown unique sellers fell {shown_wow:+.1f}% WoW — trigger/eligibility change suspected."
        elif click_wow < -10:
            driver = f"Numerator-driven (engagement): shown stable, but clicks fell {click_wow:+.1f}% WoW — sellers seeing but not acting."
        else:
            driver = f"Combined: shown {shown_wow:+.1f}% WoW, clicks {click_wow:+.1f}% WoW."

        rca_tbl = [[r["name"], _fmt(r["shown_u"]), _fmt(r["shown_t"]),
                    _fmt(r["clicked_u"]), _fmt(r["clicked_t"]),
                    _pct(r["ctr"]), _pct(r["prev_ctr"]), f"{r['delta_pp']:+.1f} pp"]
                   for r in m["alert_rows"]]
        rca_parts.append(
            f"<h3>A&amp;P Engagement Drop — RCA</h3>"
            f"<p><b>Driver:</b> {driver}</p>"
            f"<p>Alert CTR: {_pct(alert_ctr)} ({alert_ctr - prev_alert_ctr:+.1f} pp) | "
            f"Pill CTR: {_pct(pill_ctr)} ({pill_ctr - prev_pill_ctr:+.1f} pp)</p>"
            + _tbl(["Alert Type", "Shown (Unique)", "Shown (Events)",
                    "Clicked (Unique)", "Clicked (Events)", "CTR", "Prev CTR", "Δ pp"], rca_tbl)
        )

    if reco_delta < -1:
        price_adp      = round(m["price_applied_u"] / m["price_shown_u"] * 100, 1) if m["price_shown_u"] else 0
        prev_price_adp = round(m.get("prev_price_applied_u", 0) / m["prev_price_shown_u"] * 100, 1) if m.get("prev_price_shown_u") else 0
        rca_tbl = [
            ["Price Recos (All)", _fmt(m["price_shown_u"]), _fmt(m["price_applied_u"]),
             _pct(price_adp), f"{round(price_adp - prev_price_adp, 1):+.1f} pp",
             "Den" if m["price_shown_u"] < m.get("prev_price_shown_u", m["price_shown_u"]) * 0.9 else "Num/Rate"]
        ] + [
            [r["name"], _fmt(r["shown_u"]), _fmt(r["applied_u"]),
             _pct(r["adoption"]), f"{round(r['adoption'] - r['prev_adoption'], 1):+.1f} pp",
             "Den" if r["shown_u"] < r.get("prev_shown_u", r["shown_u"]) * 0.8 else "Num/Rate"]
            for r in m["rest_reco_rows"]
        ]
        rca_parts.append(
            "<h3>Reco Adoption Drop — RCA by Reco Type</h3>"
            + _tbl(["Reco Type", "Sellers Shown", "Sellers Applied", "Adoption %", "Δ pp", "Driver"], rca_tbl)
        )

    return card + "\n".join(rca_parts)


# ── HTML report ───────────────────────────────────────────────────────────────

_CSS = """
<style>
  body { font-family: Arial, sans-serif; color: #222; font-size: 14px; }
  h1 { color: #1a1a2e; font-size: 20px; margin-bottom: 4px; }
  h2 { color: #16213e; font-size: 16px; margin: 20px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
  h3 { font-size: 14px; margin: 14px 0 4px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: 13px; }
  th { background: #f0f4ff; color: #333; font-weight: bold; text-align: left;
       padding: 7px 10px; border: 1px solid #d0d7e8; }
  td { padding: 6px 10px; border: 1px solid #e0e0e0; }
  tr:nth-child(even) td { background: #fafafa; }
  ul { margin: 6px 0 12px 18px; }
  li { margin-bottom: 4px; }
  p  { margin: 6px 0; }
  .red  { color: #c0392b; font-weight: bold; }
  .warn { color: #e67e22; font-weight: bold; }
  .ok   { color: #27ae60; }
  .period { font-size: 12px; color: #666; margin-bottom: 18px; }
</style>
"""


def build_html(m: dict) -> str:
    period = f"{m['period_from']} – {m['period_to']}"
    pf, pt = m["period_from"], m["period_to"]

    # ── Funnel T1: Pills ──────────────────────────────────────────────────────
    pill_uniq_rows = [
        ["Pills Shown (Reach)",
         _fmt(m["tot_pills_shown_u"]),
         _fmt(m["prev_pills_shown_u"]),
         _wow(m["tot_pills_shown_u"], m["prev_pills_shown_u"]),
         "100%"],
        ["Pills Clicked",
         _fmt(m["tot_pills_clicked_u"]),
         _fmt(m["prev_pills_clicked_u"]),
         _wow(m["tot_pills_clicked_u"], m["prev_pills_clicked_u"]),
         _pct(m["pill_click_rate"])],
    ]
    pill_tot_rows = [
        ["Pills Shown (Impressions)",
         _fmt(m["tot_pills_shown_t"]),
         "—",
         "—",
         _eps(m["tot_pills_shown_t"], m["tot_pills_shown_u"])],
        ["Pills Clicked (Total Clicks)",
         _fmt(m["tot_pills_clicked_t"]),
         "—",
         "—",
         _eps(m["tot_pills_clicked_t"], m["tot_pills_clicked_u"])],
    ]

    # ── Funnel T2: Alerts ─────────────────────────────────────────────────────
    alert_tbl_rows = []
    for row in m["alert_rows"]:
        delta_str = f"{row['delta_pp']:+.1f} pp"
        alert_tbl_rows.append([
            row["name"], _fmt(row["shown_u"]), _fmt(row["shown_t"]),
            _fmt(row["clicked_u"]), _fmt(row["clicked_t"]),
            _pct(row["ctr"]), _pct(row["prev_ctr"]), delta_str,
        ])
    total_ctr = round(m["tot_alert_clicked_u"] / m["tot_alert_shown_u"] * 100, 1) if m["tot_alert_shown_u"] else 0
    prev_total_ctr = round(m["prev_alert_clicked_u"] / m["prev_alert_shown_u"] * 100, 1) if m["prev_alert_shown_u"] else 0
    alert_tbl_rows.append([
        "<b>Total Alerts</b>",
        _fmt(m["tot_alert_shown_u"]), _fmt(m["tot_alert_shown_t"]),
        _fmt(m["tot_alert_clicked_u"]), _fmt(m["tot_alert_clicked_t"]),
        _pct(total_ctr), _pct(prev_total_ctr),
        f"{round(total_ctr - prev_total_ctr, 1):+.1f} pp",
    ])

    # ── Funnel T3: Recos ──────────────────────────────────────────────────────
    reco_uniq_rows = [
        ["Pills Clicked (entry)",
         _fmt(m["tot_pills_clicked_u"]), _fmt(m["prev_pills_clicked_u"]),
         _wow(m["tot_pills_clicked_u"], m["prev_pills_clicked_u"]), "100%"],
        ["Any Reco Shown",
         _fmt(m["tot_reco_shown_u"]), _fmt(m["prev_reco_shown_u"]),
         _wow(m["tot_reco_shown_u"], m["prev_reco_shown_u"]), "—"],
        ["Any Reco Applied",
         _fmt(m["tot_reco_applied_u"]), _fmt(m["prev_reco_applied_u"]),
         _wow(m["tot_reco_applied_u"], m["prev_reco_applied_u"]),
         _pct(round(m["tot_reco_applied_u"] / m["tot_reco_shown_u"] * 100, 1) if m["tot_reco_shown_u"] else 0)],
    ]
    reco_tot_rows = [
        ["Pill Click Events",
         _fmt(m["tot_pills_clicked_t"]), "—", "—",
         _eps(m["tot_pills_clicked_t"], m["tot_pills_clicked_u"])],
        ["Reco Shown Events",
         _fmt(m["tot_reco_shown_t"]), "—", "—",
         _eps(m["tot_reco_shown_t"], m["tot_reco_shown_u"])],
        ["Reco Applied Events",
         _fmt(m["tot_reco_applied_t"]), "—", "—",
         _eps(m["tot_reco_applied_t"], m["tot_reco_applied_u"])],
    ]

    # ── Z-score table ─────────────────────────────────────────────────────────
    z_rows = []
    for row in m["zscore_rows"]:
        badge = f'<span class="{"red" if row["status"]=="🔴" else ("warn" if row["status"]=="🟡" else "ok")}">{row["status"]}</span>'
        z_rows.append([
            row["name"], _pct(row["value"]), _pct(row["mean"]),
            _pct(row["std"]), str(row["z"]), badge,
        ])

    # ── Reco ranking ──────────────────────────────────────────────────────────
    price_adoption = round(m["price_applied_u"] / m["price_shown_u"] * 100, 1) if m["price_shown_u"] else 0
    all_reco_tbl = [
        ["Price Recos (All)",
         _fmt(m["price_applied_u"]),
         "—",
         _eps(m["price_applied_u"], m["price_shown_u"]),
         _fmt(m["price_shown_u"]),
         _pct(price_adoption), "—", "—"],
    ] + [
        [r["name"], _fmt(r["applied_u"]), _fmt(r["applied_t"]),
         _eps(r["applied_t"], r["applied_u"]),
         _fmt(r["shown_u"]), _pct(r["adoption"]), _pct(r["prev_adoption"]),
         f"{r.get('wow_applied', 0):+.1f}%"]
        for r in sorted(m["rest_reco_rows"], key=lambda x: x["applied_u"], reverse=True)
    ]

    price_sub_rows = [
        [p["name"], _fmt(p["shown_u"]), _fmt(p["shown_t"]),
         _fmt(p["applied_u"]), _fmt(p["applied_t"]), _pct(p["adoption"])]
        for p in m["price_sub"]
    ]

    # ── Pill click ranking ────────────────────────────────────────────────────
    pill_rank_rows = sorted(m["pill_click_rows"], key=lambda r: r["clicked_u"], reverse=True)
    pill_rank_tbl = [
        [str(i + 1), r["name"], _fmt(r["clicked_u"]), _fmt(r["clicked_t"]),
         _eps(r["clicked_t"], r["clicked_u"]),
         _fmt(r["prev_u"]),
         _wow(r["clicked_u"], r["prev_u"])]
        for i, r in enumerate(pill_rank_rows)
        if r["clicked_u"] > 0
    ]

    # ── Anomaly section HTML ──────────────────────────────────────────────────
    anomaly_html = _anomaly_blocks(m["anomalies"])
    if not anomaly_html:
        anomaly_html = "<p><em>No anomalies detected this week.</em></p>"

    n = m.get("n_baseline")
    baseline_label = (
        f"Based on {n}-week cumulative baseline (since Jun 17, 2026)"
        if isinstance(n, int) and n > 0
        else "Baseline establishing — WoW comparison used until ≥4 weeks of data"
    )
    week_label = f"Week {n + 1} since Jun 17" if isinstance(n, int) else "Weekly Brief"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_CSS}</head>
<body>
<h1>📊 Growth Central Weekly Brief</h1>
<p class="period">Period: {period} | {week_label} | Generated by gc_brief automation</p>

<h2>KPI Summary</h2>
{_kpi_cards(m)}

<h2>Alert Metrics — {pf} to {pt}</h2>
{_tbl(
    ["Alert Type", "Shown (Unique)", "Shown (Events)",
     "Clicked (Unique)", "Clicked (Events)", "CTR", "Prev 7d CTR", "Δ pp"],
    alert_tbl_rows
)}
{_alert_callout(m)}

<h2>Pill Metrics — {pf} to {pt}</h2>
<h3>Unique Sellers</h3>
{_tbl(["Stage", "This 7 Days", "Prev 7 Days", "WoW %", "Conversion"], pill_uniq_rows)}
<h3>Total Events</h3>
{_tbl(["Stage", "This 7 Days", "Prev 7 Days", "WoW %", "Events/Seller"], pill_tot_rows)}
{_pill_callout(m)}

<h2>Feature Traction — {pf} to {pt}</h2>

<h3>Reco Type Ranking</h3>
{_tbl(
    ["Reco Type", "Sellers Applied", "Total Events", "Events/Seller",
     "Sellers Shown", "Adoption %", "Prev Adoption", "WoW Change"],
    all_reco_tbl
)}
{_reco_callout(m)}

<h3>Price Reco Sub-breakdown</h3>
{_tbl(
    ["Sub-type", "Shown (Unique)", "Shown (Events)",
     "Sellers Applied", "Total Events", "Adoption %"],
    price_sub_rows
)}

<h3>Pill Click Ranking</h3>
{_tbl(
    ["Rank", "Pill", "Unique Sellers", "Total Clicks",
     "Clicks/Seller", "Prev 7d Unique", "WoW Change"],
    pill_rank_tbl
)}

<h2>Negative Signals</h2>
<p><em>{baseline_label}</em></p>
{_tbl(
    ["Signal", "This 7 Days", "Baseline Avg", "Std Dev", "Z-score", "Status"],
    z_rows
)}

<h2>Anomaly Alerts</h2>
{anomaly_html}

</body>
</html>"""
    return html


# ── Google Chat text (KPI summary + Reco RCA only) ───────────────────────────

def build_chat_text(m: dict) -> str:
    period = f"{m['period_from']} – {m['period_to']}"

    traffic_u0  = m["traffic_u0"]
    traffic_wow = m["traffic_wow_pct"]

    ap_eng    = m["ap_eng_rate"]
    ap_delta  = m["ap_eng_delta"]

    reco_adoption      = round(m["tot_reco_applied_u"] / m["tot_reco_shown_u"] * 100, 1) if m["tot_reco_shown_u"] else 0
    prev_reco_adoption = round(m["prev_reco_applied_u"] / m["prev_reco_shown_u"] * 100, 1) if m.get("prev_reco_shown_u") else 0
    reco_delta         = round(reco_adoption - prev_reco_adoption, 1)

    def _dp(d: float, unit: str = "pp") -> str:
        return f"{'+' if d >= 0 else ''}{d} {unit} WoW"

    def _si_pp(d: float) -> str:
        return "🔴" if d < -3 else ("🟡" if d < -1 else "🟢")

    def _si_pct(d: float) -> str:
        return "🔴" if d < -15 else ("🟡" if d < -5 else "🟢")

    lines = [
        f"*📊 GC Brief — {period}*",
        "",
        f"📈 Traffic Visits:    *{_fmt(traffic_u0)} sellers*  ({_dp(traffic_wow, '%')})  {_si_pct(traffic_wow)}",
        f"💡 A&P Engagement:  *{_pct(ap_eng)}*  ({_dp(ap_delta)})  {_si_pp(ap_delta)}",
        f"✅ Reco Adoption:    *{_pct(reco_adoption)}*  ({_dp(reco_delta)})  {_si_pp(reco_delta)}",
    ]

    if ap_delta < -1:
        alert_ctr      = round(m["tot_alert_clicked_u"] / m["tot_alert_shown_u"] * 100, 1) if m["tot_alert_shown_u"] else 0
        prev_alert_ctr = round(m["prev_alert_clicked_u"] / m["prev_alert_shown_u"] * 100, 1) if m["prev_alert_shown_u"] else 0
        pill_ctr      = m["pill_click_rate"]
        prev_pill_ctr = round(m["prev_pills_clicked_u"] / m["prev_pills_shown_u"] * 100, 1) if m["prev_pills_shown_u"] else 0
        lines += ["", "*A&P Engagement Drop — breakdown:*",
                  f"  🔔 Alert CTR:  {_pct(alert_ctr)}  ({alert_ctr - prev_alert_ctr:+.1f} pp)",
                  f"  💊 Pill CTR:   {_pct(pill_ctr)}  ({pill_ctr - prev_pill_ctr:+.1f} pp)"]

    if reco_delta < -1:
        price_adp = round(m["price_applied_u"] / m["price_shown_u"] * 100, 1) if m["price_shown_u"] else 0
        prev_price_adp = round(m.get("prev_price_applied_u", 0) / m["prev_price_shown_u"] * 100, 1) if m.get("prev_price_shown_u") else 0
        all_recos = [("Price Recos", price_adp, prev_price_adp)] + [
            (r["name"], r["adoption"], r["prev_adoption"]) for r in m["rest_reco_rows"]
        ]
        lines += ["", "*Reco Adoption — by Type:*"]
        for name, adp, prev_adp in all_recos:
            d = round(adp - prev_adp, 1)
            lines.append(f"  {_si_pp(d)} {name}: *{_pct(adp)}*  ({_dp(d)})")
        biggest = max(all_recos, key=lambda x: abs(x[1] - x[2]))
        bname, badp, bprev = biggest
        bd = round(badp - bprev, 1)
        lines.append(f"Biggest drop: {bname} ({bd:+.1f} pp WoW)")

    lines += ["", "_Full report sent via email._"]
    return "\n".join(lines)


# ── entry point ───────────────────────────────────────────────────────────────

def build(m: dict) -> dict:
    period = f"{m['period_from']} – {m['period_to']}"
    return {
        "subject": f"GC Weekly Brief | {period}",
        "html":      build_html(m),
        "chat_text": build_chat_text(m),
    }
