# Related Work

Brief survey of the ideas this project builds on (Checkpoint 1 deliverable), not an exhaustive literature review.

- **Retrieval-Augmented Generation:** Lewis et al., ["RAG for Knowledge-Intensive NLP Tasks"](https://arxiv.org/abs/2005.11401) (NeurIPS 2020). Grounds LLM output in retrieved documents rather than parametric memory alone; the basis for this project's Retriever/Answerer split and citation-checking.
- **Reasoning + acting agents:** Yao et al., ["ReAct"](https://arxiv.org/abs/2210.03629) (2022). Interleaves reasoning with tool calls; the Planner's real tool-calling decision (call `web_search` or not) is a narrow instance of this pattern.
- **Model Context Protocol:** Anthropic's [MCP](https://modelcontextprotocol.io) (2024) standardizes tool discovery/access across LLM clients. This project's MCP server (`rag.search`, `web.search`) is a direct, small-scale application of it.
- **Voice commerce (industry):** Amazon Alexa Shopping and Google Assistant's shopping actions show voice-driven product search at scale, but are proprietary and don't expose *why* a recommendation was made. This project targets the same interaction pattern at a much smaller scale, with every recommendation traceable to a specific retrieved product.

**Where this differs:** combines RAG's grounding discipline, ReAct-style tool-calling, and MCP's standardized interface, prioritizing citation-checkable answers over broad feature coverage.
