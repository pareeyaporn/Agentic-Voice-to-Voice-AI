# Project Proposal: Agentic Voice-to-Voice Shopping Assistant

**Course:** ADSP 32028 — Applied Generative AI: Agents & Multimodal Intelligence
**Team:** Ploy Prachaseree, Rob Scott, Kelly Sun, Hai Hong Yang — just the four of us, no separate lead (see [team_structure_and_task_breakdown.md](team_structure_and_task_breakdown.md) for who's doing what)

## The problem we want to solve

Shopping online today basically means typing something into a search box and scrolling through a wall of results. That's fine if you're sitting at a laptop with both hands free, but it's annoying — or flat-out impossible — if you're driving, cooking, or just don't want to type. And most "AI shopping assistant" demos we've seen have a bigger problem: they'll happily recommend a product, but you can't actually tell if it's a real item or something the model made up.

So we want to build something you can just *talk to*. Say what you're looking for, and it finds real products from an actual catalog, tells you about them out loud, and — this is the part we care about most — backs up every recommendation with a real, checkable source. Not "trust me," but "here's exactly the product this came from."

## What data we're using

We're using the **[Amazon Product Dataset 2020](https://www.kaggle.com/datasets/promptcloud/amazon-product-dataset-2020)** from Kaggle (CC0, so we're free to use it) — about 10,000 real Amazon product listings with titles, prices, categories, and description text. No personal data involved, just product info.

Rather than try to index the whole thing right away, we're going to pick one category to focus on for the demo — partly to keep things manageable, and partly because we expect the raw data to have some messy or missing fields we'll need to look at first. We'll nail down exactly which category once we've actually explored the data, and write up what we find.

## How we're planning to build it

- **The brain of it is a LangGraph pipeline**, broken into four steps: figure out what the user wants (and whether it's safe to answer), decide how to look it up, actually retrieve the info, and then write a grounded answer. We're breaking it into separate steps on purpose — it's a lot easier to test and debug "did the search step work?" than "did the one giant prompt work?"
- **For retrieval**, we're using a local vector database (Chroma) so search is fast and free, plus the option to check the live web for current prices if someone asks for that.
- **Every tool the system can use — catalog search and web search — goes through one shared MCP server.** That's partly a course requirement, but it also just makes sense: the orchestration logic doesn't need to know or care how a tool works under the hood, only that it can call it and get something back.
- **For voice**, we're doing speech-to-text on the way in and text-to-speech on the way out, both free/local where we can manage it. Nothing fancy or streaming yet — record the whole thing, then process it. Simple first, polish later.
- **The model itself is swappable** — we don't want to be locked into one AI provider if we can help it.
- **And for the UI**, we're starting with a basic Streamlit app with mock data built in from day one, so we (and anyone grading this) can click through the whole experience without needing API keys or spending real money.

## How we'll know if it's actually working

- We'll hand-build a small set of test queries and check how often the top results are actually relevant — there's no ready-made "correct answer" key for this dataset, so we have to make our own.
- Every citation the assistant gives gets double-checked in code against what was actually retrieved. If it can't be verified, we'd rather the system say "I'm not sure" than make something up.
- We'll measure real response times end-to-end, not just guess, and make sure nothing can hang forever if an API call goes wrong.

## Timeline

| Checkpoint | Week | What's due |
|---|---|---|
| Checkpoint 1 | 6 | Proposal, chosen data slice, first ingestion notebook |
| Checkpoint 2 | 8 | Architecture diagram, working UI, retrieval eval, MCP write-up |
| Final | 10 | Live demo (7 min or less), clean repo, presentation |

Full task-by-task breakdown is in [detailed_task_backlog.md](detailed_task_backlog.md) if you want more detail than this page gives you.
