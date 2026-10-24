.PHONY: test eval dashboard demo

python = python3

test:
	$(python) -m pytest -q

eval:
	$(python) runner.py --mode protected --auto-review deny
	$(python) runner.py --mode unprotected

dashboard:
	$(python) -m streamlit run dashboard.py --server.headless true --server.port 8502

demo:
	$(python) runner.py --mode protected --auto-review approve
