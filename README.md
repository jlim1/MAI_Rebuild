# Parcel Workbench

A local-first inventory and fulfillment demo for a fictional equipment shop. Reserve a scarce product, see exactly what stock remains, and move the order through a simulated shipment. No customer records, accounts, carrier credentials or external services are needed.

## Run on Windows

Install Python 3.11 or later and Node.js 22.12 or later (with npm). Extract the project to its own directory. Open a terminal there:

```powershell
.\setup.cmd
.\start.cmd
```

Open **http://127.0.0.1:8000**. Setup needs internet access to install dependencies; subsequent launches need only the local machine. Press **Ctrl+C** in the terminal to stop. The first launch creates a local SQLite database. To start the walkthrough again, stop the server, run `.\.venv\Scripts\python.exe -m backend.reset`, then run `.\start.cmd` and reload the page.

On macOS/Linux, create a virtual environment with `python3 -m venv .venv`, activate it with `. .venv/bin/activate`, install with `python -m pip install -r requirements.txt`, build with `(cd frontend && npm ci && npm run build)`, then run `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`.

## Ask Mai: optional OpenAI or Anthropic questions

After setup, use this command **instead of** `start.cmd` to connect one or both providers for the current run. It prompts in your terminal with hidden input. Press Enter to skip a provider. Never paste keys into chat, the web UI, a tracked file, or a browser-side `VITE_*` variable.

```powershell
.\.venv\Scripts\python.exe start_with_ai.py
```

On macOS/Linux, use `python start_with_ai.py` from the activated environment. Alternatively, supply `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` through a trusted local environment or secret manager and start normally. `OPENAI_MODEL` and `ANTHROPIC_MODEL` optionally select a model your account can access. A configured key is not a verified key; no provider is contacted until you submit a question.

In **Ask Mai**, click **Check provider configuration**, choose a configured provider, optionally include the selected fictional order, and ask **“How many Arc lamps are available, and how many are reserved?”** Compare the answer with the inventory screen. Only the selected provider receives the question and synthetic context; prompting requires internet and may incur charges. Never include personal or work information in a question. Answers are advisory text, not commands: the assistant cannot place an order, run SQL or move a shipment. Without keys, use the complete inventory and fulfillment workflow offline.

## A three-minute walkthrough

1. **Find a scarce item.** Search for `ARC-01`. The Arc lamp starts with two units on hand and none reserved.
2. **Reserve one.** Place an order for one lamp and note its generated order ID. One unit remains available. Try reserving two more: the API rejects the order rather than overselling. Search for the original ID to return to it.
3. **Pack, ship, deliver.** Advance the simulation one step at a time. Packing doesn't move stock. Shipping consumes the held unit: on hand drops from two to one, reserved drops to zero, and available stays at one. Delivering it doesn't alter inventory again.
4. **Show persistence.** Refresh and look up the same ID. The order lines and event history survive the refresh. No email, payment or real shipment was sent.

## How it works

```text
React (search, reserve, look up, advance)
              | same-origin JSON
           FastAPI
              | transaction per state change
            SQLite
         stock + orders + timeline
```

The server owns stock and state transitions; the browser never calculates authoritative availability. `available = on hand − reserved`. Placing an order and reserving its units succeed or fail together. Fulfillment commands carry the status the presenter saw; stale commands are rejected rather than advancing or shipping twice. SQLite is deliberate: a laptop can demonstrate a real transaction without administering a separate database server. This is a local simulation with no authentication, not an internet-facing order service.

## Verification

From the project root, using the project Python environment:

```text
python -m pip install -r requirements-dev.txt
python -m unittest discover -s backend/tests -v
python -m unittest discover -s checks -v
```

Run `npm test` from `frontend` for the browser-to-API contract tests. Provider tests use local fakes, never real keys or paid calls.

See [browser verification](checks/README.md) for the end-to-end walkthrough and [interview and release notes](docs/interview.md) before sharing publicly.
