"""Nemotron client on Nebius Token Factory (OpenAI-compatible API)."""

import os

from openai import OpenAI

BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")


def client() -> OpenAI:
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set. Copy .env.example to .env and add your key.")
    return OpenAI(base_url=BASE_URL, api_key=key)


def model() -> str:
    name = os.environ.get("NEBIUS_MODEL")
    if not name:
        raise RuntimeError("NEBIUS_MODEL is not set. Run scripts/check_tokenfactory.py to list Nemotron models.")
    return name


def chat(prompt: str, system: str | None = None, **kwargs) -> str:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    resp = client().chat.completions.create(model=model(), messages=messages, **kwargs)
    return resp.choices[0].message.content
