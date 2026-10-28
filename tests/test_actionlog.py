from jcomit.actionlog import parse_openshell, parse_skills, timeline

# Real lines from `openshell logs jcomit` (Oct 24), one with colour codes left in.
LOGS = """\
[1792843901.343] [sandbox] [OCSF ] [ocsf] SSH:OPEN [INFO] ALLOWED
[1792872400.957] [sandbox] [OCSF ] [ocsf] NET:OPEN [INFO] ALLOWED /sandbox/.uv/python/cpython-3.14.3-linux-x86_64-gnu/bin/python3.14(62) -> api.tokenfactory.nebius.com:443 [policy:nebius_token_factory engine:opa]
[1792872401.772] [sandbox] [OCSF ] [ocsf] HTTP:POST [INFO] ALLOWED POST http://api.tokenfactory.nebius.com:443/v1/chat/completions [policy:nebius_token_factory engine:l7]
\x1b[2m[1792843902.623]\x1b[0m [sandbox] [OCSF ] [ocsf] NET:OPEN [MED] DENIED /sandbox/.uv/python/cpython-3.14.3-linux-x86_64-gnu/bin/python3.14(57) -> webhook.site:443 [policy:- engine:opa] [reason:endpoint webhook.site:443 is not allowed by any policy]
[1792844012.147] [sandbox] [OCSF ] [ocsf] CONFIG:APPLYING [INFO] Applying Landlock filesystem sandbox [abi:V2 compat:BestEffort ro:6 rw:3]
""".splitlines()


def test_parses_allowed_and_denied_network_decisions():
    events = parse_openshell(LOGS)
    assert [(e["result"], e["kind"]) for e in events] == [
        ("allowed", "connect"), ("allowed", "request"), ("denied", "connect"),
    ]
    connect, request, denied = events
    assert connect["program"] == "python3.14"
    assert connect["target"] == "api.tokenfactory.nebius.com:443"
    assert connect["policy"] == "nebius_token_factory"
    assert request["target"] == "POST api.tokenfactory.nebius.com/v1/chat/completions"
    assert denied["target"] == "webhook.site:443"
    assert denied["policy"] is None
    assert denied["reason"] == "endpoint webhook.site:443 is not allowed by any policy"
    assert denied["time"].startswith("2026-10-")


def test_timeline_merges_skill_and_sandbox_events_in_order():
    skills = parse_skills([
        '{"time": "2026-10-25T07:00:00+00:00", "source": "skill", "skill": "share_report", "result": "blocked"}',
        "",
    ])
    merged = timeline(parse_openshell(LOGS), skills)
    assert [e["time"] for e in merged] == sorted(e["time"] for e in merged)
    assert any(e["source"] == "skill" for e in merged)


def test_since_accepts_short_durations():
    from datetime import timedelta

    import pytest

    from jcomit.actionlog import since_delta

    assert since_delta("90s") == timedelta(seconds=90)
    assert since_delta("5m") == timedelta(minutes=5)
    assert since_delta("2h") == timedelta(hours=2)
    with pytest.raises(ValueError):
        since_delta("soon")
