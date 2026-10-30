import pytest
from unittest.mock import MagicMock, patch

import app.clients.llm_client as llm_module
from app.clients.llm_client import LLMClient


def _openai_response(content):
    response = MagicMock()
    response.choices[0].message.content = content
    return response


@pytest.fixture
def mocks():
    with patch.object(llm_module, "OpenAI") as mock_openai_cls, \
         patch.object(llm_module, "genai") as mock_genai:
        yield mock_openai_cls.return_value, mock_genai.GenerativeModel.return_value


def test_openai_is_used_first(mocks):
    """OpenAI が設定されていれば OpenAI の結果を使い、Gemini は呼ばない。"""
    openai_client, gemini_model = mocks
    openai_client.chat.completions.create.return_value = _openai_response('{"title": "OpenAI"}')

    client = LLMClient(api_key="gemini-key", openai_api_key="openai-key")
    result = client.parse_task_text("prompt")

    assert result == {"title": "OpenAI"}
    gemini_model.generate_content.assert_not_called()


def test_falls_back_to_gemini_when_openai_fails(mocks):
    """OpenAI がエラーになった場合は Gemini にフォールバックする。"""
    openai_client, gemini_model = mocks
    openai_client.chat.completions.create.side_effect = RuntimeError("429 quota exceeded")
    gemini_model.generate_content.return_value.text = '```json\n{"title": "Gemini"}\n```'

    client = LLMClient(api_key="gemini-key", openai_api_key="openai-key")
    result = client.parse_task_text("prompt")

    assert result == {"title": "Gemini"}


def test_openai_error_is_raised_without_gemini_key(mocks, monkeypatch):
    """Gemini のキーがなければ OpenAI のエラーをそのまま送出する。"""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    openai_client, _ = mocks
    openai_client.chat.completions.create.side_effect = RuntimeError("429 quota exceeded")

    client = LLMClient(api_key=None, openai_api_key="openai-key")
    with pytest.raises(RuntimeError):
        client.parse_task_text("prompt")


def test_gemini_only_when_openai_not_configured(mocks, monkeypatch):
    """OpenAI のキーが未設定なら従来どおり Gemini のみで動作する。"""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    openai_client, gemini_model = mocks
    gemini_model.generate_content.return_value.text = '{"title": "Gemini"}'

    client = LLMClient(api_key="gemini-key")
    result = client.parse_task_text("prompt")

    assert result == {"title": "Gemini"}
    openai_client.chat.completions.create.assert_not_called()


def test_raises_when_no_key_is_set(mocks, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError):
        LLMClient(api_key=None)
