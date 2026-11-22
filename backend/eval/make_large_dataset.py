"""Generates a reproducible synthetic dataset (default 50,000 rows) for scale testing.

    cd backend
    python eval/make_large_dataset.py            # writes ../sample_data/orders_50k.csv

Columns: order_id, order_date, region, city, category, product, quantity, unit_price, discount_pct,
total_amount, payment_method, customer_segment, delivery_days, rating, returned.
About 2% of delivery_days / rating and 1% of discount_pct are left empty on purpose (missing-value handling).
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CATALOG = {
    "Electronics": {"Laptop": (55000, 90000), "Smartphone": (15000, 70000), "Headphones": (1500, 12000), "Tablet": (12000, 45000), "Smartwatch": (3000, 25000)},
    "Furniture": {"Office Chair": (4000, 18000), "Desk": (6000, 25000), "Bookshelf": (3500, 14000), "Sofa": (15000, 60000)},
    "Clothing": {"Jacket": (1500, 6000), "Jeans": (900, 3500), "T-Shirt": (300, 1200), "Sneakers": (1500, 7000)},
    "Grocery": {"Rice (5kg)": (350, 800), "Cooking Oil": (180, 500), "Snacks Box": (120, 600), "Tea Pack": (150, 700)},
    "Sports": {"Cricket Bat": (900, 9000), "Football": (500, 3000), "Yoga Mat": (400, 2500), "Dumbbell Set": (1200, 8000)},
}
REGION_CITIES = {
    "North": ["Delhi", "Jaipur", "Chandigarh"], "South": ["Bengaluru", "Chennai", "Hyderabad"],
    "East": ["Kolkata", "Bhubaneswar", "Patna"], "West": ["Mumbai", "Pune", "Ahmedabad"],
}


def build(rows: int, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cat_names = list(CATALOG)
    category = rng.choice(cat_names, rows, p=[0.26, 0.14, 0.24, 0.22, 0.14])
    product = np.empty(rows, dtype=object)
    unit_price = np.zeros(rows)
    for c in cat_names:
        idx = np.where(category == c)[0]
        items = list(CATALOG[c])
        picks = rng.integers(0, len(items), len(idx))
        for j, item in enumerate(items):
            sel = idx[picks == j]
            product[sel] = item
            lo, hi = CATALOG[c][item]
            unit_price[sel] = np.round(rng.uniform(lo, hi, len(sel)), 0)
    region = rng.choice(list(REGION_CITIES), rows, p=[0.24, 0.30, 0.18, 0.28])
    city = np.array([rng.choice(REGION_CITIES[r]) for r in region]) if rows <= 5000 else np.empty(rows, dtype=object)
    if rows > 5000:
        for r, cities in REGION_CITIES.items():
            idx = np.where(region == r)[0]
            city[idx] = rng.choice(cities, len(idx))
    quantity = rng.choice([1, 2, 3, 4, 5, 6], rows, p=[0.45, 0.25, 0.15, 0.08, 0.05, 0.02])
    discount = rng.choice([0, 0, 0, 5, 10, 15, 20, 25], rows)
    total = np.round(quantity * unit_price * (1 - discount / 100), 0)
    payment = rng.choice(["UPI", "Credit Card", "Debit Card", "Cash", "Net Banking"], rows, p=[0.38, 0.24, 0.17, 0.12, 0.09])
    segment = rng.choice(["Regular", "Premium", "New", "Corporate"], rows, p=[0.5, 0.2, 0.2, 0.1])
    days = rng.integers(0, 1096, rows)
    order_date = pd.Timestamp("2023-01-01") + pd.to_timedelta(days, unit="D")
    delivery_days = np.clip(np.round(rng.normal(4.2, 1.8, rows) + (region == "East") * 1.2 + (region == "North") * 0.4), 1, 14)
    rating = np.clip(np.round(rng.normal(4.4, 0.7, rows) - 0.18 * (delivery_days - 4), 1), 1.0, 5.0)
    returned = rng.random(rows) < (0.05 + 0.02 * (category == "Clothing") + 0.03 * (rating < 3))

    df = pd.DataFrame({
        "order_id": np.arange(100001, 100001 + rows), "order_date": order_date.strftime("%Y-%m-%d"), "region": region, "city": city,
        "category": category, "product": product, "quantity": quantity, "unit_price": unit_price.astype(int), "discount_pct": discount,
        "total_amount": total.astype(int), "payment_method": payment, "customer_segment": segment,
        "delivery_days": delivery_days.astype(int), "rating": rating, "returned": returned,
    }).sort_values("order_date", kind="stable").reset_index(drop=True)
    df["order_id"] = np.arange(100001, 100001 + rows)
    # realistic gaps
    gap_rng = np.random.default_rng(seed + 1)
    for col, share in (("delivery_days", 0.02), ("rating", 0.02), ("discount_pct", 0.01)):
        df.loc[gap_rng.random(rows) < share, col] = np.nan
    df["delivery_days"] = df["delivery_days"].astype("Int64")
    df["discount_pct"] = df["discount_pct"].astype("Int64")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=50_000)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "sample_data" / "orders_50k.csv"))
    args = ap.parse_args()
    data = build(args.rows)
    data.to_csv(args.out, index=False)
    print(f"{len(data):,} rows x {data.shape[1]} columns -> {args.out}  ({Path(args.out).stat().st_size / 1e6:.1f} MB)")
    print("missing:", data.isna().sum()[lambda s: s > 0].to_dict())
