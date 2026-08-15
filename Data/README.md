# Data

Raw data downloaded from Kaggle for the Agentic Voice-to-Voice AI project.

## Source

- **Dataset:** [Amazon Product Dataset 2020](https://www.kaggle.com/datasets/promptcloud/amazon-product-dataset-2020) — Kaggle, `promptcloud/amazon-product-dataset-2020`
- **License:** CC0 Public Domain
- **Downloaded:** 2026-08-15

## How it was downloaded

```python
import kagglehub

# Download latest version
path = kagglehub.dataset_download("promptcloud/amazon-product-dataset-2020")

print("Path to dataset files:", path)
```

Requires `pip install kagglehub`. No Kaggle API credentials were needed — this is a public dataset and downloaded anonymously.

## Contents

```
Data/
├── amazon_kaggle_data.zip   # raw download as returned by the Kaggle API
├── README.md                # this file
└── sdf/
    └── marketing_sample_for_amazon_com-ecommerce__20200101_20200131__10k_data.csv
```

The CSV is the extracted contents of the zip (kept alongside it for convenience — no need to unzip to inspect or load the data).

## Schema

**10,002 rows × 28 columns.** Header:

```
Uniq Id, Product Name, Brand Name, Asin, Category, Upc Ean Code, List Price, Selling Price,
Quantity, Model Number, About Product, Product Specification, Technical Details,
Shipping Weight, Product Dimensions, Image, Variants, Sku, Product Url, Stock,
Product Details, Dimensions, Color, Ingredients, Direction To Use, Is Amazon Seller,
Size Quantity Variant, Product Description
```

## Known gaps (verified by direct inspection, not just the Kaggle listing)

- **`Brand Name` and `Ingredients` are empty in 100% of rows.** Don't build filters or citations that assume these are populated — brand needs to be parsed out of `Product Name`/`About Product` instead.
- **No rating/stars column exists anywhere in this file**, and there is no review-level data (no reviews table). If the assistant needs to cite a rating, it has to come from a second, separately-joined dataset (e.g. by ASIN).
- **`List Price` is mostly blank** — use `Selling Price` as the price field.
- **Category is heavily skewed:** ~67% `Toys & Games`; `Home & Kitchen` (708 rows) and `Sports & Outdoors` (540 rows) are the next largest slices. `Household`/`Cleaning` categories total only ~25 rows combined — too sparse to use as the demo category (see [README.md](../README.md#data) and [detailed_task_backlog.md](../Project%20Overview/detailed_task_backlog.md) for how this changes the planned demo slice).

See the root [README.md](../README.md#data) for the full field-mapping table (assignment schema → actual column) and downstream implications for retrieval/UI design.
