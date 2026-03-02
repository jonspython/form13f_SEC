# Form 13F + Russell 2000 Data Framework (Step 1)

This repository includes a **starter ingestion framework** for your Step 1 goal:

1. Download SEC Form 13F filings by quarter.
2. Keep a rolling retention window (default: 6 quarters).
3. Pull Russell 2000 ticker symbols.
4. Pull latest market prices via `yfinance` for those symbols.
5. Save data to structured local folders for Step 2 analytics.

## Project structure

- `src/pipeline.py` – core ingestion framework.
- `src/run_ingestion.py` – CLI entrypoint to run ingestion.
- `requirements.txt` – Python dependencies.

Data output folders (created automatically):

- `data/sec_index/` – quarter-level SEC master index extracts filtered to 13F.
- `data/prices/russell2000_tickers.csv` – latest Russell 2000 ticker universe snapshot.
- `data/prices/snapshots/` – timestamped Russell 2000 price snapshots.

## What is done in Git vs Colab?

### In Git (this repo)
- Code and versioning (`src/*.py`, `README.md`, future tests).
- Pull requests and review history.
- Any logic changes (e.g., retention behavior, parsing improvements).

### In Colab (execution environment)
- Running the pipeline on demand or on schedule.
- Installing dependencies for the runtime session.
- Writing output files to local runtime storage or Google Drive.

In short: **Git stores and evolves the framework; Colab runs it and produces data.**

## Colab setup (recommended)

### 1) Clone your Git repo in Colab

```bash
!git clone https://github.com/<your-org-or-user>/form13f_SEC.git
%cd form13f_SEC
```

### 2) Install dependencies

```bash
!pip install -r requirements.txt
```

### 3) (Optional) Mount Google Drive for persistent storage

```python
from google.colab import drive
drive.mount('/content/drive')
```

Use a Drive path for `--data-root`, for example:
`/content/drive/MyDrive/form13f_data`

### 4) Run ingestion

```bash
!python src/run_ingestion.py \
  --quarters 6 \
  --data-root /content/drive/MyDrive/form13f_data \
  --user-agent "your-name your-email@example.com"
```

If you see an argparse error mentioning `\\n`, it usually means literal newline placeholders were pasted.
Use real line breaks with trailing `\` as shown above, or run as a single line.

### 4b) Run independent stages (recommended for debugging)

You can now run each dependency path independently before full ingestion:

```bash
# SEC + Yahoo reachability checks only
python src/run_ingestion.py --stage preflight --user-agent "your-name your-email@example.com"

# SEC ingest only (13F master index by quarter)
python src/run_ingestion.py --stage sec --quarters 6 --data-root /content/drive/MyDrive/form13f_data --user-agent "your-name your-email@example.com"

# Russell 2000 + Yahoo prices only
python src/run_ingestion.py --stage prices --quarters 6 --data-root /content/drive/MyDrive/form13f_data --user-agent "your-name your-email@example.com"

# Full pipeline (default)
python src/run_ingestion.py --stage full --quarters 6 --data-root /content/drive/MyDrive/form13f_data --user-agent "your-name your-email@example.com"
```

This makes it easy to isolate whether failures are SEC-related, Yahoo-related, or processing-related.

### 4c) Connectivity troubleshooting

If a stage fails with `ProxyError`, `CONNECT tunnel failed`, or `403 Forbidden`, check whether your environment is forcing proxy settings:

```bash
env | rg -i '^(http|https|all|no)_proxy='
```

- SEC failures indicate your path to `www.sec.gov` is blocked by proxy/network policy.
- Yahoo failures indicate your path to Yahoo endpoints (used by `yfinance`) is blocked.

Fix by allowlisting required domains in your proxy, using a network without forced proxy, or setting `NO_PROXY` appropriately if direct egress is allowed.

### 5) Commit code changes back to Git (when you edit code in Colab)

```bash
!git checkout -b feature/improve-ingestion
!git add src README.md requirements.txt
!git commit -m "Improve ingestion behavior"
!git push origin feature/improve-ingestion
```

Then open a PR in GitHub.

## Local quickstart (non-Colab)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/run_ingestion.py --quarters 6 --user-agent "your-name your-email@example.com"
```

## Notes

- SEC requests should include a clear `User-Agent` that identifies you/email.
- The script stores one `13f_filings.csv` per quarter and rotates old quarters beyond your retention target.
- Russell 2000 symbols are sourced from Wikipedia in this starter (replace with a preferred provider if you want a stronger production source).
- `yfinance` returns delayed market data and symbol mapping can vary by exchange suffixes.

## Suggested next step (Step 2)

Once this ingestion layer is stable, build a transform layer to:

- Normalize 13F holdings (CUSIP, shares, value, manager CIK).
- Map CUSIPs to tickers (if needed via external mapping).
- Join with market prices and calculate position-level/manager-level changes across quarters.
