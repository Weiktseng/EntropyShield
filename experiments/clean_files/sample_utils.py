"""Utility functions for data processing."""

import json
from pathlib import Path
from typing import Optional


def load_json(filepath: str) -> dict:
    """Load JSON file and return parsed dictionary."""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, filepath: str, indent: int = 2) -> None:
    """Save dictionary to JSON file with proper encoding."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)


def find_files(directory: str, pattern: str = "*.txt") -> list[Path]:
    """Recursively find files matching a glob pattern."""
    return sorted(Path(directory).rglob(pattern))


def chunk_list(items: list, size: int) -> list[list]:
    """Split a list into chunks of specified size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


class DataProcessor:
    """Simple pipeline for processing text records."""

    def __init__(self, source_dir: str, output_dir: Optional[str] = None):
        self.source = Path(source_dir)
        self.output = Path(output_dir) if output_dir else self.source / "processed"
        self.output.mkdir(parents=True, exist_ok=True)

    def process(self, transform_fn=None) -> int:
        """Process all JSON files, applying optional transform."""
        count = 0
        for fp in self.source.glob("*.json"):
            data = load_json(str(fp))
            if transform_fn:
                data = transform_fn(data)
            save_json(data, str(self.output / fp.name))
            count += 1
        return count
