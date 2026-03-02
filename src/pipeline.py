from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import yfinance as yf
from requests import RequestException
from requests.exceptions import ProxyError


@dataclass(frozen=True)
class QuarterRef:
    year: int
    quarter: int

    @property
    def label(self) -> str:
        return f"{self.year}-Q{self.quarter}"


class Form13FIngestionPipeline:
    """Step-1 ingestion for SEC Form 13F + Russell 2000 pricing snapshots."""

    SEC_BASE = "https://www.sec.gov/Archives/edgar/full-index"

    def __init__(
        self,
        data_root: str | Path = "data",
        user_agent: str = "form13f-research/0.1 (your_email@example.com)",
        timeout_seconds: int = 60,
    ) -> None:
        self.data_root = Path(data_root)
        self.sec_index_root = self.data_root / "sec_index"
        self.prices_root = self.data_root / "prices"
        self.price_snapshots_root = self.prices_root / "snapshots"

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov",
            }
        )

        # Fallback session to bypass environment proxy variables when they reject SEC.
        self.session_no_proxy = requests.Session()
        self.session_no_proxy.trust_env = False
        self.session_no_proxy.headers.update(self.session.headers)

        self.timeout_seconds = timeout_seconds

    def run(self, quarters_to_keep: int = 6) -> None:
        """Run full ingestion pipeline after checking external dependencies."""

        self.run_preflight_checks()
        self.run_sec_ingestion(quarters_to_keep=quarters_to_keep)
        self.run_price_ingestion(files_to_keep=quarters_to_keep)

    def run_preflight_checks(self) -> None:
        """Validate outbound access required for SEC and Yahoo Finance dependencies."""

        self._precheck_connectivity()
        self._precheck_yfinance_connectivity()

    def run_sec_ingestion(self, quarters_to_keep: int = 6) -> None:
        """Download and retain SEC index snapshots only."""

        self._precheck_connectivity()
        quarters = list(self._last_n_quarters(quarters_to_keep))
        for qref in quarters:
            filings_df = self._download_and_filter_master_index(qref)
            out_dir = self.sec_index_root / qref.label
            out_dir.mkdir(parents=True, exist_ok=True)
            filings_df.to_csv(out_dir / "13f_filings.csv", index=False)

        self._apply_quarter_dir_retention(self.sec_index_root, quarters_to_keep)

    def run_price_ingestion(self, files_to_keep: int = 6) -> None:
        """Download Russell 2000 list and latest Yahoo Finance price snapshot only."""

        self._precheck_yfinance_connectivity()
        tickers_df = self._download_russell_2000_tickers()
        self.prices_root.mkdir(parents=True, exist_ok=True)
        tickers_df.to_csv(self.prices_root / "russell2000_tickers.csv", index=False)

        prices_df = self._download_latest_prices(tickers_df["ticker"].tolist())
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.price_snapshots_root.mkdir(parents=True, exist_ok=True)
        prices_df.to_csv(
            self.price_snapshots_root / f"russell2000_prices_{ts}.csv",
            index=False,
        )

        self._apply_file_retention(self.price_snapshots_root, files_to_keep)

    def _precheck_connectivity(self) -> None:
        """Fail fast with a clear error if SEC endpoints are unreachable."""

        probe_url = f"{self.SEC_BASE}/"
        try:
            response = self._get_sec_url(probe_url, timeout=min(self.timeout_seconds, 15))
            response.raise_for_status()
        except RequestException as exc:
            raise ConnectionError(
                "SEC connectivity precheck failed. "
                f"Could not reach {probe_url}. "
                "Check proxy/network settings (for example HTTPS_PROXY/HTTP_PROXY) "
                "or retry from a network that can access www.sec.gov. "
                f"Last error: {exc}"
            ) from exc

    def _precheck_yfinance_connectivity(self) -> None:
        """Fail fast with a clear error if Yahoo Finance dependencies are unreachable."""

        try:
            history = yf.Ticker("AAPL").history(period="1d", auto_adjust=False)
            if history.empty:
                raise ConnectionError("Received empty price history for AAPL.")
        except Exception as exc:  # noqa: BLE001
            raise ConnectionError(
                "Yahoo Finance connectivity precheck failed. "
                "Could not fetch sample ticker data for AAPL. "
                f"Last error: {exc}"
            ) from exc

    def _get_sec_url(self, url: str, timeout: int) -> requests.Response:
        """Request SEC URL and retry once without env proxies if proxy tunnel is rejected."""

        try:
            return self.session.get(url, timeout=timeout)
        except ProxyError:
            return self.session_no_proxy.get(url, timeout=timeout)

    def _download_and_filter_master_index(self, qref: QuarterRef) -> pd.DataFrame:
        url = f"{self.SEC_BASE}/{qref.year}/QTR{qref.quarter}/master.idx"
        response = self._get_sec_url(url, timeout=self.timeout_seconds)
        response.raise_for_status()

        lines = response.text.splitlines()
        data_start = next((i for i, line in enumerate(lines) if line.startswith("----")), None)
        if data_start is None:
            raise ValueError(f"Unexpected SEC master index format for {qref.label}")

        records: list[dict[str, str]] = []
        for raw in lines[data_start + 1 :]:
            parts = raw.split("|")
            if len(parts) != 5:
                continue
            cik, company_name, form_type, filing_date, filename = parts
            if form_type not in {"13F-HR", "13F-HR/A"}:
                continue
            records.append(
                {
                    "quarter": qref.label,
                    "cik": cik,
                    "company_name": company_name,
                    "form_type": form_type,
                    "filing_date": filing_date,
                    "filename": filename,
                    "filing_url": f"https://www.sec.gov/Archives/{filename}",
                }
            )

        return pd.DataFrame.from_records(records)

    @staticmethod
    def _last_n_quarters(n: int) -> Iterable[QuarterRef]:
        now = datetime.now(tz=timezone.utc)
        current_q = ((now.month - 1) // 3) + 1
        year = now.year

        output: list[QuarterRef] = []
        for _ in range(n):
            output.append(QuarterRef(year=year, quarter=current_q))
            current_q -= 1
            if current_q == 0:
                current_q = 4
                year -= 1
        return reversed(output)

    @staticmethod
    def _download_russell_2000_tickers() -> pd.DataFrame:
        wiki_url = "https://en.wikipedia.org/wiki/Russell_2000_Index"
        tables = pd.read_html(wiki_url)

        candidate = None
        for tbl in tables:
            cols = [str(c).strip().lower() for c in tbl.columns]
            if "ticker" in cols or "symbol" in cols:
                candidate = tbl
                break

        if candidate is None:
            raise ValueError("Could not find Russell 2000 ticker table on source page.")

        col_map = {str(c).strip().lower(): c for c in candidate.columns}
        ticker_col = col_map.get("ticker") or col_map.get("symbol")
        if ticker_col is None:
            raise ValueError("No ticker/symbol column found in Russell 2000 table.")

        df = candidate[[ticker_col]].copy()
        df.columns = ["ticker"]
        df["ticker"] = df["ticker"].astype(str).str.strip().str.upper()
        df = df[df["ticker"].str.len() > 0]
        df = df.drop_duplicates().reset_index(drop=True)
        return df

    @staticmethod
    def _download_latest_prices(tickers: list[str]) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame(columns=["ticker", "close", "currency"])

        rows = []
        for ticker in tickers:
            try:
                history = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
            except Exception:
                history = pd.DataFrame()

            if history.empty:
                rows.append({"ticker": ticker, "close": None, "currency": None})
                continue

            latest = history.iloc[-1]
            rows.append(
                {
                    "ticker": ticker,
                    "close": float(latest.get("Close")),
                    "currency": "USD",
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _apply_quarter_dir_retention(path: Path, quarters_to_keep: int) -> None:
        if not path.exists():
            return

        quarter_dirs = [p for p in path.iterdir() if p.is_dir() and "-Q" in p.name]
        quarter_dirs_sorted = sorted(quarter_dirs, key=lambda p: p.name, reverse=True)

        for item in quarter_dirs_sorted[quarters_to_keep:]:
            for child in item.rglob("*"):
                if child.is_file():
                    child.unlink()
            for child in sorted(item.rglob("*"), reverse=True):
                if child.is_dir():
                    child.rmdir()
            item.rmdir()

    @staticmethod
    def _apply_file_retention(path: Path, files_to_keep: int) -> None:
        if not path.exists():
            return

        files = sorted([p for p in path.iterdir() if p.is_file()], key=lambda p: p.name, reverse=True)
        for item in files[files_to_keep:]:
            item.unlink()
