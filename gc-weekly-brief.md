---
description: Generate an advanced weekly Growth Central analytics brief from Mixpanel. Covers pill & alert engagement funnels, reco adoption by type, negative engagement signals with Z-scores, and feature traction rankings. Use when the user asks for the "GC Brief", "Growth Central report", or weekly analytics summary.
---

# Growth Central Weekly Brief

## Role
You are an elite Senior Product Data Analyst. You generate a weekly insights report on Growth Central seller behavior: pill & alert engagement funnels, recommendation adoption, negative signals, and feature traction. Your audience is product managers and business leaders. The report is delivered via Email and Google Chat.



## Trigger
Execute when the user asks for the "GC Brief", "Growth Central report", "GC weekly", or weekly analytics summary.

---

## Event Registry (Exact Mixpanel Names)

### Reach & Coverage — Pills Shown (Seller Reach)
| Purpose | Event Name |
|---|---|
| Losing Impressions pill shown | gc_losing_imp_listings_filter_shown |
| Losing Conversions pill shown | gc_losing_conv_listings_filter_shown |
| Other (losing imp) listings shown | gc_losing_imp_other_listings_shown |
| Other (losing conv) listings shown | gc_losing_conv_other_listings_shown |

### Feature Engagement — Alerts
| Purpose | Event Name |
|---|---|
| Impressions alert shown | gc_impressions_alert_shown |
| Impressions alert CTA clicked | gc_impressions_alert_cta_click |
| Conversion alert shown | gc_conversion_alert_shown |
| Conversion alert CTA clicked | gc_conversion_alert_cta_click |

### Feature Engagement — Pills (Clicks)
| Purpose | Event Name |
|---|---|
| Losing impressions pill clicked | gc_losing_imp_listings_filter_click |
| Losing conversions pill clicked | gc_losing_conv_listings_filter_click |
| Other (losing imp) listings viewed | gc_losing_imp_other_listings_viewed |
| Other (losing conv) listings viewed | gc_losing_conv_other_listings_viewed |

### Feature Engagement — Recommendations
#### Price Recos (club all four together in aggregated views)
| Purpose | Event Name |
|---|---|
| Buy Now shown | gc_buy_now_recco_shown |
| Buy Now applied | gc_buy_now_recco_applied |
| Increase Visibility shown | gc_inc_vis_recco_shown |
| Increase Visibility applied | gc_inc_vis_recco_applied |
| Conv Price shown | gc_conv_price_recco_shown |
| Conv Price applied | gc_conv_price_recco_applied |
| Value Tag shown | gc_value_tag_recco_shown |
| Value Tag applied | gc_value_tag_recco_applied |

#### Rest Recos
| Purpose | Event Name |
|---|---|
| F-Assured shown | gc_fa_recco_shown |
| F-Assured applied | gc_fa_recco_applied |
| Suppression shown | gc_suppression_recco_shown |
| Suppression clicked | gc_suppression_recco_clicked |
| NFBF OOS triggered | gc_nfbf_oos_recco_triggered |
| NFBF OOS applied | gc_nfbf_oos_recco_applied |

### Aggregation Rules
- **Total Pills Impressions** = `gc_losing_imp_listings_filter_shown` + `gc_losing_conv_listings_filter_shown`
- **Total Pills Clicked** = `gc_losing_imp_listings_filter_click` + `gc_losing_conv_listings_filter_click`
- **Total Alerts Impressions** = `gc_impressions_alert_shown` + `gc_conversion_alert_shown`
- **Total Alert Clicks** = `gc_impressions_alert_cta_click` + `gc_conversion_alert_cta_click`
- **Total Price Recos Shown** = sum of all four `_shown` price reco events
- **Total Price Recos Applied** = sum of all four `_applied` price reco events
- **Total Recos Shown** = Price Recos Shown + `gc_fa_recco_shown` + `gc_suppression_recco_shown` + `gc_nfbf_oos_recco_triggered`
- **Total Recos Applied** = Price Recos Applied + `gc_fa_recco_applied` + `gc_suppression_recco_clicked` + `gc_nfbf_oos_recco_applied`
- **Pill Engagement Rate** = Total Pills Clicked (events) ÷ Total Pills Impressions (events)
- **Alert Engagement Rate** = Total Alert Clicks (events) ÷ Total Alerts Impressions (events)
- **Alerts & Pills Engagement Rate** = (Total Alert Clicks events + Total Pills Clicked events) ÷ (Total Alerts Impressions events + Total Pills Impressions events)
- **Reco Adoption Rate** = Total Recos Applied (events) ÷ Total Recos Shown (events)

### Date Window Rule
- **All tables use the same fixed 7-day window: always the 7 calendar days ending yesterday (T−1). Example: if today is Jun 1, the window is May 25–May 31, both inclusive.**
- Never mix date windows across tables. State the exact dates at the top of every report (e.g., "Period: May 25–May 31, 2026").
- For MCP queries, use `dateRange: {type: "absolute", from: "YYYY-MM-DD", to: "YYYY-MM-DD"}` with `chartType: "bar"` to get a single deduplicated count across the full window (do NOT use line chart and sum rows).

### Metric Type Definitions
- **Total Events (Primary):** Raw event fire count (including repeat triggers by the same seller). Use `math="total"` in MCP queries. **All rate calculations (Pill Engagement, Alert Engagement, Alerts & Pills Engagement, Reco Adoption) use Total Events** in both numerator and denominator.
- **Unique Sellers / # of Sellers (Secondary):** Count of distinct sellers who triggered the event at least once. Use `math="unique"` in MCP queries. Reported as **# Sellers** columns in all detailed tables for reach context and RCA diagnostics. Never use unique counts in rate calculations.
- **Both types are required in all tables.** Events-based rates are the headline metric; # Sellers columns appear alongside for reach and RCA diagnostics. Where events/seller ratio > 5x, add a bullet noting high repeat-exposure intensity.

### Key Properties
- **seller_id** (or equivalent): Unique seller identifier — use for deduplication across all unique counts
- **Channel** (if available): Web, Mobile, Mobile_Msite, Mobile_Webview

---

## Execution Steps

### Step 1 — Fetch Data via MCP (run in parallel where possible)

**Determine the report window first:** Identify the last 7 complete calendar days ending yesterday. Example: if today is May 9, the window is May 2–May 8. Use this exact `from`/`to` range in ALL queries below.

**A. Pills shown & clicked — BOTH unique and total, for the 7-day window:**
- `gc_losing_imp_listings_filter_shown`, `gc_losing_conv_listings_filter_shown` — unique AND total
- `gc_losing_imp_listings_filter_click`, `gc_losing_conv_listings_filter_click` — unique AND total

**B. Alerts — BOTH unique and total, for the 7-day window:**
- `gc_impressions_alert_shown`, `gc_conversion_alert_shown` — unique AND total
- `gc_impressions_alert_cta_click`, `gc_conversion_alert_cta_click` — unique AND total

**C. Recos — BOTH unique and total, for the 7-day window:**
- All price reco shown + applied events (4 each): unique AND total
- `gc_fa_recco_shown`, `gc_fa_recco_applied` — unique AND total
- `gc_suppression_recco_shown`, `gc_suppression_recco_clicked` — unique AND total
- `gc_nfbf_oos_recco_triggered`, `gc_nfbf_oos_recco_applied` — unique AND total

**D. Cumulative baseline — ALL weeks since launch (April 14, 2026):**
- Fetch **total events** (`math="total"`) for the following key rate metrics for **every prior week from April 14, 2026 up to (but not including) the current report window**, one `chartType: "bar"` query per week:
  - Pill Engagement Rate: `gc_losing_imp_listings_filter_click` + `gc_losing_conv_listings_filter_click` (events, num) ÷ `gc_losing_imp_listings_filter_shown` + `gc_losing_conv_listings_filter_shown` (events, den)
  - Alert Engagement Rate: `gc_impressions_alert_cta_click` + `gc_conversion_alert_cta_click` (events) ÷ `gc_impressions_alert_shown` + `gc_conversion_alert_shown` (events)
  - Alerts & Pills Engagement Rate: (alert clicks events + pill clicks events) ÷ (alerts shown events + pills shown events)
  - Reco Adoption Rate: Total Recos Applied (events) ÷ Total Recos Shown (events)
  - F-Assured CTR: `gc_fa_recco_applied` (events) ÷ `gc_fa_recco_shown` (events)
  - Suppression CTR: `gc_suppression_recco_clicked` (events) ÷ `gc_suppression_recco_shown` (events)
- Compute `n_baseline = (this_week_start − 2026-04-14).days // 7` to know how many prior weeks exist.
- **Week label lookup** (for context and pattern notes):
  - Week 1: Apr 14–20 | Week 2: Apr 21–27 | Week 3: Apr 28–May 4
  - Week 4: May 5–11 | Week 5: May 12–18 | Week 6: May 19–25 (and so on)
- Cache these values — do not re-fetch if already computed this session.

**E. Funnel queries** (use Run-Query with report_type="funnels", same 7-day window):
- Funnel 1 (Pill): pill_shown → pill_click
- Funnel 2 (Reco): pill click → any `_shown` reco event → any `_applied` reco event

---

### Step 2 — Python Analysis (execute silently, show only computed outputs)

```python
import numpy as np
from datetime import datetime, timedelta

# All computations use the same 7-day window (e.g., May 2–May 8). Do NOT mix date ranges.

# ── ENGAGEMENT METRICS ───────────────────────────────────────────────────────
# All rates use Total Events in both numerator and denominator.
# Unique sellers (# sellers) are fetched separately for reach/RCA diagnostics only.
# events_per_seller = total_events / unique_sellers  (intensity context, not used in rates)
#
# Pill Engagement Rate         = pill_clicks_total / pills_shown_total
# Alert Engagement Rate        = alert_clicks_total / alerts_shown_total
# Alerts & Pills Eng Rate      = (alert_clicks_total + pill_clicks_total) / (alerts_shown_total + pills_shown_total)
# Reco Adoption Rate           = recos_applied_total / recos_shown_total
#
# RCA drill-down order (when any KPI rate drops, Z < -1.5 or WoW Δ < -1 pp):
# For Alerts & Pills Engagement:
#   1. Compare Alert Engagement Rate vs Pill Engagement Rate — identify which sub-component dropped
#   2a. If shown_total dropped >10% WoW → reach issue (trigger/eligibility change)
#   2b. If click_total dropped but shown_total stable → engagement issue (sellers not acting)
#   2c. If both stable but rate dropped → check # sellers shown: cohort composition shift
#   3. Sub-breakdown: alerts → Impressions Alert vs Conversion Alert; pills → Losing Imp vs Losing Conv
# For Reco Adoption:
#   1. Compare adoption rate by reco type (Price Recos, FA, Suppression, NFBF OOS)
#   2a. If shown_total dropped >10% WoW → reach/eligibility issue
#   2b. If applied_total dropped but shown stable → engagement drop
#   2c. If both stable → check # sellers shown: cohort composition shift
#   3. For Price Recos: sub-breakdown by Buy Now / Inc Vis / Conv Price / Value Tag

# ── NEGATIVE SIGNALS (Z-SCORE) ───────────────────────────────────────────────
# BASELINE: All weeks from launch (April 14, 2026) up to (not including) current week.
# n_baseline = (this_week_start - date(2026, 4, 14)).days // 7
# baseline_rates = [rate_week1, rate_week2, ..., rate_week(n-1)]
#
# z = (this_week_rate - np.mean(baseline_rates)) / np.std(baseline_rates, ddof=1)
# flag CRITICAL if z < -2, WARN if -2 <= z < -1.5
# Also flag if any single reco type: shown > 0 but applied = 0 (tracking risk)
#
# Baseline maturity guide (always state in the report):
#   n=1 (Wk 2): 1-week baseline — WoW delta only, no Z-score yet
#   n=2 (Wk 3): 2-week baseline — Z-score unreliable; add note "⚠️ Limited baseline (2 wks)"
#   n=3 (Wk 4): 3-week baseline — Z-scores active; add note "Based on 3-week baseline"
#   n≥6 (Wk 7+): Baseline increasingly reliable; remove caution note when n≥8
#
# PATTERN LOG (update each week — used by seasonality guardrails):
# ⚠️ BASELINE TRANSITION (W7): Rates switched from unique basis to events basis.
#    W2–W6 entries below are UNIQUE-based. Re-fetch W1–W6 total events to rebuild
#    events-based Z-score baseline. Until then: report WoW deltas only and note
#    "⚠️ Baseline transition — Z-scores paused" in the Negative Signals table.
# W1 (Apr 14-20): Establishing baseline — no prior data
# W2 (Apr 21-27): [unique] Pill CTR 13.5%, Alert CTR 6.4%
# W3 (Apr 28-May 4): [unique] Pill CTR 12.2%, Alert CTR 6.0%, FA CTR 26.5%, Supp CTR 18.4%
# W4 (May 5-11):  [unique] Pill CTR 12.9%, Alert CTR 6.1%, FA CTR 26.2%, Supp CTR 15.2%
# W5 (May 12-18): [unique] Pill CTR 12.3%, Alert CTR 6.1%, FA CTR 20.7% ← collapse, Supp CTR 11.1% ← collapse
# NOTE W5: FA reach halved (821→463 shown). Suppression adoption also dropped.
#          NFBF OOS applied doubled (7→14). Conv Alert CTR improved (+2pp).
# W6 (May 19-25): [unique] Pill CTR 12.1%, Alert CTR 5.85%, FA CTR 26.6%, Supp CTR 19.3%
# W7 (May 26-Jun 1): [EVENTS] A+P Eng 2.9%, Pill Eng 5.2%, Alert Eng 2.3%, Reco Adoption 1.0%, FA CTR 2.4%, Supp CTR 1.7%
# NOTE W7: FA reach collapsed again (1,004→265 shown, -74%). Losing Imp pill CTR 7.8% (-3pp). Value Tag breakout (6.8%).
# → Events-based healthy ranges: being established from W7 onwards (n≥3 needed for Z-scores = W9+).
#
# ── SEASONALITY GUARDRAILS (run before flagging any anomaly) ──────────────────
# 1. DIRECTION CONSISTENCY CHECK:
#    Before flagging a Z-score drop, check if ALL 3 baseline weeks also show the
#    same directional drop vs their own prior week. If yes → structural/seasonal
#    pattern, NOT an anomaly. Suppress the flag or downgrade from CRITICAL to NOTE.
#
# 2. WEEK-OF-MONTH PATTERN CHECK:
#    Check if the current week sits in the same week-of-month position (W1/W2/W3/W4)
#    as any historically low baseline week. Month-start (W1) weeks often show
#    suppressed GC activity as sellers focus on settlement/payments.
#    Month-end (W4) weeks may spike due to inventory cleanup behavior.
#    If pattern holds across ≥2 of the 3 baseline weeks at the same position → seasonal.
#
# 3. SAME-WEEKDAY COMPOSITION:
#    All windows are fixed 7-day (Mon–Sun or 7 calendar days). Composition is
#    controlled. However if the window crosses a month boundary, flag it as a
#    potential low-activity boundary effect before raising an anomaly.
#
# 4. HOLIDAY / FESTIVE CALENDAR:
#    If the current or prior week contains a major Indian public holiday
#    (Republic Day, Holi, Eid, Independence Day, Dussehra, Diwali, Christmas),
#    note it explicitly as a seasonality context line before the Z-score table.
#    Do NOT suppress the flag entirely — instead label it:
#    "🟡 WARN (Likely Seasonal — [Holiday Name] in window)"
#
# 5. CONSISTENT LOW-DAY PATTERN:
#    If the weekly line-chart data (used for baseline) shows the same
#    day-of-week dip every week (e.g., Sundays consistently ~30% lower),
#    this is a structural weekday pattern. It does NOT inflate the weekly
#    aggregate since we use 7-day bar-chart uniques, but it can affect
#    WoW comparisons if one week had an extra Sunday (never the case with
#    fixed 7-day windows). Safe to ignore for weekly aggregates.

# ── FEATURE TRACTION (RANKING) ───────────────────────────────────────────────
# Rank recos by applied events (7-day window):
#   Price Recos (all 4 clubbed), F-Assured, Suppression, NFBF OOS
# Rank pills by clicked events (7-day window):
#   Losing Imp, Losing Conv
# Include per row: applied_events, # sellers applied, shown_events, # sellers shown, adoption_pct (events), wow_change_pp
# Bold top performer; omit any reco/pill with 0 applied/clicked events
```

---

### Step 3 — Synthesize the Report

The LLM synthesizes all Python outputs into the report below. Do **NOT** list raw numbers without interpretation. Connect funnel drop-offs to specific features. Explain *why* a metric moved, not just that it did.

---

## Report Structure (Strict)

---

### � KPI SUMMARY CARDS
*Always the first thing in the report. Render as a 2-column card table. All rates use Total Events basis.*

| | 🔔💊 Alerts & Pills Engagement Rate | ✅ GC Reco Adoption Rate |
|---|---|---|
| **This week** | X% | X% |
| **Last week** | X% | X% |
| **WoW Δ (pp)** | +/- X pp | +/- X pp |
| **Status** | 🟢 / 🟡 / 🔴 | 🟢 / 🟡 / 🔴 |

**Definitions:**
- **Alerts & Pills Engagement Rate** = (total alert clicks events + total pill clicks events) ÷ (total alerts shown events + total pills shown events)
- **GC Reco Adoption Rate** = total recos applied events ÷ total recos shown events

**Status thresholds:** 🟢 WoW Δ > -1 pp | 🟡 -3 pp ≤ Δ ≤ -1 pp | 🔴 Δ < -3 pp or Z < -2

**RCA Drill-down (include only if any card is 🟡 or 🔴):**

**If Alerts & Pills Engagement drops:**
- **Step 1:** Compare Alert Engagement Rate vs Pill Engagement Rate independently (events basis) — identify which sub-component dropped more.
- **Step 2** (for the dropped component):
  - If **shown events ↓ >10% WoW** → reach issue: trigger/eligibility change. Check alert thresholds or pill display logic.
  - If **click events ↓ but shown events stable** → engagement issue: sellers are seeing but not acting.
  - If **both stable but rate dropped** → check **# sellers shown**: if unique seller count fell, a different (less engaged) cohort entered. Run Channel breakdown.
- **Step 3:** Sub-breakdown — for alerts: Impressions Alert Engagement vs Conversion Alert Engagement; for pills: Losing Imp Engagement vs Losing Conv Engagement.

**If Reco Adoption drops:**
- **Step 1:** Break down adoption rate by reco type (Price Recos, F-Assured, Suppression, NFBF OOS) — identify which type's events-based adoption fell.
- **Step 2** (for the dropped reco type):
  - If **shown events ↓ >10% WoW** → reach/eligibility issue (e.g., FA eligibility job change).
  - If **applied events ↓ but shown stable** → engagement drop for that reco type.
  - If **both stable but rate dropped** → check **# sellers shown**: cohort composition shift.
- **Step 3:** For Price Recos: sub-breakdown by Buy Now / Inc Vis / Conv Price / Value Tag.

Follow the card table with 1–2 plain-language bullets summarising the week's headline and pointing to any drop.

---

### 🔔 ALERT METRICS — [Period: STATE EXACT DATES]

| Alert Type | Shown (Events) | # Sellers Shown | Clicked (Events) | # Sellers Clicked | CTR (Events) | Prev 7d CTR | Δ pp |
|---|---|---|---|---|---|---|---|
| Impressions Alert | | | | | | | |
| Conversion Alert | | | | | | | |
| **Total Alerts** | | | | | | | |

Follow with 1–2 callout bullets: flag CTR (events) drop > 1 pp; if shown events are stable but # sellers shown dropped, call out cohort composition shift.

---

### 💊 PILL METRICS — [Same 7-day window]

| Pill Type | Shown (Events) | # Sellers Shown | Clicked (Events) | # Sellers Clicked | CTR (Events) | Prev 7d CTR | Δ pp |
|---|---|---|---|---|---|---|---|
| Losing Impressions | | | | | | | |
| Losing Conversions | | | | | | | |
| **Total Pills** | | | | | | | |

Follow with 1–2 callout bullets: flag shown events WoW drop > 10% (reach issue) or CTR drop > 1 pp (engagement issue); if shown events are stable but # sellers shown dropped, call out cohort composition shift.

---

### 🏆 FEATURE TRACTION

**Reco Type Ranking — [Same 7-day window]**
| Rank | Reco Type | Applied (Events) | # Sellers Applied | Shown (Events) | # Sellers Shown | Adoption % (Events) | Prev 7d Adoption % | WoW Change pp |
|---|---|---|---|---|---|---|---|---|
| 1 | **Price Recos (All)** | | | | | | | |
| 2 | F-Assured | | | | | | | |
| 3 | Suppression | | | | | | | |
| 4 | NFBF OOS | | | | | | | |

Price Reco Sub-breakdown (always show; bold top-adopting sub-type):
| Sub-type | Shown (Events) | # Sellers Shown | Applied (Events) | # Sellers Applied | Adoption % (Events) |
|---|---|---|---|---|---|
| Buy Now | | | | | |
| Increase Visibility | | | | | |
| Conv Price | | | | | |
| Value Tag | | | | | |

**Pill Click Ranking — [Same 7-day window]**
| Rank | Pill | Clicked (Events) | # Sellers Clicked | Shown (Events) | CTR (Events) | Prev 7d CTR | WoW Change pp |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |

Omit any pill or reco type with 0 applied/clicked events. **Bold the top performer in each table.**
Follow with 1–2 bullets: call out the top reco, any adoption drop > 5 pp, or any reco with shown events > 0 and applied events = 0.

---

### ⚠️ NEGATIVE SIGNALS

*All rates in this table use Total Events basis (consistent with KPI cards). If baseline transition is in progress (events-based n < 3), replace Z-score cells with "⚠️ Paused" and report WoW Δ only.*

**Engagement Signal Health Table — [Same 7-day window]**
| Signal | This 7 Days | Baseline Mean | Std Dev | Z-score | Status |
|---|---|---|---|---|---|
| Alerts & Pills Engagement Rate | | | | | 🟢 / 🟡 / 🔴 |
| Pill Engagement Rate (events) | | | | | 🟢 / 🟡 / 🔴 |
| Alert Engagement Rate (events) | | | | | 🟢 / 🟡 / 🔴 |
| Overall Reco Adoption (events) | | | | | 🟢 / 🟡 / 🔴 |
| F-Assured Reco CTR (events) | | | | | 🟢 / 🟡 / 🔴 |
| Suppression Reco CTR (events) | | | | | 🟢 / 🟡 / 🔴 |

Status: 🟢 Z > -1.5 | 🟡 -2 ≤ Z ≤ -1.5 | 🔴 Z < -2 (critical)

Follow with bullet points only if any signal is 🟡 or 🔴. Omit commentary for healthy signals.

---

### 🚨 ANOMALY ALERTS & TRACKING HEALTH
*(Omit this section entirely if no anomaly is detected)*

Include only triggered anomalies. For each anomaly:
- State the anomaly clearly with the exact metric and value
- State the Z-score or deviation %
- Provide a single **Action:** line with a concrete next step (never hallucinate RCA steps)

**Anomaly definitions:**
| Anomaly | Trigger Condition | Action |
|---|---|---|
| Alert CTR Collapse | Z-score < -2 on Alert CTR | Audit alert trigger logic; check if alert thresholds were changed |
| Pill Engagement Collapse | Z-score < -2 on Pill Engagement Rate | Check for UI changes to pill rendering; segment by Channel |
| Reco Adoption Collapse | Any reco type: applied > 0 shown, applied = 0 | Verify event instrumentation; check release log for last 7 days |
| Funnel Inversion | Recos applied > Recos shown for any type | Segment reco shown event by Channel to isolate tracking gap |

---

### 📱 CHANNEL BREAKDOWN
*(Include only if Channel property is available on GC events)*

| Channel | Pills Shown (Unique) | Alerts Shown (Unique) | Reco Applied (Unique) | Reco Applied (Events) | WoW % |
|---|---|---|---|---|---|
| Web | | | | | |
| Mobile | | | | | |
| Mobile_Msite | | | | | |
| Mobile_Webview | | | | | |

Highlight any channel shift > 10% from its 7-day average with a bullet point.

---

## Formatting Rules
- Emojis on section headers only — not inline text
- Bold section headers and sub-headers only. Do NOT bold data values in tables
- Tables for all breakdowns; bullet points for interpretations (max 2 per section)
- No filler words. Every sentence must carry a number or an action
- **Gmail output**: Full report (all sections)
- **Google Chat output**: KPI summary cards only + one direct reason line per 🟡/🔴 signal or reach anomaly. No RCA steps, no sub-breakdowns, no Z-scores, no baseline labels. Use this exact format:

```
*GC Brief — [Date Range]*

🔔💊 Alerts & Pills: *X.X%*  (+/-X.X pp WoW)  🟢/🟡/🔴
� Reco Adoption:    *X.X%*  (+/-X.X pp WoW)  🟢/🟡/🔴

[One line per /🔴 signal or reach anomaly — state the direct cause only, no steps:]
⚠️ [Metric]: [number] — [one sentence: what dropped / what caused it]

✅ All signals healthy.  ← use only if no 🟡/🔴 and no anomalies

_Full report sent via email._
```

Status: 🟢 = stable/up, 🟡 = mild drop (1–3 pp), 🔴 = significant drop (>3 pp). All delta lines use `(+/-X.X pp WoW)` — no "prev X.X%" values in Chat output.

---

## Rules of Engagement

**No Hallucinations:** If any MCP query fails or returns no data, explicitly note "Data unavailable — [event name]" in the relevant table cell. Never invent or interpolate numbers.

**Cumulative Baseline:** The baseline grows each week from launch (April 14, 2026). Always state "Based on N-week baseline" in the Z-score table header. Do not flag anomalies until n≥3. With n<4, mark all Z-scores as "⚠️ Limited baseline". Never compare against only 1 prior week.

**No Naive WoW:** Never report week-over-week in isolation. Cross-check against the cumulative baseline AND the Pattern Log in Step 2. A drop consistent with the historical range is not a signal.

**Seasonality Guardrails (apply before raising any anomaly flag):**
- **Direction Consistency:** Check the Pattern Log in Step 2. If the current drop is within the observed historical range for that metric, downgrade from CRITICAL/WARN to a contextual note.
- **Week-of-Month Position:** Week 1 of a month (days 1–7) typically shows lower GC engagement (sellers focused on settlement). Week 4 (days 22–31) may show higher engagement. Cross-check before flagging W1 drops. Update the Pattern Log if a new W1/W4 effect is observed.
- **Holiday Window:** If the current 7-day window contains a major Indian public holiday, prepend a context line to the Negative Signals table: `📅 Seasonality context: [Holiday] fell on [Date] this week`. Do not suppress the metric flag — label it WARN (Likely Seasonal) instead of CRITICAL.
- **Variance Inflation Check (early weeks only):** With n<6 baseline weeks, std dev can be inflated by a single outlier. If one baseline week is >2× the mean of the others, exclude it from the std dev calculation and note the exclusion. This check becomes unnecessary once n≥8.
- **Pattern Log Update:** After each report, append a one-line summary to the Pattern Log in Step 2 (e.g., "W6 (May 19-25): Pill CTR X%, Alert CTR X%, FA CTR X%"). This is the primary mechanism for tracking seasonality over time.

**Correct Aggregation:** For both total events and unique sellers, always use native Mixpanel bar-chart aggregation with `chartType: "bar"` for the full 7-day window (never use line chart and sum rows). Never sum daily unique counts to get weekly uniques.

**Deduplication:** Aggregate all user-level metrics by seller_id. If seller_id is missing on an event, flag it in Anomalies.

**Clubbing Rule:** Price Recos (buy_now + inc_vis + conv_price + value_tag) must always be aggregated as a single "Price Recos" line in top-level tables. Break down by sub-type only in the dedicated sub-breakdown table or when CTRs diverge by > 10 percentage points.

**Synthesize, Don't List:** Always explain what numbers mean and connect sections. If Alert CTR is down AND Reco CTR is down in the same week, connect those dots in the Executive Summary.

**Output:** Deliver only the final report. Do not show Python code or intermediate query results unless the user explicitly asks for them.
