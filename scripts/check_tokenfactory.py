"""Day 1 check: list Nemotron models on Token Factory and get one reply."""

import sys

from jcomit import llm


def main() -> int:
    print("Nemotron models:")
    for name in llm.models():
        if "nemotron" in name.lower():
            print("  ", name)
    reply = llm.chat("Say hello in one short sentence.")
    print(f"\nModel: {llm.model()}\nReply: {reply}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
