from pathlib import Path
from unittest.mock import MagicMock

import pytest

from wit_pytools.aufmass.tablesimport import (
    NextcloudTablesImporter,
    TablesImportError,
    read_table_map,
    run_import,
)


def _state(**kw):
    state = {
        "found_columns_count": 10,
        "matching_columns_count": 10,
        "created_columns_count": 0,
        "inserted_rows_count": 5,
        "updated_rows_count": 0,
        "errors_parsing_count": 0,
        "errors_count": 0,
    }
    state.update(kw)
    return state


def test_verify_import_state_ok():
    NextcloudTablesImporter.verify_import_state(_state())


@pytest.mark.parametrize("kw", [
    {"errors_count": 1},
    {"errors_parsing_count": 2},
    {"inserted_rows_count": 0, "updated_rows_count": 0},
])
def test_verify_import_state_fails(kw):
    with pytest.raises(TablesImportError):
        NextcloudTablesImporter.verify_import_state(_state(**kw))


def test_read_table_map(tmp_path):
    map_file = tmp_path / "map.csv"
    map_file.write_text(
        "file,table_id,view_id\n"
        "a.csv,11,\n"
        "room/b.csv,22,33\n",
        encoding="utf-8")
    table_map = read_table_map(map_file)
    assert table_map["a.csv"] == (11, None)
    assert table_map["room/b.csv"] == (22, 33)


def test_importer_urls():
    imp = NextcloudTablesImporter("https://nc.example.com/", "u", "p")
    assert imp.dav_root == "https://nc.example.com/remote.php/dav/files/u"
    assert imp.api_root == "https://nc.example.com/index.php/apps/tables/api/1"


def test_upload_and_import(tmp_path):
    local = tmp_path / "list.csv"
    local.write_text("a,b\n1,2\n", encoding="utf-8")
    imp = NextcloudTablesImporter("https://nc.example.com", "u", "p")
    imp.session = MagicMock()

    mkcol = MagicMock(status_code=201)
    put = MagicMock(status_code=201)
    imp.session.request.return_value = mkcol
    imp.session.put.return_value = put

    nc_path = imp.upload_file(local, "Aufmass/Import")
    assert nc_path == "Aufmass/Import/list.csv"
    assert imp.session.request.call_count == 2  # both dir segments
    put_call = imp.session.put.call_args
    assert put_call.args[0].endswith(
        "/remote.php/dav/files/u/Aufmass/Import/list.csv")

    post = MagicMock(status_code=200)
    post.json.return_value = _state(inserted_rows_count=1)
    imp.session.post.return_value = post
    state = imp.import_table(42, nc_path)
    call = imp.session.post.call_args
    assert call.args[0].endswith("/import/table/42")
    assert call.kwargs["json"] == {
        "path": "Aufmass/Import/list.csv", "createMissingColumns": True}
    assert state["inserted_rows_count"] == 1


def test_import_http_error():
    imp = NextcloudTablesImporter("https://nc.example.com", "u", "p")
    imp.session = MagicMock()
    resp = MagicMock(status_code=404)
    resp.text = '{"message": "no table"}'
    imp.session.post.return_value = resp
    with pytest.raises(TablesImportError, match="404"):
        imp.import_table(99, "x.csv")


def test_run_import_dry_run(tmp_path):
    (tmp_path / "a.csv").write_text("x\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("x\n", encoding="utf-8")
    map_file = tmp_path / "map.csv"
    map_file.write_text("file,table_id\na.csv,11\n", encoding="utf-8")
    results = run_import(
        None, sorted(tmp_path.glob("*.csv")), "remote",
        table_map=read_table_map(map_file), base_dir=tmp_path,
        dry_run=True)
    assert results[0]["table_id"] == 11
    assert results[1]["error"] == "no table_id in map"


def test_run_import_table_id_for_all(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x\n", encoding="utf-8")
    results = run_import(
        None, [f], "remote", table_id=7, dry_run=True)
    assert results[0]["table_id"] == 7
