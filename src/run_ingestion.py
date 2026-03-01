import argparse

from pipeline import Form13FIngestionPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step-1 Form 13F ingestion pipeline")
    parser.add_argument("--quarters", type=int, default=6, help="How many quarters to retain")
    parser.add_argument(
        "--user-agent",
        type=str,
        default="form13f-research/0.1 (your_email@example.com)",
        help="SEC-compliant User-Agent string",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline = Form13FIngestionPipeline(user_agent=args.user_agent)
    pipeline.run(quarters_to_keep=args.quarters)


if __name__ == "__main__":
    main()
