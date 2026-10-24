"""Day 1 check: the sandbox reaches Token Factory and nothing else."""

import socket
import sys

import httpx

ALLOWED = "https://api.tokenfactory.nebius.com/v1/models"
BLOCKED = ["https://webhook.site/", "https://example.com/"]


def try_proxy(url: str) -> str:
    try:
        r = httpx.get(url, timeout=15)
        return f"reachable (HTTP {r.status_code})"
    except httpx.HTTPError as e:
        return f"BLOCKED ({type(e).__name__}: {e})"


def try_direct(host: str) -> str:
    # Bypass the proxy entirely, the way a misbehaving agent might.
    try:
        socket.create_connection((host, 443), timeout=5).close()
        return "reachable"
    except OSError as e:
        return f"BLOCKED ({e})"


def main() -> int:
    ok = True
    result = try_proxy(ALLOWED)
    print(f"[allow-listed] {ALLOWED}: {result}")
    ok &= result.startswith("reachable")

    for url in BLOCKED:
        result = try_proxy(url)
        print(f"[not listed]   {url}: {result}")
        ok &= result.startswith("BLOCKED")

    result = try_direct("webhook.site")
    print(f"[no proxy]     webhook.site:443 direct: {result}")
    ok &= result.startswith("BLOCKED")

    print("\nPASS: only Token Factory is reachable." if ok else "\nFAIL: egress policy is not holding.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
