import os
import sys
from dotenv import load_dotenv

load_dotenv()

_REQUIRED = [
    "MX_SA_USERNAME",
    "MX_SA_SECRET",
    "GMAIL_USER",
    "GMAIL_APP_PASSWORD",
    "GMAIL_TO",
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

# ── Mixpanel ──────────────────────────────────────────────────────────────────
MX_PROJECT_ID  = int(os.getenv("MX_PROJECT_ID", "2823261"))
MX_SA_USERNAME = os.environ["MX_SA_USERNAME"]   # service account username
MX_SA_SECRET   = os.environ["MX_SA_SECRET"]     # service account secret
MX_EU_BASE     = "https://eu.mixpanel.com"

# ── Gmail (SMTP + App Password) ───────────────────────────────────────────────
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_TO           = [e.strip() for e in os.environ.get("GMAIL_TO", "").split(",") if e.strip()]
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
PILLS_CLICKED = [
    "gc_losing_imp_listings_filter_click",
    "gc_losing_conv_listings_filter_click",
    "gc_low_conv_filter_click",
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

ALL_EVENTS = list(dict.fromkeys(
    PILLS_SHOWN + PILLS_CLICKED +
    ALERTS_SHOWN + ALERTS_CLICKED +
    PRICE_RECOS_SHOWN + PRICE_RECOS_APPLIED +
    REST_RECOS_SHOWN + REST_RECOS_APPLIED
))

PRICE_RECO_PAIRS = list(zip(PRICE_RECOS_SHOWN, PRICE_RECOS_APPLIED))
REST_RECO_PAIRS  = list(zip(REST_RECOS_SHOWN, REST_RECOS_APPLIED))
ALERT_PAIRS      = list(zip(ALERTS_SHOWN, ALERTS_CLICKED))

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
    "gc_low_conv_filter_click":             "Low Conv",
}
