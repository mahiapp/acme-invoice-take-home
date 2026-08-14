# Shared helpers used across agents and the pipeline.
import json
import os
import re

from dotenv import load_dotenv
from langchain_xai import ChatXAI


def get_api_key():
    '''Return XAI_API_KEY from the environment, or raise if it is missing.'''
    load_dotenv()
    key = os.getenv("XAI_API_KEY")
    if not key:
        raise ValueError(
            "Missing XAI_API_KEY. Copy .env.example to .env and add your key."
        )
    return key


def get_llm():
    '''Create the shared Grok chat model used by all agents.'''
    return ChatXAI(model="grok-4.5", api_key=get_api_key())


def parse_llm_json(text):
    '''Parse JSON from an LLM response, stripping markdown fences if present.'''
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model returned invalid JSON: {e}") from e


def is_approved(decision):
    '''Return True if an approval decision means pay the invoice.'''
    return str(decision or "").lower() in ("approve", "approved")
