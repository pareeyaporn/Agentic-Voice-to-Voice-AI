# Data Schema Decision & Licensing

Closes out the remaining §1.1 items in [detailed_task_backlog.md](detailed_task_backlog.md) — final working schema and licensing/usage constraints — based on [Code/data/explore_data.ipynb](../Code/data/explore_data.ipynb) run against the actual downloaded CSV.

## Licensing / usage constraints

- **Dataset:** [Amazon Product Dataset 2020](https://www.kaggle.com/datasets/promptcloud/amazon-product-dataset-2020), Kaggle, publisher `promptcloud`
- **License:** CC0 Public Domain (per the Kaggle listing) — free to use, modify, and redistribute, including in this repo
- **No PII**: data is product listings (title, price, category, description text), not personal/customer data
- **Attribution**: not legally required under CC0, but we credit PromptCloud/Kaggle in [Data/README.md](../Data/README.md) and the root [README.md](../README.md#data) for traceability
- Committing the raw CSV/zip into this repo is acceptable under the license and small enough (~24MB) not to be a repo-hygiene problem

## Final working schema

Ground truth from [Code/data/explore_data.ipynb](../Code/data/explore_data.ipynb) against the 10,002-row CSV (see full field-coverage table in [Code/data/processed/column_coverage.csv](../Code/data/processed/column_coverage.csv)):

### Columns that are entirely unusable (100% empty, all 10,002 rows)

`Product Description`, `Stock`, `Size Quantity Variant`, `Product Details`, `Dimensions`, `Color`, `Quantity`, `Ingredients`, `Asin`, `Brand Name`, `Direction To Use`, `List Price`, `Sku`

This is a bigger gap than initially scanned by hand — 13 of 28 columns are dead weight. Notably **`Asin` and `Sku` are both entirely empty**, which means there is **no reliable external key** to join in a second dataset (e.g. for ratings) by product identifier — any join would have to be fuzzy, on `Product Name`/title similarity, and should be treated as best-effort, not authoritative.

### Columns usable but partial

| Column | Coverage | Note |
|---|---|---|
| `Category` | 91.7% (830 rows blank) | usable, but expect ~8% of rows with no category to filter/route on |
| `About Product` | 97.3% | primary source for "features" |
| `Technical Details` | 92.1% | secondary feature text |
| `Shipping Weight` | 88.6% | useful for unit-normalization where present |
| `Product Specification` | 83.7% | secondary feature text |
| `Model Number` | 82.3% | not used in current schema |
| `Selling Price` | 98.9% raw non-null, but only 95.2% parse to a clean number | some values need cleanup (ranges, stray characters) before numeric use |
| `Product Name` | 100%, but 137 duplicate values | dedupe pass needed in preprocessing |

### Columns fully usable

`Uniq Id` (100%, zero duplicates — the real primary key), `Product Name`, `Product Url`, `Image`, `Is Amazon Seller`

### Resulting working schema (CSV, not parquet — this project keeps data as CSV end to end)

`products_clean.csv`:

| Field | Source column | Notes |
|---|---|---|
| `id` | `Uniq Id` | primary key |
| `title` | `Product Name` | dedupe near-identical titles |
| `category` | `Category` | parse pipe-delimited hierarchy; ~8% rows will be blank |
| `price` | `Selling Price` | parse to numeric; drop/flag rows that fail to parse (~4.8%) |
| `features` | `About Product` (fallback: `Technical Details`, `Product Specification`) | embedding text source |
| `brand` | *(derived)* | parsed from `Product Name`/`About Product` text — not a source column, since `Brand Name` is 100% empty |
| `rating` | — | **not available**; omit unless a second dataset is joined in (fuzzy, by title — see above) |
| `ingredients` | — | **not available**; omit |

No `reviews.csv` — there is no review-level data in this dataset at all.

### Recommended demo category slice

**`Home & Kitchen`** — 708–712 rows depending on match method (top-level split vs. substring match), the largest well-formed slice after `Toys & Games` (which dominates at 67% of the dataset but is a worse fit for the assignment's "eco-friendly cleaner" style example queries). `Household`/`Cleaning` combined is only ~25 rows — confirmed too sparse to use, as flagged earlier.
