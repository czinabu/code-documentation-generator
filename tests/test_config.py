import pytest

from docgen.config import ConfigError, Settings


def test_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings.load(env={})
    assert s.model == "qwen3:14b"
    assert s.ollama_host == "http://localhost:11434"
    assert s.timeout == 120.0


def test_env_overrides(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings.load(
        env={"DOCGEN_MODEL": "llama3", "OLLAMA_HOST": "http://h:1", "DOCGEN_TIMEOUT": "30"}
    )
    assert (s.model, s.ollama_host, s.timeout) == ("llama3", "http://h:1", 30.0)


def test_docgen_host_beats_ollama_host(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    s = Settings.load(env={"DOCGEN_OLLAMA_HOST": "http://a", "OLLAMA_HOST": "http://b"})
    assert s.ollama_host == "http://a"


def test_toml_file_then_env(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[docgen]\nmodel = "from-file"\ntimeout = 10\n')
    s = Settings.load(env={"DOCGEN_CONFIG": str(cfg), "DOCGEN_TIMEOUT": "20"})
    assert s.model == "from-file"
    assert s.timeout == 20.0


def test_default_config_file_in_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docgen.toml").write_text('model = "cwd-model"\n')
    assert Settings.load(env={}).model == "cwd-model"


@pytest.mark.parametrize(
    "content, env",
    [
        ("bogus = 1\n", {}),
        ("", {"DOCGEN_TIMEOUT": "soon"}),
        ("", {"DOCGEN_TIMEOUT": "-1"}),
        ("not = [valid", {}),
    ],
)
def test_invalid_config(tmp_path, content, env):
    cfg = tmp_path / "c.toml"
    cfg.write_text(content)
    with pytest.raises(ConfigError):
        Settings.load(env={"DOCGEN_CONFIG": str(cfg), **env})


def test_missing_config_file(tmp_path):
    with pytest.raises(ConfigError):
        Settings.load(env={"DOCGEN_CONFIG": str(tmp_path / "nope.toml")})
