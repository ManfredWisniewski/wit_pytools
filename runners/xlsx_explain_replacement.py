import argparse
from collections import Counter
from pathlib import Path

from wit_pytools.documenttools import explain_xlsx_replacement


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Show which cells and mapping keys produce a replacement token."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("replacement")
    args = parser.parse_args()

    rows = explain_xlsx_replacement(args.source, args.mapping, args.replacement)
    print(f"Cells containing {args.replacement!r}: {len(rows)}")

    counts = Counter(key for row in rows for key in row["matched_keys"])
    print("\nMatched keys (count, key):")
    for key, count in counts.most_common():
        print(f"  {count:4d}  {key!r}")

    partial = [row for row in rows if row["matched_keys"] != [row["original"]]]
    print(f"\nPartial matches inside longer strings: {len(partial)}")
    for row in partial:
        print(
            f"  {row['worksheet']}!{row['cell']}: {row['original']!r}"
            f"\n      -> {row['result']!r}"
            f"\n      via {row['matched_keys']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
