"""Synthetic Hearthline data: tables, documents and a planted ground-truth story.

Planted story (Jan-Oct 2026):
  * P-104 AeroBrew Pro: batch B-2026-09B has a faulty heating element from a new supplier.
    Complaint rate jumps from about 3.9% to about 16% in October; every October P-104
    complaint traces to that batch.
  * P-107 Robo Vac R2: a carrier change causes delivery-delay complaints (a confounder).
  * legacy_complaint_stats is a deprecated, stale table with a different metric (a decoy).
"""
from __future__ import annotations

import json
import random
import sqlite3
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta

from ..config import Settings
from ..metadata import load_metadata

YEAR = 2026
MONTHS = [f"{YEAR}-{m:02d}" for m in range(1, 11)]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October"]
MONTHLY_ORDERS = [1800, 1750, 1900, 1950, 2000, 2050, 1950, 2000, 2100, 2500]  # sums to 20,000
TARGET_COMPLAINTS = 380
FAULTY_BATCH = "B-2026-09B"
FAULTY_SUPPLIER = "Zenvolt Components"
OLD_SUPPLIER = "Calderon Heating Works"
CORE_SUPPLIER = "Hearthline Core Suppliers"
CHANNELS = ["web", "retail", "marketplace"]

# id, name, category, list_price, unit_cost, order share
PRODUCTS = [
    ("P-101", "Toastella 2-Slice Toaster", "Kitchen", 39.0, 18.0, 0.13),
    ("P-102", "BlendMate 600 Blender", "Kitchen", 59.0, 27.0, 0.14),
    ("P-103", "KettleOne Electric Kettle", "Kitchen", 34.0, 15.0, 0.13),
    ("P-104", "AeroBrew Pro Coffee Maker", "Kitchen", 89.0, 41.0, 0.14),
    ("P-105", "CrispAir Mini Fryer", "Kitchen", 79.0, 36.0, 0.13),
    ("P-106", "WhiskWiz Hand Mixer", "Kitchen", 29.0, 12.0, 0.11),
    ("P-107", "Robo Vac R2", "Home care", 149.0, 74.0, 0.12),
    ("P-108", "PureMist Humidifier", "Home care", 49.0, 22.0, 0.10),
]
NAME = {p[0]: p[1] for p in PRODUCTS}
BASE_RATE = {"P-101": 1.2, "P-102": 1.4, "P-103": 1.0, "P-104": 3.9,
             "P-105": 1.6, "P-106": 1.1, "P-107": 1.3, "P-108": 1.3}

BASE_CATEGORIES = ["noise", "cosmetic_damage", "missing_accessory", "packaging_damage", "performance_issue"]
DESCRIPTIONS = {
    "noise": "The unit makes a loud rattling noise when running.",
    "cosmetic_damage": "Arrived with scratches on the housing.",
    "missing_accessory": "An accessory listed in the box contents was missing.",
    "packaging_damage": "The outer box was crushed and the product was dented.",
    "performance_issue": "The product works but performs worse than the description promised.",
    "delivery_delay": "The order arrived many days later than the delivery date promised at checkout.",
    "heating_element_failure": "The coffee maker stopped heating water; the brew comes out lukewarm.",
}


def _fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def generate(settings: Settings) -> dict:
    """Generate the SQLite database, documents.jsonl and ground_truth.json. Returns a summary."""
    settings.ensure_dirs()
    meta = load_metadata(settings.context_dir)
    rng = random.Random(settings.seed)
    pids = [p[0] for p in PRODUCTS]
    shares = [p[5] for p in PRODUCTS]
    price = {p[0]: p[3] for p in PRODUCTS}
    cost = {p[0]: p[4] for p in PRODUCTS}

    # ---------------- orders ----------------
    orders = []
    cell_orders: dict[tuple[str, str], list[int]] = defaultdict(list)
    oid = 0
    for mi, month in enumerate(MONTHS):
        m = mi + 1
        days = monthrange(YEAR, m)[1]
        for _ in range(MONTHLY_ORDERS[mi]):
            oid += 1
            pid = rng.choices(pids, weights=shares)[0]
            d = date(YEAR, m, rng.randint(1, days))
            qty = rng.choices([1, 2, 3], [0.78, 0.17, 0.05])[0]
            unit_price = round(price[pid] * rng.choice([1.0, 1.0, 0.95, 0.9]), 2)
            batch = FAULTY_BATCH if (pid == "P-104" and month == "2026-10") else f"B-2026-{m:02d}A"
            orders.append((f"O-{oid:06d}", f"C{rng.randint(1, 7000):05d}", pid, batch,
                           d.isoformat(), qty, unit_price, rng.choice(CHANNELS)))
            cell_orders[(month, pid)].append(len(orders) - 1)

    # ---------------- complaint counts per (month, product) ----------------
    base_n: dict[tuple[str, str], int] = {}
    extra_n: dict[tuple[str, str], int] = {}
    for month in MONTHS:
        for pid in pids:
            n_orders = len(cell_orders[(month, pid)])
            if pid == "P-104" and month == "2026-10":
                rate = rng.uniform(15.6, 16.4)
            else:
                rate = BASE_RATE[pid] * rng.uniform(0.85, 1.15)
            base_n[(month, pid)] = round(n_orders * rate / 100)
            extra = 0.0
            if pid == "P-107" and month == "2026-10":
                extra = 4.6   # carrier change: delivery delays
            elif pid == "P-107" and month == "2026-09":
                extra = 1.2
            extra_n[(month, pid)] = round(n_orders * extra / 100)

    protected = {("2026-10", "P-104"), ("2026-10", "P-107"), ("2026-09", "P-107")}
    adjustable = [c for c in base_n if c not in protected and base_n[c] > 0]
    total = sum(base_n.values()) + sum(extra_n.values())
    while total != TARGET_COMPLAINTS:
        c = rng.choice(adjustable)
        if total > TARGET_COMPLAINTS and base_n[c] > 0:
            base_n[c] -= 1
            total -= 1
        elif total < TARGET_COMPLAINTS:
            base_n[c] += 1
            total += 1

    # ---------------- complaints ----------------
    raw_complaints = []
    for (month, pid), idxs in cell_orders.items():
        n_extra, n_base = extra_n[(month, pid)], base_n[(month, pid)]
        chosen = rng.sample(idxs, n_extra + n_base)
        y, m = int(month[:4]), int(month[5:])
        month_end = date(y, m, monthrange(y, m)[1])
        for k, oi in enumerate(chosen):
            order = orders[oi]
            if pid == "P-104" and month == "2026-10":
                cat = "heating_element_failure"
                sev = rng.choice([2, 3, 3])
            elif k < n_extra:
                cat = "delivery_delay"
                sev = rng.choice([1, 1, 2])
            else:
                cat = rng.choice(BASE_CATEGORIES)
                sev = rng.choices([1, 2, 3], [0.5, 0.35, 0.15])[0]
            cdate = min(date.fromisoformat(order[4]) + timedelta(days=rng.randint(1, 12)), month_end)
            raw_complaints.append((cdate.isoformat(), order[0], pid, order[3], cat, sev,
                                   DESCRIPTIONS[cat]))
    raw_complaints.sort(key=lambda r: (r[0], r[1]))
    complaints = [(f"CMP-{i:05d}", r[1], r[2], r[3], r[0], r[4], r[5], r[6])
                  for i, r in enumerate(raw_complaints, 1)]

    # ---------------- batches ----------------
    batches = []
    for pid in pids:
        for m in range(1, 11):
            supplier = (OLD_SUPPLIER if pid == "P-104" else CORE_SUPPLIER)
            batches.append((f"B-2026-{m:02d}A", pid, date(YEAR, m, 5).isoformat(), supplier,
                            rng.randint(1500, 3000)))
    batches.append((FAULTY_BATCH, "P-104", date(YEAR, 9, 18).isoformat(), FAULTY_SUPPLIER, 600))

    # ---------------- monthly aggregates ----------------
    order_by_id = {o[0]: o for o in orders}
    n_orders = Counter((o[4][:7], o[2]) for o in orders)
    n_compl = Counter((c[4][:7], c[2]) for c in complaints)
    monthly = []
    for month in MONTHS:
        for pid in pids:
            o, c = n_orders[(month, pid)], n_compl[(month, pid)]
            monthly.append((month, pid, o, c, round(100.0 * c / o, 2) if o else 0.0))
    stats = {(r[0], r[1]): r for r in monthly}

    gross, cogs, refunds = defaultdict(float), defaultdict(float), defaultdict(float)
    for o in orders:
        gross[(o[4][:7], o[2])] += o[6] * o[5]
        cogs[(o[4][:7], o[2])] += cost[o[2]] * o[5]
    for c in complaints:
        if c[6] >= 2:
            o = order_by_id[c[1]]
            refunds[(c[4][:7], c[2])] += o[6] * o[5]
    revenue = []
    for month in MONTHS:
        for pid in pids:
            g, r = gross[(month, pid)], refunds[(month, pid)]
            net = g - r
            margin = round(100.0 * (net - cogs[(month, pid)]) / net, 1) if net else 0.0
            revenue.append((month, pid, round(g, 2), round(r, 2), round(net, 2), margin))

    legacy = []
    for month in MONTHS[:6]:  # stale: stops in June
        for pid in pids:
            o, c = n_orders[(month, pid)], n_compl[(month, pid)]
            legacy.append((month, pid, round(c / max(1, o * 2.3) * 1000 * rng.uniform(0.7, 1.3), 1)))

    products = [(p[0], p[1], p[2], p[3], p[4]) for p in PRODUCTS]

    # ---------------- write the database ----------------
    if settings.db_path.exists():
        settings.db_path.unlink()
    conn = sqlite3.connect(settings.db_path)
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE products (product_id TEXT PRIMARY KEY, name TEXT, category TEXT, list_price REAL, unit_cost REAL);
    CREATE TABLE orders (order_id TEXT PRIMARY KEY, customer_id TEXT, product_id TEXT, batch_id TEXT,
                         order_date TEXT, quantity INTEGER, unit_price REAL, channel TEXT);
    CREATE TABLE complaints (complaint_id TEXT PRIMARY KEY, order_id TEXT, product_id TEXT, batch_id TEXT,
                             complaint_date TEXT, category TEXT, severity INTEGER, description TEXT);
    CREATE TABLE complaints_monthly (month TEXT, product_id TEXT, orders INTEGER, complaints INTEGER,
                                     complaint_rate_pct REAL);
    CREATE TABLE production_batches (batch_id TEXT, product_id TEXT, produced_date TEXT, supplier TEXT,
                                     units_produced INTEGER);
    CREATE TABLE revenue_monthly (month TEXT, product_id TEXT, gross_revenue REAL, refunds REAL,
                                  net_revenue REAL, gross_margin_pct REAL);
    CREATE TABLE legacy_complaint_stats (month TEXT, product_id TEXT, complaints_per_1000_units REAL);
    """)
    cur.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)
    cur.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", orders)
    cur.executemany("INSERT INTO complaints VALUES (?,?,?,?,?,?,?,?)", complaints)
    cur.executemany("INSERT INTO complaints_monthly VALUES (?,?,?,?,?)", monthly)
    cur.executemany("INSERT INTO production_batches VALUES (?,?,?,?,?)", batches)
    cur.executemany("INSERT INTO revenue_monthly VALUES (?,?,?,?,?,?)", revenue)
    cur.executemany("INSERT INTO legacy_complaint_stats VALUES (?,?,?)", legacy)
    conn.commit()
    conn.close()

    # ---------------- ground truth ----------------
    oct_rates = {pid: stats[("2026-10", pid)][4] for pid in pids}
    ranking = sorted(pids, key=lambda p: -oct_rates[p])
    p104_base = [stats[(m, "P-104")][4] for m in MONTHS[:9]]
    oct_p104 = [c for c in complaints if c[2] == "P-104" and c[4].startswith("2026-10")]
    docs = _build_documents(meta, stats, complaints, revenue, n_orders)

    gold = ["quality_reports-incident-2026-10", "quality_reports-rca-2026-10",
            "quality_reports-supplier-change-2026-09", "support_digests-2026-10",
            "carrier_notices-2026-10", "finance_reports-2026-10"]
    ground_truth = {
        "as_of": settings.as_of,
        "question_period": "2026-10",
        "orders_total": len(orders),
        "complaints_total": len(complaints),
        "october_rates_pct": oct_rates,
        "october_ranking": ranking,
        "p104_baseline_rate_pct": round(sum(p104_base) / len(p104_base), 2),
        "root_cause": {
            "product_id": "P-104", "batch_id": FAULTY_BATCH, "supplier": FAULTY_SUPPLIER,
            "component": "heating element",
            "october_p104_complaints": len(oct_p104),
            "traced_to_batch": sum(1 for c in oct_p104 if c[3] == FAULTY_BATCH),
        },
        "confounder": {"product_id": "P-107", "cause": "carrier change", "category": "delivery_delay"},
        "decoy_table": "legacy_complaint_stats",
        "gold_doc_ids": [d for d in gold if d in {x["doc_id"] for x in docs}],
        "tier_by_doc": {d["doc_id"]: d["tier"] for d in docs},
    }
    settings.ground_truth_path.write_text(json.dumps(ground_truth, indent=2))
    with settings.documents_path.open("w") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")

    return {"orders": len(orders), "complaints": len(complaints), "documents": len(docs),
            "tiers": sorted({d["tier"] for d in docs})}


# ====================================================================== documents
def _doc(meta, source_id, slug, title, text, month="all", product_ids=(), doc_type="note"):
    return {
        "doc_id": f"{source_id}-{slug}",
        "source_id": source_id,
        "tier": meta.doc_sources[source_id].tier,
        "title": title,
        "month": month,
        "product_ids": list(product_ids),
        "doc_type": doc_type,
        "text": text,
    }


def _build_documents(meta, stats, complaints, revenue, n_orders) -> list[dict]:
    docs: list[dict] = []
    pids = [p[0] for p in PRODUCTS]
    cats_by_month: dict[str, Counter] = defaultdict(Counter)
    for c in complaints:
        cats_by_month[c[4][:7]][c[5]] += 1
    rev = {(r[0], r[1]): r for r in revenue}

    # ---- general: product FAQs and policies
    blurbs = {
        "P-101": "Two wide slots, six browning levels and a bagel mode.",
        "P-102": "A 600 W blender with a 1.5 L jar and a pulse button.",
        "P-103": "A 1.7 L electric kettle with auto shut-off and boil-dry protection.",
        "P-104": "A drip coffee maker with a 1.2 L tank, a thermal carafe and a programmable timer.",
        "P-105": "A 3 L air fryer with a digital panel and a dishwasher-safe basket.",
        "P-106": "A five-speed hand mixer with two beaters and two dough hooks.",
        "P-107": "A robot vacuum with 90 minutes of runtime and automatic carpet detection.",
        "P-108": "A 3 L ultrasonic humidifier with a night mode and auto shut-off.",
    }
    for pid in pids:
        docs.append(_doc(
            meta, "product_faq", pid.lower(), f"{NAME[pid]} ({pid}) FAQ",
            f"{NAME[pid]} ({pid}) frequently asked questions.\n\n{blurbs[pid]}\n\n"
            f"Care: clean the removable parts after each use and descale monthly if you have hard water. "
            f"Warranty: every Hearthline product carries a 12-month warranty against manufacturing defects.",
            product_ids=[pid], doc_type="faq"))
    docs.append(_doc(
        meta, "company_policies", "warranty-returns", "Warranty and returns policy",
        "Hearthline warranty and returns policy.\n\nCustomers may return a product within 30 days for a full refund. "
        "Defective products are covered for 12 months and are replaced or refunded.\n\n"
        "Refunds for defective products are issued once the complaint is logged with an order ID.",
        doc_type="policy"))
    docs.append(_doc(
        meta, "company_policies", "complaint-handling", "Complaint handling policy",
        "Complaint handling policy.\n\nEvery complaint is logged with its order ID and production batch ID. "
        "Severity 3 complaints are escalated to Quality Engineering within 24 hours.\n\n"
        "If the complaint rate for a product exceeds 8% in a month, Customer Support must open an incident review "
        "with Quality Engineering and Logistics, and recommend containment actions such as pausing shipments of "
        "the affected batch.",
        doc_type="policy"))

    # ---- support: monthly digests
    for mi, month in enumerate(MONTHS):
        tot_o = sum(n_orders[(month, p)] for p in pids)
        tot_c = sum(stats[(month, p)][3] for p in pids)
        ranked = sorted(pids, key=lambda p: -stats[(month, p)][4])[:3]
        top = "; ".join(f"{NAME[p]} ({p}) at {stats[(month, p)][4]:.1f}%" for p in ranked)
        cats = ", ".join(f"{k} ({v})" for k, v in cats_by_month[month].most_common(3))
        text = (f"Support complaint digest for {MONTH_NAMES[mi]} 2026 ({month}).\n\n"
                f"Hearthline logged {tot_c} customer complaints against {tot_o} orders in {month}, an overall "
                f"complaint rate of {100 * tot_c / tot_o:.2f}%.\n\n"
                f"Highest complaint rates by product: {top}.\n\n"
                f"Most common complaint categories: {cats}.")
        if month == "2026-10":
            text += (
                "\n\nCustomer complaints increased sharply compared with September. The products affected are "
                "AeroBrew Pro (P-104), where heating element failures dominate, and Robo Vac R2 (P-107), where "
                "customers report late deliveries. Recommended actions: escalate the AeroBrew Pro complaints to "
                "Quality Engineering, ask Logistics to review the carrier service level, and proactively contact "
                "affected customers.")
        docs.append(_doc(meta, "support_digests", month, f"Support complaint digest {month}", text,
                         month=month, doc_type="digest"))

    # ---- support: carrier notices
    docs.append(_doc(
        meta, "carrier_notices", "2026-09", "Carrier change notice",
        "Logistics notice, September 2026.\n\nFrom 22 September 2026 bulky items, including the Robo Vac R2 (P-107), "
        "ship with a new carrier, Urbanlane, replacing SwiftFreight. Expect transition delays of three to six days "
        "while routes are re-planned.",
        month="2026-09", product_ids=["P-107"], doc_type="notice"))
    docs.append(_doc(
        meta, "carrier_notices", "2026-10", "Carrier delay update",
        "Logistics update, October 2026.\n\nDelivery delays for the Robo Vac R2 (P-107) continued through October "
        "after the carrier change. Customers received their orders several days after the promised date, which "
        "raised delivery-delay complaints. Logistics is renegotiating the service level with Urbanlane.",
        month="2026-10", product_ids=["P-107"], doc_type="notice"))

    # ---- support: sample tickets
    p104 = [c for c in complaints if c[2] == "P-104" and c[4].startswith("2026-10")][:6]
    p107 = [c for c in complaints if c[2] == "P-107" and c[4].startswith("2026-10") and c[5] == "delivery_delay"][:4]
    for c in p104 + p107:
        docs.append(_doc(
            meta, "support_tickets", c[0].lower(), f"Complaint ticket {c[0]}",
            f"Complaint ticket {c[0]} for {NAME[c[2]]} ({c[2]}), logged {c[4]}.\n\n"
            f"Order {c[1]}, batch {c[3]}, severity {c[6]}. Customer says: {c[7]}",
            month="2026-10", product_ids=[c[2]], doc_type="ticket"))

    # ---- quality
    for mi, month in enumerate(MONTHS[:8]):
        docs.append(_doc(
            meta, "quality_reports", f"summary-{month}", f"Monthly quality summary {month}",
            f"Monthly quality summary for {MONTH_NAMES[mi]} 2026.\n\nIncoming inspection and end-of-line tests were "
            f"within tolerance for all eight products. No systemic defects are open. The AeroBrew Pro heating "
            f"element supplier, {OLD_SUPPLIER}, passed its periodic audit.",
            month=month, doc_type="summary"))
    docs.append(_doc(
        meta, "quality_reports", "supplier-change-2026-09", "Supplier change memo: AeroBrew Pro heating element",
        f"Supplier change memo, September 2026.\n\nTo secure capacity, AeroBrew Pro (P-104) heating elements for "
        f"production batch {FAULTY_BATCH} were sourced from a new supplier, {FAULTY_SUPPLIER}, instead of "
        f"{OLD_SUPPLIER}. Because of schedule pressure the first-article inspection was reduced to a sampling check.",
        month="2026-09", product_ids=["P-104"], doc_type="memo"))
    docs.append(_doc(
        meta, "quality_reports", "inspection-2026-09", "September end-of-line inspection log",
        f"End-of-line inspection log, September 2026.\n\nBatch {FAULTY_BATCH} of AeroBrew Pro was released with a "
        f"reduced sampling plan. No heating failures were seen in the sample, but no extended thermal-cycling "
        f"test was run on the new supplier's elements.",
        month="2026-09", product_ids=["P-104"], doc_type="log"))
    oct_p104 = [c for c in complaints if c[2] == "P-104" and c[4].startswith("2026-10")]
    oct_rate = stats[("2026-10", "P-104")][4]
    sep_rate = stats[("2026-09", "P-104")][4]
    docs.append(_doc(
        meta, "quality_reports", "incident-2026-10", "Incident report INC-2026-10-01: AeroBrew Pro heating failures",
        f"Incident report INC-2026-10-01, October 2026.\n\nSummary: customer complaints for AeroBrew Pro (P-104) "
        f"increased from {sep_rate:.1f}% in September to {oct_rate:.1f}% in October. All {len(oct_p104)} October "
        f"complaints for this product trace to production batch {FAULTY_BATCH}, and every one reports that the "
        f"coffee maker stopped heating water.\n\n"
        f"Root cause: the heating elements in batch {FAULTY_BATCH} came from a new supplier, {FAULTY_SUPPLIER}, "
        f"and are faulty.\n\n"
        f"Recommended actions: quarantine remaining stock from batch {FAULTY_BATCH}, pause shipments, replace "
        f"affected units, and return to {OLD_SUPPLIER} until {FAULTY_SUPPLIER} passes a full qualification.",
        month="2026-10", product_ids=["P-104"], doc_type="incident"))
    docs.append(_doc(
        meta, "quality_reports", "rca-2026-10", "Root cause analysis follow-up: batch B-2026-09B",
        f"Root cause analysis follow-up, October 2026.\n\nRetained samples from batch {FAULTY_BATCH} were put "
        f"through thermal-cycling tests and a majority failed, while samples from earlier batches passed. The "
        f"failures point to the heating elements from {FAULTY_SUPPLIER}. The Robo Vac R2 complaints are "
        f"unrelated to quality: they come from carrier delays.",
        month="2026-10", product_ids=["P-104", "P-107"], doc_type="rca"))

    # ---- finance
    for mi, month in enumerate(MONTHS):
        g = sum(rev[(month, p)][2] for p in pids)
        r = sum(rev[(month, p)][3] for p in pids)
        worst = max(pids, key=lambda p: rev[(month, p)][3])
        text = (f"Finance commentary for {MONTH_NAMES[mi]} 2026 ({month}).\n\n"
                f"Gross revenue was {_fmt_money(g)}, refunds were {_fmt_money(r)} ({100 * r / g:.1f}% of gross) and "
                f"net revenue was {_fmt_money(g - r)}. The largest refund contributor was {NAME[worst]} ({worst}).")
        if month == "2026-10":
            text += ("\n\nRefunds rose in October because of the increase in AeroBrew Pro (P-104) complaints, which "
                     "put pressure on gross margin. Finance recommends accruing replacement and refund costs for "
                     "the affected batch.")
        docs.append(_doc(meta, "finance_reports", month, f"Finance commentary {month}", text,
                         month=month, doc_type="commentary"))
    docs.append(_doc(
        meta, "finance_reports", "margin-analysis", "Margin analysis by product",
        "Margin analysis by product, 2026 year to date.\n\nKitchen products carry a gross margin of roughly 50%. "
        "Margin on AeroBrew Pro is the most sensitive to refunds because of its high unit price.",
        product_ids=["P-104"], doc_type="analysis"))

    # ---- legacy (deprecated decoy)
    docs.append(_doc(
        meta, "legacy_stats_notes", "overview", "Legacy complaint statistics overview",
        "Legacy complaint statistics (deprecated).\n\nThe legacy complaint stats report complaints per 1000 units "
        "and were last refreshed in June 2026. They use a different denominator from complaint_rate_pct and "
        "exclude the marketplace channel, so figures are not comparable.",
        doc_type="legacy"))
    docs.append(_doc(
        meta, "legacy_stats_notes", "methodology", "Legacy complaint statistics methodology",
        "Legacy complaint statistics methodology (deprecated).\n\nComplaints per 1000 units shipped, calculated "
        "quarterly from a manual export. Do not use for monthly complaint rate analysis.",
        doc_type="legacy"))
    return docs
