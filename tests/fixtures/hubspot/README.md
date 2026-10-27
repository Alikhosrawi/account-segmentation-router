Fixtures for `tests/test_hubspot.py`. `owners.json` and `upsert_response.json` follow the response shapes in HubSpot's
CRM v3 docs (no real portal data). When a real token is available, `python3 router/hubspot.py --live --record tests/fixtures/hubspot/recorded`
captures real request/response pairs (the token is sent in a header and never written).
