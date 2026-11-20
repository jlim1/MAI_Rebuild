# Client and browser checks

For a client-to-API integration check without browser dependencies, install `requirements-dev.txt`, make sure Node.js is on PATH, and run `python -m unittest discover -s checks -v` from the project root. The real JavaScript client calls a temporary local FastAPI server to reserve stock, reject an oversized order, ask both simulated providers and finish fulfillment. No API keys or vendor network calls are used. This does not render the React UI.

## Browser walkthrough

Build the frontend first (`npm ci` and `npm run build` in `frontend`). Using the project's Python environment, install the app dependencies, then:

```text
python -m pip install -r checks/requirements.txt
python -m playwright install chromium
python checks/walkthrough.py
```

If Microsoft Edge is already installed on Windows, you can skip the Chromium download and set `$env:PARCEL_TEST_BROWSER = 'msedge'` before running the check. The browser sandbox stays enabled.

The check uses a disposable copy of the backend and browser build, a disposable database, a fresh browser context, and an ephemeral loopback port. It never resets your working demo. Browser requests to any other origin are blocked and cause the check to fail. The script shuts down its own server and removes its scratch copy on exit.
