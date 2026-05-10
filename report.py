"""
Report builder.
build(m)  → {"subject": str, "html": str, "chat_text": str}
"""

from __future__ import annotations


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


# ── executive summary (auto-generated) ───────────────────────────────────────

def _exec_summary(m: dict) -> str:
    bullets = []

    # 1. Pills reach + engagement rate vs prev week
    pcr      = m["pill_click_rate"]
    prev_pcr = round(m["prev_pills_clicked_u"] / m["prev_pills_shown_u"] * 100, 1) if m["prev_pills_shown_u"] else 0
    pills_wow = _wow(m["tot_pills_shown_u"], m["prev_pills_shown_u"])
    pcr_dir   = f"({'+' if pcr >= prev_pcr else ''}{round(pcr - prev_pcr, 1)} pp vs last week)"
    bullets.append(
        f"{_fmt(m['tot_pills_shown_u'])} sellers saw pills this week ({pills_wow} WoW); "
        f"pill click rate {_pct(pcr)} {pcr_dir}."
    )

    # 2. Alerts engagement rate (unique CTR) vs prev week
    alert_ctr      = round(m["tot_alert_clicked_u"] / m["tot_alert_shown_u"] * 100, 1) if m["tot_alert_shown_u"] else 0
    prev_alert_ctr = round(m["prev_alert_clicked_u"] / m["prev_alert_shown_u"] * 100, 1) if m["prev_alert_shown_u"] else 0
    alert_dir      = f"({'+' if alert_ctr >= prev_alert_ctr else ''}{round(alert_ctr - prev_alert_ctr, 1)} pp vs last week)"
    bullets.append(
        f"{_fmt(m['tot_alert_shown_u'])} sellers reached by alerts; "
        f"alert engagement rate {_pct(alert_ctr)} {alert_dir}."
    )

    # 3. Overall reco adoption rate (unique applied / unique shown) vs prev week
    reco_ctr      = round(m["tot_reco_applied_u"] / m["tot_reco_shown_u"] * 100, 1) if m["tot_reco_shown_u"] else 0
    prev_reco_ctr = round(m["prev_reco_applied_u"] / m["prev_reco_shown_u"] * 100, 1) if m.get("prev_reco_shown_u") else 0
    reco_dir      = f"({'+' if reco_ctr >= prev_reco_ctr else ''}{round(reco_ctr - prev_reco_ctr, 1)} pp vs last week)"
    bullets.append(
        f"Overall reco adoption: {_pct(reco_ctr)} — {_fmt(m['tot_reco_applied_u'])} sellers applied "
        f"out of {_fmt(m['tot_reco_shown_u'])} shown {reco_dir}."
    )

    # 4. Anomaly callout
    critical = [a for a in m["anomalies"] if a.get("type") == "zscore"]
    if critical:
        names = ", ".join(a["name"] for a in critical)
        bullets.append(f"⚠️ Anomaly detected: {names} — see Anomaly Alerts section below.")
    else:
        bullets.append("✅ No critical anomalies this week. All engagement signals within normal range.")

    return "<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"


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

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">{_CSS}</head>
<body>
<h1>📊 Growth Central Weekly Brief</h1>
<p class="period">Period: {period} | Generated by gc_brief automation</p>

<h2>🔍 Executive Summary</h2>
{_exec_summary(m)}

<h2>🔁 Funnel Conversion &amp; Engagement</h2>

<h3>Funnel 1 — Pills — {pf} to {pt}</h3>
<p><b>Unique Sellers</b></p>
{_tbl(["Stage", "This 7 Days", "Prev 7 Days", "WoW %", "Conversion"], pill_uniq_rows)}
<p><b>Total Events</b></p>
{_tbl(["Stage", "This 7 Days", "Prev 7 Days", "WoW %", "Events/Seller"], pill_tot_rows)}
{_pill_callout(m)}

<h3>Funnel 2 — Alert Engagement — {pf} to {pt}</h3>
{_tbl(
    ["Alert Type", "Shown (Unique)", "Shown (Events)",
     "Clicked (Unique)", "Clicked (Events)", "CTR", "Prev 7d CTR", "Δ pp"],
    alert_tbl_rows
)}
{_alert_callout(m)}

<h3>Funnel 3 — Reco Adoption — {pf} to {pt}</h3>
<p><b>Unique Sellers</b></p>
{_tbl(["Stage", "This 7 Days", "Prev 7 Days", "WoW %", "Conversion"], reco_uniq_rows)}
<p><b>Total Events</b></p>
{_tbl(["Stage", "This 7 Days", "Prev 7 Days", "WoW %", "Events/Seller"], reco_tot_rows)}
{_reco_callout(m)}

<h2>⚠️ Negative Signals</h2>
{_tbl(
    ["Signal", "This 7 Days", "Prev 4-Wk Avg", "Std Dev", "Z-score", "Status"],
    z_rows
)}

<h2>🏆 Feature Traction</h2>

<h3>Reco Ranking — {pf} to {pt}</h3>
{_tbl(
    ["Reco Type", "Sellers Applied", "Total Events", "Events/Seller",
     "Unique Shown", "Adoption %", "Prev Adoption", "WoW Change"],
    all_reco_tbl
)}

<h3>Price Reco Sub-breakdown</h3>
{_tbl(
    ["Sub-type", "Shown (Unique)", "Shown (Events)",
     "Sellers Applied", "Total Events", "Adoption %"],
    price_sub_rows
)}

<h3>Pill Click Ranking — {pf} to {pt}</h3>
{_tbl(
    ["Rank", "Pill", "Unique Sellers", "Total Clicks",
     "Clicks/Seller", "Prev 7d Unique", "WoW Change"],
    pill_rank_tbl
)}

<h2>🚨 Anomaly Alerts &amp; Tracking Health</h2>
{anomaly_html}

</body>
</html>"""
    return html


# ── Google Chat text (exec summary + anomalies only) ─────────────────────────

def build_chat_text(m: dict) -> str:
    period = f"{m['period_from']} – {m['period_to']}"
    lines = [f"*📊 GC Weekly Brief | {period}*", ""]

    lines.append("*🔍 Executive Summary*")
    pills_wow = _wow(m["tot_pills_shown_u"], m["prev_pills_shown_u"])
    lines.append(
        f"• {_fmt(m['tot_pills_shown_u'])} sellers saw pills ({pills_wow} WoW); "
        f"click rate {_pct(m['pill_click_rate'])}."
    )

    rest_rows = m["rest_reco_rows"]
    if rest_rows:
        top = max(rest_rows, key=lambda r: r["applied_u"])
        lines.append(
            f"• {top['name']} leads reco adoption — "
            f"{_fmt(top['applied_u'])} sellers applied ({_pct(top['adoption'])} adoption)."
        )

    critical = [a for a in m["anomalies"] if a.get("type") == "zscore"]
    if critical:
        lines.append(f"• ⚠️ {len(critical)} anomaly(ies) detected: "
                     + ", ".join(a["name"] for a in critical))
    else:
        lines.append("• ✅ No critical anomalies. All signals within normal range.")

    if m["anomalies"]:
        lines += ["", "*🚨 Anomaly Alerts*"]
        for a in m["anomalies"]:
            if a["type"] == "zscore":
                lines.append(
                    f"🔴 *{a['name']}* Z={a['z']} | "
                    f"this week: {_pct(a['value'])} | avg: {_pct(a['mean'])}"
                )
            elif a["type"] == "tracking_risk":
                label = a["event"].replace("gc_", "").replace("_", " ")
                lines.append(f"⚠️ Tracking risk: {label} — shown > 0, applied = 0")
            elif a["type"] == "funnel_inversion":
                label = a["event"].replace("gc_", "").replace("_", " ")
                lines.append(f"⚠️ Funnel inversion: {label} — applied > shown")

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
