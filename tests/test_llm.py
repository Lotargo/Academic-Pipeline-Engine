import pytest
from src.core.llm import (
    MockProvider,
    OpenAIProvider,
    CustomOpenAIProvider,
    create_provider,
    register_provider,
    LLMProvider,
)
from src.core.llm import AnthropicProvider as AnthropicProviderCls


class TestMockProvider:
    def test_generates_response(self):
        provider = MockProvider()
        result = provider.generate("sys", "hello", "mock-model", 0.0)
        assert isinstance(result, str)
        assert "mock response" in result

    def test_includes_prompt_in_response(self):
        provider = MockProvider()
        result = provider.generate("sys", "custom prompt text", "m", 0.5)
        assert "custom prompt text" in result


class TestCreateProvider:
    def test_creates_mock_by_default(self):
        provider = create_provider("mock")
        assert isinstance(provider, MockProvider)

    def test_creates_openai(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        provider = create_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_custom_openai_requires_base_url(self):
        with pytest.raises(ValueError, match="base_url is required"):
            create_provider("custom_openai")

    def test_custom_openai_with_base_url(self, monkeypatch):
        monkeypatch.setenv("CUSTOM_API_KEY", "sk-test")
        provider = create_provider("custom_openai", base_url="http://localhost:11434/v1")
        assert isinstance(provider, CustomOpenAIProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("nonexistent")

    def test_register_and_create_custom(self):
        class TestProvider(LLMProvider):
            def generate(self, system_prompt, user_prompt, model, temperature):
                return "test"

        register_provider("test_custom", TestProvider)
        provider = create_provider("test_custom")
        assert isinstance(provider, TestProvider)
        assert provider.generate("", "", "", 0) == "test"


class TestCustomOpenAIProvider:
    def test_uses_custom_base_url(self, monkeypatch):
        monkeypatch.setenv("CUSTOM_API_KEY", "sk-test")
        provider = CustomOpenAIProvider(base_url="http://localhost:11434/v1")
        assert provider._client.base_url == "http://localhost:11434/v1/"

    def test_custom_api_key_env(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "sk-custom")
        provider = CustomOpenAIProvider(
            base_url="http://localhost:11434/v1",
            api_key_env="MY_KEY",
        )
        assert provider._client.api_key == "sk-custom"


class TestAnthropicProvider:
    def test_missing_api_key_raises(self):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            AnthropicProviderCls()

    def test_missing_package_raises(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with pytest.raises(ImportError, match="anthropic package"):
            AnthropicProviderCls()
