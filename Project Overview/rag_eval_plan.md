# RAG Evaluation Plan & Results

Covers task backlog §1.5. Full implementation: [Code/data/1.5 rag evaluation.ipynb](../Code/data/1.5%20rag%20evaluation.ipynb) — evaluates [1.4 hybrid retrieval.ipynb](../Code/data/1.4%20hybrid%20retrieval.ipynb)'s `search()`, self-contained, pre-executed.

## Methodology

- **14 queries**: 10 plain `Home & Kitchen` queries, 2 with filters (`budget_max`, `brand`), 2 against the full `products_all` catalog.
- **Metrics**: precision@5 and recall@5, standard IR metrics, k=5 to match the top-5 shown elsewhere in this project.
- **Ground truth — a real limitation, not gold-standard labels**: there is no human-labeled relevance data for this dataset. "Relevant" is approximated by a **keyword/substring match on `title`** (case-insensitive). This is cheap and reproducible, but imperfect in both directions — confirmed empirically below, not just theoretically:
  - **False negatives** (misses genuinely relevant items that use different wording): e.g. for `"birthday party decorations"` (keyword `"party"`), the retrieved *"Happy Anniversary Gold - Large Foil Letter Banner"* is obviously a party decoration but doesn't contain the literal word "party," so it's counted as a miss even though it's a correct result.
  - **False positives** (counts tangentially-matching items as relevant): for `"board game for family night"` (keyword `"board game"`), the 94-item ground truth set includes things like a *board-game-themed T-shirt* and a *dice bag*, not games themselves — inflating the denominator with items that aren't real matches.

## Results

| Query | precision@5 | recall@5 | relevant (total) |
|---|---|---|---|
| insulated lunch box for kids | 1.00 | 0.56 | 9 |
| kids bedding set | 1.00 | 0.09 | 58 |
| toy storage organizer | 1.00 | 0.23 | 22 |
| birthday party decorations | 0.80 | 0.07 | 61 |
| kids table and chairs | 1.00 | 0.12 | 41 |
| paper plates | 0.80 | 0.67 | 6 |
| area rug for kids room | 1.00 | 0.15 | 33 |
| duvet cover set | 0.80 | 0.33 | 12 |
| party balloons | 1.00 | 0.38 | 13 |
| step stool | 1.00 | 0.21 | 24 |
| lunch box under $15 (`budget_max`) | 1.00 | 0.63 | 8 |
| insulated lunch box (`brand="Wildkin"`) | 0.80 | 1.00 | 4 |
| dinosaur toy (`products_all`) | 0.80 | 0.09 | 44 |
| board game for family night (`products_all`) | 0.60 | 0.03 | 94 |

**Mean precision@5: 0.90. Mean recall@5: 0.32.**

## Reading recall@5 correctly — the mean alone is misleading

Recall@5 is mechanically capped by `5 / relevant_total`. A query with 94 relevant items (`"board game for family night"`) cannot score above 0.053 recall@5 even with a perfect top-5 — its 0.03 is close to that ceiling, not a sign of poor retrieval. A query with only 6 relevant items (`"paper plates"`) can reach 0.67 with just 4 correct hits. **Comparing recall@5 across queries with very different ground-truth-set sizes is not meaningful** — the 0.32 mean is dominated by this structural effect, not by retrieval quality. Precision@5 is the more informative number here, and it's strong (0.90 mean, every query at 0.6 or above).

## Takeaways

- Retrieval quality is genuinely good: 12 of 14 queries hit 0.8+ precision@5, all real vector search against the real index (no query in this eval set was cherry-picked for a good result — see [1.4](../Code/data/1.4%20hybrid%20retrieval.ipynb)'s own separate sanity checks for further confirmation).
- The two lowest-precision queries (`"board game for family night"` at 0.60, `"dinosaur toy"` at 0.80) are both against the broader `products_all` catalog, not `products_home_kitchen` — consistent with that collection covering far more diverse content (per §1.3's category-mix findings), giving vector search more room to surface adjacent-but-not-quite matches.
- Filters work as designed: the `budget_max=15` query correctly narrowed the relevant set and still hit 1.00 precision; the `brand="Wildkin"` query hit 1.00 recall (all 4 ground-truth Wildkin lunch boxes retrieved) confirming the substring-based brand post-filter from §1.4 works despite `brand` being a low-confidence field.
- No reranker was needed to reach these numbers (confirms the §1.4 decision to skip it for now) — revisit only if a future eval set shows a specific, real gap this doesn't cover.
