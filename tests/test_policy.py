import pytest

from jcomit.policy import build


def section(policy: str, name: str) -> str:
    start = policy.index(f"  {name}:")
    end = policy.find("\n\n", start)
    return policy[start:end if end >= 0 else None]


def test_default_policy_only_reaches_token_factory():
    p = build()
    assert "host: api.tokenfactory.nebius.com" in p
    assert 'method: POST, path: "/v1/chat/completions"' in p
    assert "example.com" not in p
    assert "integrate.api.nvidia.com" not in p
    assert "used by: categorize, monthly_review" in section(p, "nebius_token_factory")


def test_only_data_is_writable():
    p = build()
    read_write = p.split("read_write:")[1].split("\n\n")[0]
    assert "/sandbox/data" in read_write
    assert "/app" not in read_write
    assert "include_workdir: false" in p


def test_approving_share_report_adds_exactly_its_endpoint():
    base, opened = build(), build({"share_report"})
    s = section(opened, "skill_share_report")
    assert "host: example.com" in s
    assert 'method: POST, path: "/upload"' in s
    assert "used by: share_report" in s
    # Everything else is unchanged: the approval only appends this one section.
    assert opened.startswith(base)
    assert opened[len(base):].strip() == s.strip()


def test_nvidia_backup_is_opt_in():
    assert "integrate.api.nvidia.com" in build(nvidia_backup=True)


def test_unknown_skill_is_rejected():
    with pytest.raises(ValueError):
        build({"wire_money"})
