"""The zero-credential first run must never touch config or the network."""

from click.testing import CliRunner

from adkit import core
from adkit.commands import demo as demo_cmd


def test_demo_needs_no_env_or_network(monkeypatch):
    def explode(*a, **k):
        raise AssertionError("demo must not call the Graph API")

    monkeypatch.setattr(core.graph, "get", explode)
    monkeypatch.setattr(core.graph, "post", explode)
    monkeypatch.delenv("META_ACCESS_TOKEN", raising=False)

    result = CliRunner().invoke(demo_cmd.demo, [])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    assert "Expensive chatbot" in result.output
    assert "Nothing was created" in result.output


def test_init_writes_starter_brief(tmp_path):
    out = tmp_path / "brief.yaml"
    result = CliRunner().invoke(demo_cmd.init, [str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "campaign:" in out.read_text()


def test_init_refuses_to_overwrite(tmp_path):
    out = tmp_path / "brief.yaml"
    out.write_text("keep me")
    result = CliRunner().invoke(demo_cmd.init, [str(out)])
    assert result.exit_code != 0
    assert out.read_text() == "keep me"
