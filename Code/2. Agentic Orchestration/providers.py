"""
LLM provider abstraction + central prompt/logging wrapper (§2.6).

get_chat_model() branches on LLM_PROVIDER (openai/anthropic/google/bedrock)
instead of hardcoding one provider's class, per the brief's Model-Agnostic
Requirement. Only the openai path is exercised; the others share the same
interface but are untested.

invoke_and_log() is the only path any node uses to call an LLM, capturing
system prompt + input + output into LLM_CALL_LOG (Prompt Disclosure).

§4.3: every openai call gets a real, bounded timeout. The openai SDK's own
default is 600s (confirmed: `openai._base_client.DEFAULT_TIMEOUT`) -- a hung
call would leave the UI's spinner running for up to 10 minutes with no
escape. REQUEST_TIMEOUT_SECONDS tightens that to something a live demo can
actually recover from.
"""

from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

LLM_CALL_LOG: List[Dict[str, Any]] = []
REQUEST_TIMEOUT_SECONDS = 30


def get_chat_model(provider: str, model: str, **kwargs):
    """Each branch imports its package lazily -- only the actually-selected
    provider's package needs to be installed."""
    provider = (provider or "").lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        # use_responses_api=True: found by testing, not assumed -- the pinned
        # reasoning model (gpt-5.6-luna) rejects function/tool-calling on the
        # older /v1/chat/completions surface ("Function tools with
        # reasoning_effort are not supported... use /v1/responses"). Routing
        # through /v1/responses instead is what makes method="function_calling"
        # (router.py/answerer.py) actually work with this model.
        kwargs.setdefault("use_responses_api", True)
        kwargs.setdefault("request_timeout", REQUEST_TIMEOUT_SECONDS)
        kwargs.setdefault("max_retries", 1)  # 1 retry, not the SDK's default 2 -- fail fast for a live demo
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
