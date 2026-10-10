"""Command-line entry point for rebuilding TalentGuard outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services import DEFAULT_ARTIFACT_DIR, DEFAULT_DATASET, DEFAULT_OUTPUT_DIR, train_and_export


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train TalentGuard and export its ranked watch list.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = train_and_export(args.dataset, args.output_dir, args.artifact_dir)
    selected = metrics["selected_model_score"]
    summary = {
        "selected_model": metrics["selected_model"],
        "average_precision": round(selected["average_precision"], 4),
        "precision_at_50": round(selected["precision_at_50"], 4),
        "recall_at_50": round(selected["recall_at_50"], 4),
        "lift_at_50": round(selected["lift_at_50"], 2),
        "output_dir": str(args.output_dir.resolve()),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
