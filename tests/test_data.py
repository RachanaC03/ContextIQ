import json

from contextiq.config import Settings
from contextiq.synth.generate import generate


def q(db, sql, *args):
    return db.execute(sql, args).fetchall()


def test_order_count(db):
    assert q(db, "SELECT COUNT(*) FROM orders")[0][0] == 20000


def test_complaint_count(db):
    assert q(db, "SELECT COUNT(*) FROM complaints")[0][0] == 380


def test_eight_products(db):
    assert q(db, "SELECT COUNT(*) FROM products")[0][0] == 8


def test_every_complaint_references_a_real_order_of_same_product(db):
    bad = q(db, "SELECT COUNT(*) FROM complaints c LEFT JOIN orders o ON o.order_id = c.order_id "
                "WHERE o.order_id IS NULL OR o.product_id != c.product_id")
    assert bad[0][0] == 0


def test_p104_october_rate_is_about_16_percent(db):
    rate = q(db, "SELECT complaint_rate_pct FROM complaints_monthly WHERE month='2026-10' AND product_id='P-104'")[0][0]
    assert 14.5 <= rate <= 17.5


def test_p104_baseline_is_about_3_9_percent(db):
    avg = q(db, "SELECT AVG(complaint_rate_pct) FROM complaints_monthly "
                "WHERE product_id='P-104' AND month < '2026-10'")[0][0]
    assert 3.0 <= avg <= 4.8


def test_every_october_p104_complaint_traces_to_faulty_batch(db):
    rows = q(db, "SELECT DISTINCT batch_id, category FROM complaints "
                 "WHERE product_id='P-104' AND complaint_date LIKE '2026-10%'")
    assert rows == [("B-2026-09B", "heating_element_failure")]


def test_faulty_batch_uses_new_supplier(db):
    assert q(db, "SELECT supplier FROM production_batches WHERE batch_id='B-2026-09B'")[0][0] == "Zenvolt Components"


def test_p107_is_second_most_affected_in_october(truth):
    assert truth["october_ranking"][:2] == ["P-104", "P-107"]


def test_p107_complaints_are_delivery_delays(db):
    cats = {r[0] for r in q(db, "SELECT DISTINCT category FROM complaints WHERE product_id='P-107' "
                                "AND complaint_date LIKE '2026-10%'")}
    assert "delivery_delay" in cats


def test_other_products_stay_near_baseline_in_october(db):
    rates = q(db, "SELECT complaint_rate_pct FROM complaints_monthly WHERE month='2026-10' "
                  "AND product_id NOT IN ('P-104','P-107')")
    assert all(r[0] < 4.0 for r in rates)


def test_complaints_monthly_matches_raw_complaints(db):
    raw = q(db, "SELECT substr(complaint_date,1,7), product_id, COUNT(*) FROM complaints GROUP BY 1,2")
    agg = {(m, p): c for m, p, c in q(db, "SELECT month, product_id, complaints FROM complaints_monthly")}
    assert all(agg[(m, p)] == c for m, p, c in raw)
    assert sum(agg.values()) == 380


def test_legacy_table_is_stale_and_deprecated(db, meta):
    last = q(db, "SELECT MAX(month) FROM legacy_complaint_stats")[0][0]
    assert last <= "2026-06"
    assert meta.tables["legacy_complaint_stats"].deprecated


def test_documents_cover_all_four_tiers_with_unique_ids(settings):
    docs = [json.loads(line) for line in settings.documents_path.read_text().splitlines()]
    assert {d["tier"] for d in docs} == {"general", "support", "quality", "finance"}
    assert len({d["doc_id"] for d in docs}) == len(docs)


def test_ground_truth_root_cause(truth):
    rc = truth["root_cause"]
    assert (rc["product_id"], rc["batch_id"]) == ("P-104", "B-2026-09B")
    assert rc["traced_to_batch"] == rc["october_p104_complaints"]
    assert truth["decoy_table"] == "legacy_complaint_stats"


def test_generation_is_deterministic(tmp_path):
    a, b = Settings(generated_dir=tmp_path / "a"), Settings(generated_dir=tmp_path / "b")
    generate(a)
    generate(b)
    assert json.loads(a.ground_truth_path.read_text()) == json.loads(b.ground_truth_path.read_text())
