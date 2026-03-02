import argparse
import sys

from pipeline import Form13FIngestionPipeline


def _sanitize_cli_tokens(argv: list[str] | None = None) -> list[str]:
    """Drop accidental newline placeholders copied from notebook snippets."""

    tokens = list(sys.argv[1:] if argv is None else argv)
    return [token for token in tokens if token not in {"\\n", "\n"}]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step-1 Form 13F ingestion pipeline")
    parser.add_argument("--quarters", type=int, default=6, help="How many quarters to retain")
    parser.add_argument(
        "--data-root",
        type=str,
        default="data",
        help="Output folder for generated data (use a Drive path in Colab if desired)",
    )
    parser.add_argument(
        "--user-agent",
        type=str,
        default="form13f-research/0.1 (your_email@example.com)",
        help="SEC-compliant User-Agent string",
    )
    return parser.parse_args(_sanitize_cli_tokens(argv))


def main() -> None:
    args = parse_args()
    pipeline = Form13FIngestionPipeline(data_root=args.data_root, user_agent=args.user_agent)
    pipeline.run(quarters_to_keep=args.quarters)


if __name__ == "__main__":
    main()
