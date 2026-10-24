"""Day 1 check inside the OpenShell sandbox: get one reply from Nemotron.

The sandbox only sees a placeholder for the API key. OpenShell swaps in the
real key at the network boundary. Standard library only.
"""

import json
import os
import sys
import urllib.request

# Nebius Token Factory is the main provider; NVIDIA's free endpoint is the backup.
if os.environ.get("NEBIUS_API_KEY"):
    BASE, KEY = "https://api.tokenfactory.nebius.com/v1", os.environ["NEBIUS_API_KEY"]
    DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"
else:
    BASE, KEY = "https://integrate.api.nvidia.com/v1", os.environ.get("NVIDIA_API_KEY", "")
    # Free endpoint on build.nvidia.com; the Super/Ultra models 404 on free accounts.
    DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def call(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main() -> int:
    print(f"Key visible inside sandbox: {KEY[:12]}... (length {len(KEY)})")
    models = sorted(m["id"] for m in call("/models")["data"] if "nemotron" in m["id"].lower())
    print("Nemotron models:", *models, sep="\n  ")
    model = os.environ.get("MODEL", DEFAULT_MODEL)
    print(f"Endpoint: {BASE}")
    out = call("/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
        "max_tokens": 2000,
    })
    choice = out["choices"][0]
    print(f"\nModel: {model}\nReply: {choice['message']['content']!r}"
          f" (finish: {choice['finish_reason']}, tokens: {out['usage']['total_tokens']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
