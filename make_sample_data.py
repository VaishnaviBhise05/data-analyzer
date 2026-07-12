#!/usr/bin/env python3
"""Generates a synthetic sample_sales.csv so you can try the analyzer immediately."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
n = 500

regions = rng.choice(["North", "South", "East", "West"], size=n, p=[0.3, 0.25, 0.25, 0.2])
categories = rng.choice(["Electronics", "Furniture", "Clothing", "Groceries"], size=n)
dates = pd.date_range("2025-01-01", periods=365, freq="D")
order_date = rng.choice(dates, size=n)

base_price = rng.gamma(shape=2.5, scale=40, size=n)
quantity = rng.integers(1, 15, size=n)
discount = rng.choice([0, 0.05, 0.1, 0.15, 0.2], size=n, p=[0.4, 0.2, 0.2, 0.1, 0.1])
revenue = base_price * quantity * (1 - discount)
satisfaction = np.clip(rng.normal(4.0, 0.8, size=n), 1, 5).round(1)

df = pd.DataFrame({
    "order_id": np.arange(1001, 1001 + n),
    "order_date": order_date,
    "region": regions,
    "category": categories,
    "unit_price": base_price.round(2),
    "quantity": quantity,
    "discount": discount,
    "revenue": revenue.round(2),
    "customer_satisfaction": satisfaction,
})

# introduce some realistic messiness
missing_idx = rng.choice(df.index, size=25, replace=False)
df.loc[missing_idx, "customer_satisfaction"] = np.nan
df.loc[rng.choice(df.index, size=10, replace=False), "region"] = None

df.to_csv("sample_sales.csv", index=False)
print("Wrote sample_sales.csv with", len(df), "rows")
