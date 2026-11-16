"""Generated schemas must retain the same bytes in Windows and Linux checkouts."""

import sys

from easyai.domain import export


def test_export_matches_canonical_schemas(tmp_path, monkeypatch):
    from easyai.domain.catalog import SOURCE_ROOT

    monkeypatch.setattr(sys, "argv", ["export", str(tmp_path)])
    export.main()
    for model in export.MODELS:
        name = f"{model.__name__}.json"
        generated = (tmp_path / name).read_bytes()
        assert b"\r" not in generated
        assert generated == (SOURCE_ROOT / "packages/contracts/schema" / name).read_bytes()
