"""
Shared config for the graph package (§2.1-2.6, extracted from
"2.1-2.6 graph and nodes.ipynb" once §2.7's testing notebook needed a real,
importable graph -- see that notebook's file-format note for why).

Uses __file__-based path resolution, not the notebook's os.getcwd() trick --
a .py module can be imported from any working directory, unlike a notebook
launched from its own folder.
"""

import os

from dotenv import load_dotenv

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))

load_dotenv(os.path.join(REPO_ROOT, ".env"))

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
LLM_MODEL = os.environ.get("LLM_MODEL", "")

PROMPTS_DIR = os.path.join(REPO_ROOT, "Code", "6. Prompts & Documentation")

_has_key = bool(os.environ.get("OPENAI_API_KEY"))  # presence only -- never read/printed
assert _has_key, "OPENAI_API_KEY missing -- copy .env.example to .env and fill it in"
assert LLM_MODEL, "LLM_MODEL missing in .env"
