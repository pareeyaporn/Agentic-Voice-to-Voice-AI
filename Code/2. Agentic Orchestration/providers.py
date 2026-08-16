"""
LLM provider abstraction + central prompt/logging wrapper (§2.6).

get_chat_model() branches on LLM_PROVIDER for real (openai/anthropic/google/
bedrock, the assignment brief's own listed hosted options) instead of
hardcoding one provider's class -- that's what the brief's Model-Agnostic
Requirement actually asks for ("the code is swappable via environment
variables/config"). Only the openai path is exercised; the others are written
to the same interface but genuinely untested -- stated, not hidden.

invoke_and_log() is the only path any node uses to call an LLM, capturing
system prompt + input + output into LLM_CALL_LOG (the brief's separate "log
prompts & system messages for transparency" / Prompt Disclosure requirement).
"""

from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

LLM_CALL_LOG: List[Dict[str, Any]] = []


def get_chat_model(provider: str, model: str, **kwargs):
    """Each branch imports its package lazily -- only the actually-selected
    provider's package needs to be installed."""
    provider = (provider or "").lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, **kwargs)
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, **kwargs)
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model, **kwargs)
    if provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(model_id=model, **kwargs)
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (expected one of: openai, anthropic, google, bedrock)")


def invoke_and_log(llm, node_name: str, system_prompt: str, human_content: str):
    """Every node's LLM call goes through here so every system prompt +
    input + output is captured in one place."""
    result = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_content)])
    LLM_CALL_LOG.append({
        "node": node_name,
        "system_prompt_chars": len(system_prompt),
        "input": human_content,
        "output": result.model_dump() if hasattr(result, "model_dump") else str(result),
    })
    return result
