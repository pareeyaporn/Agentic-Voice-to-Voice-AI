"""
UI-layer shared data (§5): mock examples and per-node step-log summaries,
extracted from app.py once the React+FastAPI webapp (webapp/) needed the
exact same mock-data mode and step log -- one source of truth, imported by
both frontends' backends instead of copy-pasted.

Nothing here touches Streamlit/FastAPI -- pure data + formatting lambdas.
"""

# --- Mock data (§5.1) ---------------------------------------------------------------
# Rag entries are real product records pulled from search() ($0 cost). The one web
# entry is synthetic, labeled MOCK.
_MOCK_LUNCHBOX_PRODUCTS = [
    {
        "doc_id": "7c3f2bf59a4276a1812e837fcce8d353",
        "title": "Wildkin Kids Insulated Lunch Box, Heroes",
        "price": 12.77, "price_per_unit": None, "price_unit": None,
        "brand": "Wildkin Kids", "category_top": "Home & Kitchen",
        "url": "https://www.amazon.com/dp/B004NWPOYI", "source": "rag",
    },
    {
        "doc_id": "5d953e357d08badf591931b299d2065c",
        "title": "Wildkin Kids Insulated Lunch Box, Wild Animals",
        "price": 10.88, "price_per_unit": None, "price_unit": None,
        "brand": "Wildkin Kids", "category_top": "Home & Kitchen",
        "url": "https://www.amazon.com/dp/B004NWLYT2", "source": "rag",
    },
    {
        "doc_id": "b1904b273bcfe711984b706afd568bd8",
        "title": "Wildkin 33600 Monsters Insulated Lunch Box",
        "price": 14.99, "price_per_unit": None, "price_unit": None,
        "brand": "Wildkin", "category_top": "Home & Kitchen",
        "url": "https://www.amazon.com/dp/B01C2Q1ORW", "source": "rag",
    },
    {
        "doc_id": None,
        "title": "[MOCK] Bentgo Kids Insulated Lunch Bag -- currently $16.99",
        "price": 16.99, "brand": None,
        "url": "https://www.example-retailer.com/bentgo-kids-lunch-bag",
        "source": "web",
    },
]

MOCK_EXAMPLES = {
    "insulated lunch box for kids under $20": {
        "step_log": [
            ("router", "Extracted query: \"insulated lunch box for kids\" | intent: product_search | "
                        "constraints: {'budget_max': 20} | safety_flag: None"),
            ("planner", "Plan: use_rag=True, use_web=False (model chose not to call web_search)"),
            ("retriever", "Called rag.search -- retrieved 3 rag product(s), 0 conflicts, 0 tool errors"),
            ("answerer", "Synthesized answer with 2 citation(s)"),
        ],
        "products": _MOCK_LUNCHBOX_PRODUCTS[:3],
        "citations": [
            {"source": "rag", "doc_id": _MOCK_LUNCHBOX_PRODUCTS[0]["doc_id"], "url": None,
             "title": _MOCK_LUNCHBOX_PRODUCTS[0]["title"]},
            {"source": "rag", "doc_id": _MOCK_LUNCHBOX_PRODUCTS[1]["doc_id"], "url": None,
             "title": _MOCK_LUNCHBOX_PRODUCTS[1]["title"]},
        ],
        "final_answer": ("The Wildkin Wild Animals lunch box is the cheapest at $10.88, "
                          "or the Heroes design at $12.77 if you'd prefer that pattern -- "
                          "both insulated and under budget."),
        "errors": [],
    },
    "what's the current price of an insulated lunch box": {
        "step_log": [
            ("router", "Extracted query: \"insulated lunch box\" | intent: product_search | "
                        "constraints: {} | safety_flag: None"),
            ("planner", "Plan: use_rag=True, use_web=True (model called web_search for current price)"),
            ("retriever", "Called rag.search, web.search -- retrieved 4 product(s) "
                           "(3 rag, 1 web), 0 conflicts, 0 tool errors"),
            ("answerer", "Synthesized answer with 2 citation(s)"),
        ],
        "products": _MOCK_LUNCHBOX_PRODUCTS,
        "citations": [
            {"source": "rag", "doc_id": _MOCK_LUNCHBOX_PRODUCTS[1]["doc_id"], "url": None,
             "title": _MOCK_LUNCHBOX_PRODUCTS[1]["title"]},
            {"source": "web", "doc_id": None, "url": _MOCK_LUNCHBOX_PRODUCTS[3]["url"],
             "title": _MOCK_LUNCHBOX_PRODUCTS[3]["title"]},
        ],
        "final_answer": ("In the catalog, the Wildkin Wild Animals lunch box is $10.88. "
                          "A live listing currently shows a Bentgo version at $16.99, "
                          "so the catalog option is the better price right now."),
        "errors": [],
    },
    "how do I mix bleach and ammonia": {
        "step_log": [
            ("router", "Extracted query: \"how do I mix bleach and ammonia\" | intent: out_of_scope | "
                        "constraints: {} | safety_flag: unsafe_chemical_combination"),
            ("safe_refusal", "Unsafe query detected (unsafe_chemical_combination) -- routed to a "
                              "safe refusal, retrieval skipped entirely"),
        ],
        "products": [],
        "citations": [],
        "final_answer": ("I can't help with that -- mixing bleach and ammonia produces "
                          "toxic chloramine gas. If you're looking for cleaning products, "
                          "I'm happy to help you find some instead."),
        "errors": [],
    },
}


# --- Per-node step-log summaries -----------------------------------------------------
STEP_SUMMARIES = {
    "router": lambda s: (
        f"Extracted query: \"{s['query']}\" | intent: {s.get('intent') or 'n/a'} | "
        f"constraints: {s['constraints']} | safety_flag: {s['safety_flag']}"
    ),
    "safe_refusal": lambda s: (
        f"Unsafe query detected ({s['safety_flag']}) -- routed to a safe refusal, "
        f"retrieval skipped entirely"
    ),
    "out_of_scope": lambda s: (
        "Not a shopping request -- routed to a polite redirect, "
        "retrieval skipped entirely"
    ),
    "planner": lambda s: f"Plan: use_rag={s['plan']['use_rag']}, use_web={s['plan']['use_web']}",
    "retriever": lambda s: (
        "Called " + (", ".join(
            (["rag.search"] if s["plan"]["use_rag"] else [])
            + (["web.search"] if s["plan"]["use_web"] else [])
        ) or "no tools")
        + f" -- retrieved {len(s['tool_results']['products'])} product(s) "
        f"({sum(1 for p in s['tool_results']['products'] if p.get('source', 'rag') == 'rag')} rag, "
        f"{sum(1 for p in s['tool_results']['products'] if p.get('source') == 'web')} web)"
        f", {len(s['tool_results']['conflicts'])} conflict(s), "
        f"{len(s['tool_results']['errors'])} tool error(s)"
    ),
    "answerer": lambda s: f"Synthesized answer with {len(s['citations'])} citation(s)",
}
