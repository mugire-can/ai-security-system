#!/usr/bin/env python3
"""
Validate the evaluation manifest scaffold.

This is a light structural check for the benchmark/evaluation layout. It does
not score models; it verifies that the manifest and referenced paths follow the
expected contract before a real evaluation run is attempted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_SCENARIO_KEYS = {
    "id",
    "venue_type",
    "camera_id",
    "video_path",
    "label_path",
    "expected_events",
}


def validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"Manifest not found: {path}"]
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON in {path}: {exc}"]

    if "scenarios" not in payload or not isinstance(payload["scenarios"], list):
        errors.append("Manifest must contain a list field named 'scenarios'")
        return errors

    for idx, scenario in enumerate(payload["scenarios"], start=1):
        if not isinstance(scenario, dict):
            errors.append(f"Scenario #{idx} is not an object")
            continue

        missing = REQUIRED_SCENARIO_KEYS.difference(scenario.keys())
        if missing:
            errors.append(
                f"Scenario #{idx} is missing keys: {', '.join(sorted(missing))}"
            )
            continue

        if not isinstance(scenario["expected_events"], list) or not scenario["expected_events"]:
            errors.append(
                f"Scenario #{idx} must define a non-empty 'expected_events' list"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate evaluation manifest structure")
    parser.add_argument(
        "manifest",
        nargs="?",
        default="evaluation/manifest.example.json",
        help="Path to the manifest JSON file",
    )
    args = parser.parse_args()

    errors = validate_manifest(Path(args.manifest))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Evaluation manifest structure looks valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
