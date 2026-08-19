import csv
from pathlib import Path

from wit_pytools.csvtools import csv_transform


EXAMPLES_DIR = Path(__file__).parent / "csvtools"


def test_csv_transform_passwordsapp_to_passman(tmp_path):
    target_file = tmp_path / "target.csv"

    csv_transform(
        EXAMPLES_DIR / "passwordsapp-export-example_v2026_7_20.csv",
        target_file,
        EXAMPLES_DIR / "passwordsapp-to-passman-mapping.csv",
    )

    with target_file.open(encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        rows = list(reader)

    assert reader.fieldnames == [
        "label",
        "description",
        "changed",
        "tags",
        "username",
        "password",
        "url",
        "custom_fields",
    ]
    assert len(rows) == 1
    assert rows[0]["label"] == "Name"
    assert rows[0]["description"] == "notes"
    assert rows[0]["tags"] == "tag1,tag2"
    assert rows[0]["username"] == "user"
    assert rows[0]["password"] == "password"
    assert rows[0]["url"] == "website"
