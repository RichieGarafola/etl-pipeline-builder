"""
Generate a realistic "dirty" raw CSV for the ETL pipeline to clean.
Intentionally includes: mixed-case headers, duplicate rows, nulls,
inconsistent casing, currency strings, extra whitespace, bad dates.
Run once: python scripts/generate_sample_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
OUTPUT = Path(__file__).parent.parent / "data" / "sample" / "sample_raw.csv"

AGENCIES = [
    "Department of Defense", "VA Health", "DHS", "GSA", "Treasury",
    "OPM", "DOE", "USDA", "HHS", "NASA",
]
VENDORS = [
    "  Apex Federal Solutions  ", "Nexus Systems LLC", " TechBridge Inc",
    "ClearPath Consulting  ", "DataCore Federal", "  Orion Analytics",
    "Summit IT Group", "Meridian Services LLC", "BlueShield Tech", "Apex Federal Solutions  ",
]
CATEGORIES = ["IT Services", "Consulting", "Equipment", "Training", "Analytics", "Cloud"]
STATUSES   = ["active", "ACTIVE", "Active", "completed", "Completed", "COMPLETED",
               "pending", "Pending", "PENDING", "cancelled"]


def rand_date(start: date, end: date) -> str:
    """Randomly pick a date format to create inconsistency."""
    d = start + timedelta(days=random.randint(0, (end - start).days))
    fmt = random.choice(["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y"])
    return d.strftime(fmt)


def rand_value() -> str:
    """Mix of numeric strings, currency strings, and blanks."""
    choice = random.random()
    if choice < 0.10:
        return ""                              # missing
    v = random.randint(50_000, 5_000_000)
    if choice < 0.40:
        return f"${v:,}"                       # currency string
    if choice < 0.55:
        return str(v)                          # plain number
    return f"{v:,}"                            # comma-separated, no $


rows = []
for i in range(1, 81):
    start = date(2024, 1, 1) + timedelta(days=random.randint(0, 365))
    end   = start + timedelta(days=random.randint(90, 730))
    rows.append({
        "Contract ID":     f"W{random.randint(10,99)}QKN-{2024 + random.randint(0,1)}-C-{i:04d}",
        "Agency Name":     random.choice(AGENCIES) if random.random() > 0.08 else "",
        "Vendor":          random.choice(VENDORS),
        "Category":        random.choice(CATEGORIES),
        "Contract Value":  rand_value(),
        "Start Date":      rand_date(date(2024, 1, 1), date(2025, 6, 1)),
        "End Date":        rand_date(date(2025, 1, 1), date(2027, 12, 31)),
        "Status":          random.choice(STATUSES),
        "Award Year":      str(random.choice([2024, 2024, 2024, 2025])),
        "Notes":           random.choice(["", "", "", "Follow up needed", "High priority",
                                           "  See attached  ", "N/A", "TBD"]),
    })

# Inject ~10 exact duplicate rows
for _ in range(10):
    rows.append(random.choice(rows[:60]))

random.shuffle(rows)

# Messy header names (mixed case, spaces)
FIELDS = ["Contract ID", "Agency Name", "Vendor", "Category",
          "Contract Value", "Start Date", "End Date", "Status",
          "Award Year", "Notes"]

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows -> {OUTPUT}")
print(f"  ~10 duplicates injected | ~8% nulls in Agency Name | mixed date formats")
