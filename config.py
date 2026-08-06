import os
import sys
from datetime import date
from dotenv import load_dotenv

load_dotenv()

_REQUIRED = [
    "MIXPANEL_USER",
    "MIXPANEL_SECRET",
    "GMAIL_SENDER",
    "GMAIL_APP_PASSWORD",
    "GMAIL_RECIPIENTS",
    "GCHAT_WEBHOOK",
]
_missing = [k for k in _REQUIRED if not os.environ.get(k)]
if _missing:
    print(
        "\n[gc_brief] ERROR: The following required environment variables / "
        "GitHub Secrets are not set:\n"
        + "\n".join(f"  - {k}" for k in _missing)
        + "\n\nAdd them via: GitHub repo → Settings → Secrets and variables "
          "→ Actions → New repository secret\n",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Dates ─────────────────────────────────────────────────────────────────────
LAUNCH_DATE   = date(2026, 4, 14)   # GC feature launch — used for MAU start
BASELINE_DATE = date(2026, 6, 17)   # Z-score baseline start date

# ── Mixpanel ──────────────────────────────────────────────────────────────────
MX_PROJECT_ID  = int(os.getenv("MX_PROJECT_ID", "2823261"))
MX_SA_USERNAME = os.environ["MIXPANEL_USER"]    # service account username
MX_SA_SECRET   = os.environ["MIXPANEL_SECRET"]  # service account secret
MX_EU_BASE     = "https://eu.mixpanel.com"

# ── Gmail (SMTP + App Password) ───────────────────────────────────────────────
GMAIL_USER         = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_TO           = [e.strip() for e in os.environ.get("GMAIL_RECIPIENTS", "").split(",") if e.strip()]
GMAIL_CC           = [e.strip() for e in os.environ.get("GMAIL_CC", "").split(",") if e.strip()]

# ── Google Chat ───────────────────────────────────────────────────────────────
GCHAT_WEBHOOK = os.environ["GCHAT_WEBHOOK"]

# ── Scheduler ─────────────────────────────────────────────────────────────────
REPORT_TIMEZONE = "Asia/Kolkata"
SCHEDULE_HOUR   = 10
SCHEDULE_MINUTE = 0

# ── Event lists (exact Mixpanel names) ────────────────────────────────────────
PILLS_SHOWN = [
    "gc_losing_imp_listings_filter_shown",
    "gc_losing_conv_listings_filter_shown",
]
OTHER_PILLS_SHOWN = [
    "gc_losing_imp_other_listings_shown",
    "gc_losing_conv_other_listings_shown",
]
PILLS_CLICKED = [
    "gc_losing_imp_listings_filter_click",
    "gc_losing_conv_listings_filter_click",
]
OTHER_PILLS_VIEWED = [
    "gc_losing_imp_other_listings_viewed",
    "gc_losing_conv_other_listings_viewed",
]
ALERTS_SHOWN = [
    "gc_impressions_alert_shown",
    "gc_conversion_alert_shown",
]
ALERTS_CLICKED = [
    "gc_impressions_alert_cta_click",
    "gc_conversion_alert_cta_click",
]
PRICE_RECOS_SHOWN = [
    "gc_buy_now_recco_shown",
    "gc_inc_vis_recco_shown",
    "gc_conv_price_recco_shown",
    "gc_value_tag_recco_shown",
]
PRICE_RECOS_APPLIED = [
    "gc_buy_now_recco_applied",
    "gc_inc_vis_recco_applied",
    "gc_conv_price_recco_applied",
    "gc_value_tag_recco_applied",
]
REST_RECOS_SHOWN = [
    "gc_fa_recco_shown",
    "gc_suppression_recco_shown",
    "gc_nfbf_oos_recco_triggered",
]
REST_RECOS_APPLIED = [
    "gc_fa_recco_applied",
    "gc_suppression_recco_clicked",
    "gc_nfbf_oos_recco_applied",
]

TRAFFIC_EVENT = "Traffic_Report_Visit"

ALL_EVENTS = list(dict.fromkeys(
    [TRAFFIC_EVENT] +
    PILLS_SHOWN + OTHER_PILLS_SHOWN +
    PILLS_CLICKED + OTHER_PILLS_VIEWED +
    ALERTS_SHOWN + ALERTS_CLICKED +
    PRICE_RECOS_SHOWN + PRICE_RECOS_APPLIED +
    REST_RECOS_SHOWN + REST_RECOS_APPLIED
))

PRICE_RECO_PAIRS = list(zip(PRICE_RECOS_SHOWN, PRICE_RECOS_APPLIED))
REST_RECO_PAIRS  = list(zip(REST_RECOS_SHOWN, REST_RECOS_APPLIED))
ALERT_PAIRS      = list(zip(ALERTS_SHOWN, ALERTS_CLICKED))

# ── OR-dedup query groups ─────────────────────────────────────────────────────
# Each key maps to the list of events to OR-deduplicate across via JQL.
# A seller who triggered multiple events in the group is counted once (true union).
# Used for all L0 KPI rates (Pill, Alert, A&P, Reco Adoption).
OR_QUERY_GROUPS: dict[str, list[str]] = {
    # Pill engagement denominator: sellers shown any filter pill
    "pill_shown_or":  PILLS_SHOWN,
    # Pill engagement numerator: sellers who clicked any filter pill
    "pill_click_or":  PILLS_CLICKED,
    # Alert engagement denominator: sellers shown any alert
    "alert_shown_or": ALERTS_SHOWN,
    # Alert engagement numerator: sellers who clicked any alert CTA
    "alert_click_or": ALERTS_CLICKED,
    # A&P combined shown: sellers shown any pill OR any alert
    "ap_shown_or":    PILLS_SHOWN + ALERTS_SHOWN,
    # A&P combined clicked: sellers who clicked any pill OR any alert
    "ap_click_or":    PILLS_CLICKED + ALERTS_CLICKED,
    # Reco shown OR across 6 types (excl NFBF — different event suffix)
    "recco_shown_or": PRICE_RECOS_SHOWN + [
        "gc_fa_recco_shown",
        "gc_suppression_recco_shown",
    ],
    # Reco applied OR across 6 types (excl Suppression — different event suffix)
    "recco_applied_or": PRICE_RECOS_APPLIED + [
        "gc_fa_recco_applied",
        "gc_nfbf_oos_recco_applied",
    ],
}

PRICE_RECO_LABELS = {
    "gc_buy_now_recco_shown":   "Buy Now",
    "gc_inc_vis_recco_shown":   "Increase Visibility",
    "gc_conv_price_recco_shown": "Conv Price",
    "gc_value_tag_recco_shown": "Value Tag",
}
REST_RECO_LABELS = {
    "gc_fa_recco_shown":           "F-Assured",
    "gc_suppression_recco_shown":  "Suppression",
    "gc_nfbf_oos_recco_triggered": "NFBF OOS",
}
PILL_LABELS = {
    "gc_losing_imp_listings_filter_click":  "Losing Imp",
    "gc_losing_conv_listings_filter_click": "Losing Conv",
}
OTHER_PILL_LABELS = {
    "gc_losing_imp_other_listings_shown":   "Other Imp Shown",
    "gc_losing_conv_other_listings_shown":  "Other Conv Shown",
    "gc_losing_imp_other_listings_viewed":  "Other Imp Viewed",
    "gc_losing_conv_other_listings_viewed": "Other Conv Viewed",
}
