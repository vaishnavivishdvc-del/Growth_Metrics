"""
Diagnostic script — run this in GitHub Actions to test Mixpanel API connectivity.
Prints raw responses from multiple endpoint candidates so we can identify the
correct one for EU-hosted projects.
"""
import os
import requests

USER    = os.environ["MIXPANEL_USER"]
SECRET  = os.environ["MIXPANEL_SECRET"]
PROJECT = os.getenv("MX_PROJECT_ID", "2823261")
AUTH    = (USER, SECRET)

print(f"Service account user : {USER[:20]}...")
print(f"Project ID           : {PROJECT}")
print()

SIMPLE_JQL = """
function main() {
  return Events({
    from_date: '2026-05-01',
    to_date:   '2026-05-07',
    event_selectors: [{"event": "gc_losing_imp_listings_filter_shown"}]
  }).groupBy(['name'], mixpanel.reducer.count());
}
"""

ENDPOINTS = [
    "https://data-eu.mixpanel.com/api/2.0/jql",
    "https://eu.mixpanel.com/api/2.0/jql",
    "https://mixpanel.com/api/2.0/jql",
]

for url in ENDPOINTS:
    print(f"=== Testing: {url}")
    try:
        r = requests.post(
            url,
            auth=AUTH,
            data={"script": SIMPLE_JQL, "project_id": PROJECT},
            timeout=20,
        )
        print(f"    Status : {r.status_code}")
        print(f"    Body   : {r.text[:400]}")
    except Exception as e:
        print(f"    ERROR  : {e}")
    print()

# Also test the segmentation API (simpler, REST-based)
print("=== Testing segmentation API (EU)")
try:
    r = requests.get(
        "https://eu.mixpanel.com/api/2.0/segmentation",
        auth=AUTH,
        params={
            "project_id": PROJECT,
            "event": "gc_losing_imp_listings_filter_shown",
            "from_date": "2026-05-01",
            "to_date": "2026-05-07",
            "type": "unique",
            "unit": "day",
        },
        timeout=20,
    )
    print(f"    Status : {r.status_code}")
    print(f"    Body   : {r.text[:400]}")
except Exception as e:
    print(f"    ERROR  : {e}")
