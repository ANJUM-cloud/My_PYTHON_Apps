# Python Full-Stack Web Portfolio

Three independent Flask applications:

1. **TaskFlow Pro** — task and project tracking
2. **StockWise** — inventory and stock control
3. **CareerTrack** — job application pipeline

Each folder is standalone: source, templates, CSS, dependencies, `.env.example`, tests and deployment guide.
Recommended order: TaskFlow -> StockWise -> CareerTrack. Python 3.10+ required.

Quick start (inside a project folder):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python app.py
```

See `CHANGES.md` for what was corrected in this revision and what still needs to be verified by running it.
