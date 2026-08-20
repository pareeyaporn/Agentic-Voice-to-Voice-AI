"""
Shared config for the graph package (§2.1-2.6), extracted from
"2.1-2.6 graph and nodes.ipynb" once §2.7 needed a real importable graph.

Uses __file__-based path resolution, not the notebook's os.getcwd() trick --
a .py module can be imported from any working directory.
"""

import os

from dotenv import load_dotenv

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))

load_dotenv(os.path.join(REPO_ROOT, ".env"))

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
LLM_MODEL = os.environ.get("LLM_MODEL", "")

PROMPTS_DIR = os.path.join(REPO_ROOT, "Code", "6. Prompts & Documentation")

def require_llm_config() -> None:
    """Validates the LLM env vars at first real use, not at import -- app.py
    imports this module unconditionally, and mock-data mode (§5.1) must work
    with no .env at all. Nodes call this lazily before building their LLM."""
    _has_key = bool(os.environ.get("OPENAI_API_KEY"))  # presence only -- never read/printed
    if LLM_PROVIDER == "openai" and not _has_key:
        raise RuntimeError("OPENAI_API_KEY missing -- copy .env.example to .env and fill it in")
    if not LLM_MODEL:
        raise RuntimeError("LLM_MODEL missing in .env")
