"""Day 1 check: list Nemotron models on Token Factory and get one reply."""

import os
import sys

from jcomit import llm


def main() -> int:
    c = llm.client()
    nemotron = sorted(m.id for m in c.models.list().data if "nemotron" in m.id.lower())
    print("Nemotron models on Token Factory:")
    for name in nemotron:
        print("  ", name)

    if not os.environ.get("NEBIUS_MODEL"):
        print("\nSet NEBIUS_MODEL in .env to one of the names above, then run this again.")
        return 1

    reply = llm.chat("Say hello in one short sentence.", max_tokens=200)
    print(f"\nModel: {llm.model()}\nReply: {reply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
