#!/usr/bin/env python3
"""
Data exploration for the Amazon Product Dataset 2020 (Kaggle, promptcloud/amazon-product-dataset-2020).

Covers task backlog §1.1 "Acquisition & Exploration":
  - field coverage / nulls per column
  - price distribution (Selling Price)
  - duplicate ASIN check
  - category distribution (to confirm the demo category slice)

Usage:
    python3 Code/data/explore_data.py

Reads the CSV directly (no parquet conversion — this project keeps data as CSV
throughout). Writes a per-column null-count summary to
Code/data/processed/column_coverage.csv and prints a full report to stdout.
"""

import os
import sys

import pandas as pd

# Path to the raw CSV, relative to the repo root (this script lives in Code/data/).
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CSV_PATH = os.path.join(
    REPO_ROOT,
    "Data",
    "sdf",
    "marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv",
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "processed")
COVERAGE_CSV = os.path.join(OUTPUT_DIR, "column_coverage.csv")

# Columns confirmed to be recommended demo-category candidates in the task backlog.
CANDIDATE_CATEGORIES = ["Home & Kitchen", "Sports & Outdoors", "Household", "Cleaning"]


def load_data(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        sys.exit(
            f"Could not find the dataset at:\n  {path}\n\n"
            "Download it first, e.g.:\n"
            "  import kagglehub\n"
            '  kagglehub.dataset_download("promptcloud/amazon-product-dataset-2020")\n'
            "and place the extracted CSV under Data/sdf/, or update CSV_PATH."
        )
    return pd.read_csv(path)


def report_shape(df: pd.DataFrame) -> None:
    print("=" * 70)
    print("SHAPE")
    print("=" * 70)
    print(f"Rows: {len(df):,}   Columns: {len(df.columns)}")
    print()


def report_field_coverage(df: pd.DataFrame) -> pd.DataFrame:
    print("=" * 70)
    print("FIELD COVERAGE (non-null %, per column)")
    print("=" * 70)
    total = len(df)
    coverage = pd.DataFrame(
        {
            "non_null_count": df.notna().sum(),
            "non_null_pct": (df.notna().sum() / total * 100).round(1),
            "empty_string_count": (df.astype(str).apply(lambda s: (s.str.strip() == "").sum())),
        }
    )
    coverage = coverage.sort_values("non_null_pct")
    with pd.option_context("display.max_rows", None, "display.width", 120):
        print(coverage)
    print()

    zero_coverage = coverage[coverage["non_null_pct"] == 0.0]
    if not zero_coverage.empty:
        print(f"⚠️  Columns with ZERO non-null values: {list(zero_coverage.index)}")
    print()
    return coverage


def report_price_distribution(df: pd.DataFrame) -> None:
    print("=" * 70)
    print("PRICE DISTRIBUTION")
    print("=" * 70)

    for col in ["List Price", "Selling Price"]:
        non_null = df[col].notna().sum()
        print(f"{col}: {non_null:,} / {len(df):,} non-null ({non_null / len(df):.1%})")

    def to_numeric_price(series: pd.Series) -> pd.Series:
        return pd.to_numeric(
            series.astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce"
        )

    selling = to_numeric_price(df["Selling Price"])
    print()
    print("Selling Price stats (parsed numeric):")
    print(selling.describe().round(2).to_string())
    print()


def report_duplicates(df: pd.DataFrame) -> None:
    print("=" * 70)
    print("DUPLICATE CHECK")
    print("=" * 70)
    def dup_count(col: str) -> str:
        non_null = df[col].dropna()
        if non_null.empty:
            return "n/a (column is entirely empty)"
        return f"{non_null.duplicated(keep=False).sum():,} (out of {len(non_null):,} non-null values)"

    print(f"Duplicate Asin values: {dup_count('Asin')}")
    print(f"Duplicate Uniq Id values: {dup_count('Uniq Id')}")
    print(f"Duplicate Product Name values: {dup_count('Product Name')}")
    print()


def report_categories(df: pd.DataFrame) -> None:
    print("=" * 70)
    print("CATEGORY DISTRIBUTION (top-level, from pipe-delimited Category field)")
    print("=" * 70)
    top_level = df["Category"].fillna("").str.split("|").str[0].str.strip()
    counts = top_level.value_counts()
    print(counts.head(15).to_string())
    print()

    print("Candidate demo-category row counts:")
    for cat in CANDIDATE_CATEGORIES:
        mask = df["Category"].fillna("").str.contains(cat, case=False)
        print(f"  '{cat}': {mask.sum():,} rows")
    print()


def main() -> None:
    df = load_data(CSV_PATH)

    report_shape(df)
    coverage = report_field_coverage(df)
    report_price_distribution(df)
    report_duplicates(df)
    report_categories(df)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    coverage.to_csv(COVERAGE_CSV)
    print(f"Wrote per-column coverage summary to: {os.path.relpath(COVERAGE_CSV, REPO_ROOT)}")


if __name__ == "__main__":
    main()
