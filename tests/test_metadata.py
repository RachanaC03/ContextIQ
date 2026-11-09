import copy

import pytest

from contextiq.metadata import load_metadata


def test_metadata_validates(meta):
    meta.validate()


def test_product_names_match_database(meta, db):
    names = dict(db.execute("SELECT product_id, name FROM products").fetchall())
    assert {p.id: p.name for p in meta.products.values()} == names


def test_every_catalog_column_exists_in_database(meta, db):
    for t in meta.tables.values():
        cols = [r[1] for r in db.execute(f"PRAGMA table_info({t.name})")]
        assert set(cols) == set(t.columns), t.name


def test_validation_catches_unknown_table(meta):
    bad = copy.deepcopy(meta)
    bad.lineage.append({"upstream": "nope", "downstream": "orders"})
    with pytest.raises(ValueError, match="unknown table nope"):
        bad.validate()


def test_validation_catches_bad_role_column(meta):
    bad = copy.deepcopy(meta)
    bad.roles["support_analyst"]["tables"]["orders"] = {"deny_columns": ["ghost"]}
    with pytest.raises(ValueError, match="ghost"):
        bad.validate()


def test_load_metadata_from_disk(settings):
    assert "complaints_monthly" in load_metadata(settings.context_dir).tables
