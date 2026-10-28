"""Nemotron client for Nebius Token Factory (OpenAI-compatible API).

Standard library only, so it runs inside the OpenShell sandbox, where pip is
blocked by policy. Inside the sandbox the API key is a placeholder; OpenShell
swaps in the real key at the network boundary.
"""

import json
import os
import urllib.request

TOKEN_FACTORY = "https://api.tokenfactory.nebius.com/v1"
NVIDIA_BUILD = "https://integrate.api.nvidia.com/v1"


def _endpoint() -> tuple[str, str, str]:
    """(base_url, api_key, model). Token Factory first; NVIDIA's free endpoint is the backup."""
    if os.environ.get("NEBIUS_API_KEY"):
        return (
            os.environ.get("NEBIUS_BASE_URL", TOKEN_FACTORY).rstrip("/"),
            os.environ["NEBIUS_API_KEY"],
            os.environ.get("NEBIUS_MODEL") or "nvidia/nemotron-3-super-120b-a12b",
        )
    if os.environ.get("NVIDIA_API_KEY"):
        return (
            NVIDIA_BUILD,
            os.environ["NVIDIA_API_KEY"],
            os.environ.get("NVIDIA_MODEL") or "nvidia/nemotron-3.5-lightning-30b-a3b",
        )
    raise RuntimeError("Set NEBIUS_API_KEY (or NVIDIA_API_KEY as a backup).")


def _request(path: str, body: dict | None = None, timeout: float = 120) -> dict:
    base, key, _ = _endpoint()
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def model() -> str:
    return _endpoint()[2]


def models() -> list[str]:
    return sorted(m["id"] for m in _request("/models")["data"])


def complete(prompt: str, system: str | None = None, max_tokens: int = 4000,
             temperature: float = 0.0) -> tuple[str, dict]:
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    out = _request("/chat/completions", {
        "model": model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    })
    return (out["choices"][0]["message"]["content"] or "").strip(), out.get("usage") or {}


def chat(prompt: str, system: str | None = None, max_tokens: int = 4000, temperature: float = 0.0) -> str:
    """One chat completion. Nemotron reasons before answering, so leave room in max_tokens."""
    return complete(prompt, system, max_tokens, temperature)[0]
