import argparse
from pathlib import Path

from wit_pytools.anonymization import create_mapping
from wit_pytools.documenttools import anonymize_xlsx, identify_xlsx_strings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("overwrite", type=int, choices=(0, 1))
    parser.add_argument("group_contained_values", type=int, choices=(0, 1))
    args = parser.parse_args()

    if not args.candidates.exists():
        print(identify_xlsx_strings(args.source))
        print("Candidates created. Review the CSV before the next run.")
        return 0

    overwrite = bool(args.overwrite)
    mapping_stem = args.candidates.stem
    if mapping_stem.endswith("_candidates"):
        mapping_stem = mapping_stem[: -len("_candidates")]
    mapping = args.candidates.with_name(f"{mapping_stem}_mapping.csv")
    if not mapping.exists():
        mapping = create_mapping(
            args.candidates,
            overwrite=overwrite,
            group_contained_values=bool(args.group_contained_values),
        )
    else:
        print(f"Using existing mapping: {mapping}")
    output = anonymize_xlsx(args.source, mapping, overwrite=overwrite)
    print(mapping)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
