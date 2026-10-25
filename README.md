# JComit

A private personal-finance agent. It reads bank statements and receipts on your own machine, redacts personal details, and only then asks NVIDIA Nemotron (served by Nebius Token Factory) for help. It runs inside a sandbox that can reach Token Factory and nothing else.

Built for the Nebius x NVIDIA Global AI Hackathon 2026, Personal AI track.

> Work in progress. All data in this repo is synthetic.

## Use it

```bash
python -m pytest                                              # unit tests, no network
PYTHONPATH=src python -m jcomit.cli categorize data/statement.csv --show-sent
PYTHONPATH=src python -m jcomit.cli correct "SQ *BLUE DOOR LLC" Dining
PYTHONPATH=src python -m jcomit.cli memory                     # corrections survive restarts
```

Categories come from the user's saved corrections first, then simple rules, then Nemotron 3 Super on Nebius Token Factory for the merchants the rules don't know. Only redacted text reaches the model, and a guard refuses any payload that still contains the account holder's name, account number or card number. How the modules fit together: [docs/interfaces.md](docs/interfaces.md).

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

## Skills and the sandbox policy

The agent's tools are skills ([src/jcomit/skills.py](src/jcomit/skills.py)). Each declares the network access it needs, and the OpenShell policy is generated from those declarations ([src/jcomit/policy.py](src/jcomit/policy.py)), so a skill reaches only what it declared and the user approved:

| Skill | Approved | Declares |
|---|---|---|
| `categorize` | yes | `POST api.tokenfactory.nebius.com/v1/chat/completions` |
| `monthly_review` | yes | `POST api.tokenfactory.nebius.com/v1/chat/completions` |
| `share_report` | no | `POST example.com/upload` |

The code is baked into the sandbox image read-only at `/app`; only `/sandbox/data` is writable.

```bash
bash scripts/sandbox_up.sh              # build image, generate policy, attach Token Factory key, upload fake data
scripts/skill.sh categorize
scripts/skill.sh monthly_review --month 2026-09
bash scripts/check_sandbox_rules.sh     # file and network rules + the blocked upload 10 times
bash scripts/demo_policy_flip.sh        # share_report: blocked -> approve -> sent -> revoke -> blocked
PYTHONPATH=src python3 -m jcomit.actionlog -o data/action_log.json
```

We originally planned OpenClaw skills, but `nemoclaw onboard` needs systemd, which Codespaces lacks (see below). The skills are plain Python run inside the same NVIDIA OpenShell sandbox and policy engine.

## NVIDIA OpenShell sandbox (GitHub Codespaces)

The agent runs inside an [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) sandbox with the policy in [openshell/jcomit-policy.yaml](openshell/jcomit-policy.yaml):

- Only Python may reach the model API, and only `POST /v1/chat/completions` and `GET /v1/models`. Any other host, path or program is denied.
- The API key is attached as an OpenShell provider. Code inside the sandbox only sees a placeholder; OpenShell injects the real key at the network boundary.
- Every allowed and denied connection is logged with a reason (`openshell logs jcomit`).

Setup in a Codespace (Ubuntu 22.04, see [.devcontainer](.devcontainer)):

```bash
# Install NemoClaw + OpenShell (onboarding deferred)
curl -fsSL https://www.nvidia.com/nemoclaw.sh | \
  NEMOCLAW_NON_INTERACTIVE=1 NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 \
  NEMOCLAW_AGENT=hermes NEMOCLAW_DEFER_ONBOARDING=1 bash
export PATH="$HOME/.local/bin:$PATH"

# Codespaces has no systemd, so start the gateway by hand and register it
bash openshell/start-gateway.sh
openshell gateway add --local --name local https://127.0.0.1:17670

# Create the sandbox and attach the model key as a provider
openshell sandbox create --name jcomit --policy openshell/jcomit-policy.yaml --detach
NVIDIA_API_KEY=... openshell provider create --name nvidia --type nvidia --credential NVIDIA_API_KEY
openshell sandbox provider attach jcomit nvidia

# Checks
openshell sandbox upload jcomit scripts/check_openshell_egress.py /tmp/
openshell sandbox exec -n jcomit --no-tty -- python3 /tmp/check_openshell_egress.py
```

`nemoclaw onboard` itself needs systemd to supervise the gateway, so it does not complete inside Codespaces.

## License

MIT, see [LICENSE](LICENSE).
