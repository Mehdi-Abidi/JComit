import json
import os
import re
import urllib.request

TAVILY = "https://api.tavily.com"
_PREFIX = re.compile(r"^(?:SQ|TST|SP|PP|PAYPAL)\s*\*\s*", re.IGNORECASE)
_NOISE = {"LLC", "INC", "CO", "LTD", "CORP"}


def available() -> bool:
    return bool(os.environ.get("TAVILY_API_KEY"))


def shop_query(description: str) -> str | None:
    if "[" in description:
        return None
    d = _PREFIX.sub("", description.upper())
    d = re.split(r"[*#]", d)[0]
    words = [w for w in d.split() if not any(c.isdigit() for c in w) and w not in _NOISE]
    return " ".join(words) or None


def search(query: str, max_results: int = 3, timeout: float = 20) -> str:
    body = {
        "query": f"What kind of business is {query}?",
        "search_depth": "basic",
        "max_results": max_results,
        "include_answer": True,
    }
    req = urllib.request.Request(
        TAVILY + "/search",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ.get('TAVILY_API_KEY', '')}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        out = json.load(r)
    parts = [out.get("answer") or ""] + [x.get("content") or "" for x in out.get("results", [])]
    return " ".join(" ".join(p.split()) for p in parts if p)[:600]
