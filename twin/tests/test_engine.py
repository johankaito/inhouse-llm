import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from engine import EngineError, OllamaEngine, OpenAICompatEngine, build_engine


def test_build_engine_defaults_to_ollama_legacy_section():
    config = {"twin_config": {"ollama": {"base_url": "http://example:11434", "timeout": 99}}}
    engine = build_engine(config)
    assert isinstance(engine, OllamaEngine)
    assert engine.base_url == "http://example:11434"
    assert engine.timeout == 99


def test_build_engine_engine_section_wins():
    config = {
        "twin_config": {
            "engine": {"provider": "ollama", "base_url": "http://engine:11434", "timeout": 5},
            "ollama": {"base_url": "http://legacy:11434", "timeout": 120},
        }
    }
    engine = build_engine(config)
    assert isinstance(engine, OllamaEngine)
    assert engine.base_url == "http://engine:11434"
    assert engine.timeout == 5


def test_build_engine_openai_compat():
    config = {
        "twin_config": {
            "engine": {
                "provider": "openai-compat",
                "base_url": "http://127.0.0.1:8080/v1",
                "api_key": "secret",
            }
        }
    }
    engine = build_engine(config)
    assert isinstance(engine, OpenAICompatEngine)
    assert engine.base_url == "http://127.0.0.1:8080/v1"
    assert engine.api_key == "secret"


def test_build_engine_openai_compat_requires_base_url():
    config = {"twin_config": {"engine": {"provider": "openai-compat"}}}
    with pytest.raises(EngineError):
        build_engine(config)


def test_openai_compat_payload_maps_options_and_strips_server_side_keys():
    engine = OpenAICompatEngine(base_url="http://127.0.0.1:8080/v1")
    payload = engine._build_payload(
        model="qwen2.5-coder:14b",
        messages=[{"role": "user", "content": "hi"}],
        options={"temperature": 0.3, "top_p": 0.8, "num_ctx": 32768, "keep_alive": "5m"},
        stream=False,
    )
    assert payload["model"] == "qwen2.5-coder:14b"
    assert payload["temperature"] == 0.3
    assert payload["top_p"] == 0.8
    assert "num_ctx" not in payload
    assert "keep_alive" not in payload
    assert payload["messages"] == [{"role": "user", "content": "hi"}]


def test_openai_compat_rejects_images():
    engine = OpenAICompatEngine(base_url="http://127.0.0.1:8080/v1")
    with pytest.raises(EngineError):
        engine._build_payload(
            model="llava",
            messages=[{"role": "user", "content": "what is this", "images": ["/tmp/x.png"]}],
            options={},
            stream=False,
        )


def test_openai_compat_warns_when_pointed_at_ollama_v1(capsys):
    engine = OpenAICompatEngine(base_url="http://localhost:11434/v1")
    engine._warn_if_ollama_v1({"num_ctx": 32768})
    captured = capsys.readouterr()
    assert "num_ctx" in captured.err
    engine._warn_if_ollama_v1({"num_ctx": 32768})
    assert capsys.readouterr().err == ""


def test_openai_compat_auth_header_only_with_key():
    no_key = OpenAICompatEngine(base_url="http://127.0.0.1:8080/v1")
    assert "Authorization" not in no_key._headers()
    with_key = OpenAICompatEngine(base_url="http://127.0.0.1:8080/v1", api_key="abc")
    assert with_key._headers()["Authorization"] == "Bearer abc"
