# JComit

A private personal-finance agent. It reads bank statements and receipts on your own machine, redacts personal details, and only then asks NVIDIA Nemotron (served by Nebius Token Factory) for help. It runs inside a sandbox that can reach Token Factory and nothing else.

Built for the Nebius x NVIDIA Global AI Hackathon 2026, Personal AI track.

> Work in progress. All data in this repo is synthetic.

## How the sandbox works

```
 ┌──────────── sandbox network (internal, no internet) ────────────┐
 │                                                                 │
 │   jcomit-app  ──HTTPS_PROXY──►  jcomit-egress (tinyproxy)       │
 │                                    │  default deny               │
 └────────────────────────────────────┼────────────────────────────┘
                                      ▼
                      api.tokenfactory.nebius.com  (only allowed host)
```

- The app container has no route to the internet. Even code that ignores the proxy cannot get out.
- The egress proxy allows only the hosts in [egress/allowlist.txt](egress/allowlist.txt). Everything else is refused.
- Every allowed and refused request is written to `logs/egress.log`.

## Setup

Requirements: Docker Desktop.

```bash
cp .env.example .env          # add NEBIUS_API_KEY
docker compose up -d --build

# 1. List Nemotron models, then set NEBIUS_MODEL in .env
docker compose exec app python scripts/check_tokenfactory.py
docker compose up -d          # reload .env
docker compose exec app python scripts/check_tokenfactory.py

# 2. Prove the sandbox only reaches Token Factory
docker compose exec app python scripts/check_egress.py
```

## License

MIT, see [LICENSE](LICENSE).
