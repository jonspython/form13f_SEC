# Form 13F + Russell 2000 Data Framework (Step 1)

This repository now includes a **starter ingestion framework** for your Step 1 goal:

1. Download all SEC Form 13F filings by quarter.
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
- `data/prices/` – Russell 2000 ticker snapshots and price snapshots.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/run_ingestion.py --quarters 6
```

## Notes

- SEC requests should include a clear `User-Agent` that identifies you/email.
- The script stores one `13f_filings.csv` per quarter and rotates old quarters beyond your retention target.
- Russell 2000 symbols are sourced from Wikipedia in this starter (replace with a preferred provider if you want a stronger production source).
- `yfinance` returns delayed market data and symbol mapping can vary by exchange suffixes.

## Suggested next step (Step 2)

Once you confirm this ingestion layer is stable, build a transform layer to:

- Normalize 13F holdings (CUSIP, shares, value, manager CIK).
- Map CUSIPs to tickers (if needed via external mapping).
- Join with market prices and calculate position-level/manager-level changes across quarters.
