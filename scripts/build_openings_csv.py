"""One-off: convert the Lichess chess-openings parquet into the bundled CSV.

The `img` column (board images, almost all of the 226 MB) is dropped.
`id` is the row's position in the parquet file.

Usage (from the repository root; pyarrow is not a project dependency):
    uv run --with pyarrow python scripts/build_openings_csv.py
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "raw" / "train-00000-of-00001.parquet"
TARGET = ROOT / "familyagent" / "data" / "openings.csv"
SOURCE_COLUMNS = ["eco-volume", "eco", "name", "pgn", "uci", "epd"]
HEADER = ["id", "eco_volume", "eco", "name", "pgn", "uci", "epd"]


def main() -> int:
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("pyarrow is missing. Run: uv run --with pyarrow python scripts/build_openings_csv.py")
        return 1
    if not SOURCE.exists():
        print(f"Source file not found: {SOURCE}")
        return 1

    table = pq.read_table(SOURCE, columns=SOURCE_COLUMNS)
    columns = [table.column(name).to_pylist() for name in SOURCE_COLUMNS]

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(HEADER)
        for i, values in enumerate(zip(*columns)):
            cleaned = [" ".join(str(v).split()) for v in values]
            if not all(cleaned):
                print(f"Row {i} has an empty field: {cleaned}")
                return 1
            writer.writerow([i, *cleaned])

    names = columns[SOURCE_COLUMNS.index("name")]
    print(f"rows:          {table.num_rows}")
    print(f"unique names:  {len(set(names))}")
    print(f"file:          {TARGET.relative_to(ROOT)}")
    print(f"size:          {TARGET.stat().st_size / 1024:.0f} KB")
    print("first row:     ", [c[0] for c in columns])
    return 0


if __name__ == "__main__":
    sys.exit(main())
