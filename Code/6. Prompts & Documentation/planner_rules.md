# Planner Rules

**Used by:** Planner node — [Code/2. Agentic Orchestration/2.1-2.6 graph and nodes.ipynb](../2.%20Agentic%20Orchestration/2.1-2.6%20graph%20and%20nodes.ipynb) (`planner_node`)
**Maps to backlog:** §2.3 (this file doubles as the CP2 "planner rules" deliverable)

**Not an LLM system prompt.** Unlike the Router (§2.2), the Planner is implemented as a
deterministic rule, not an LLM call — the decision it makes is a single binary
(`use_web: bool`), the backlog's own framing of the rule is already keyword-based
("skip web.search unless query implies current/latest/now"), and an extra LLM call for
a decision this narrow isn't worth the added cost/latency. If real usage shows the
keyword rule misfiring often, revisit as an LLM call then — not preemptively.

## Source selection rule

- `plan.use_rag` is **always `True`** — every query gets a private-catalog lookup.
- `plan.use_web` is `True` only if the (Router-normalized) query contains a live
  price/availability signal word: `current`, `latest`, `now`, `today`, `right now`,
  `currently`, `in stock`, `available`, `still available`, `on sale`. Case-insensitive
  substring match. Otherwise `False`.

## Fields to retrieve & comparison criteria

Treated as a **static policy**, not a per-query decision — the catalog's available
fields don't change query to query, so there's nothing for the Planner to actually
decide here per call:

- **Compare on:** price (incl. price-per-unit where available, §1.4), parsed `brand`
  (low-confidence field, §1.2 — treat as a soft signal not a hard filter), title/feature
  match to the stated query
- **Do not compare on:** rating, ingredients — no rating column exists in this dataset
  at all (§1.1), and no ratings/reviews source has been backfilled. Comparing on these
  would mean fabricating values; the Answerer (§2.5) must not do that.
