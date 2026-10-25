"""Day 1 check inside an OpenShell sandbox: model APIs allowed, everything else denied.

Standard library only, so it runs in a bare sandbox image.
"""

import sys
import urllib.error
import urllib.request

CASES = [
    ("allow", "https://api.tokenfactory.nebius.com/v1/models"),
    ("deny", "https://webhook.site/"),
    ("deny", "https://example.com/"),
]


def reach(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return f"reachable (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        # 401/403 from the real API still means we got through the sandbox.
        if e.code in (401, 403) and "api." in url:
            return f"reachable (HTTP {e.code})"
        return f"BLOCKED (HTTP {e.code})"
    except Exception as e:
        return f"BLOCKED ({type(e).__name__}: {e})"


def main() -> int:
    ok = True
    for expect, url in CASES:
        result = reach(url)
        passed = result.startswith("reachable") == (expect == "allow")
        ok &= passed
        print(f"[{'ok' if passed else 'FAIL'}] expect {expect:5} {url}: {result}")
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
