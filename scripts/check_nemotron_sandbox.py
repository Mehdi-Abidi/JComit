"""Day 1 check inside the OpenShell sandbox: get one reply from Nemotron.

The sandbox only sees a placeholder for the API key. OpenShell swaps in the
real key at the network boundary. Standard library only.
"""

import json
import os
import sys
import urllib.request

BASE = os.environ.get("MODEL_BASE_URL", "https://integrate.api.nvidia.com/v1")
KEY = os.environ.get("NVIDIA_API_KEY", "")


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
    model = os.environ.get("MODEL") or next((m for m in models if "super" in m), models[0])
    out = call("/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
        "max_tokens": 300,
    })
    print(f"\nModel: {model}\nReply: {out['choices'][0]['message']['content']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
