# V21.1 executable engineering status

- 53 pytest tests passed (`pytest -q test_lab.py test_lab_debug.py`), including 46 baseline tests and 7 additional debugging checks.
- Static Python compilation passed.
- Mocked 44-stock whole-roster automatic provider pipeline was intentionally interrupted at stock 6, then resumed using the same SQLite cache and finished without refetching the first 5.
- A cached 520-stock, 2,200-session, Top100/200/300/500, 64-profile, 5/20/60 synthetic input resumed and reached `COMPLETE` in 33.96 s, observed process RSS 291.43 MiB. A preceding first-load attempt timed out after 180 s while processing initial features; this is NOT a 34-second end-to-end first-install benchmark.
- Bounded fake Streamlit UI-contract smoke passed using a stub because the actual runtime is not available here.
- External FinMind/TWSE/TPEx/Yahoo real-network + actual Streamlit Cloud deployment **NOT tested**. The container does not have working external pip install/network access to install Streamlit/yfinance.
- No real full-universe provider-history model verification has been obtained here. No financial alpha, profitability, factor-optimum or execution approval is claimed.
- Original V21.0 code has a first-stage hourly source limit (260 requests per hour without token / 520 with token); a new Cloud app can require multiple hours and a durable cache. This release improves visibility, error propagation, and resume; it does not bypass data service limits.

## Python 3.14 Cloud installation compatibility hotfix (2026-10-22)

- Cloud log shows Python 3.14.8, repository install stage, no visible traceback or `app.py` execution. Root cause of that individual deployment is not fully proven from this truncated excerpt.
- Previous pandas 2.2.3 and Streamlit 1.50.0 pins predate CPython 3.14 support. Updated to pandas 2.3.3, Streamlit 1.52.2 and explicit PyArrow 22.0.0, which have CPython 3.14-compatible distribution metadata/wheels.
- No model algorithm, feature engineering, cache identifiers or research configurations modified.
- New wheel pins were cross-checked against published package release information, not installed on Python 3.14 in this environment; actual Cloud deployment requires validation from complete logs.
