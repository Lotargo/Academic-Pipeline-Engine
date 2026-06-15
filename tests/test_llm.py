import pytest
from academic_pe.core.llm import (
    MockProvider,
    OpenAIProvider,
    CustomOpenAIProvider,
    GoogleProvider,
    LMStudioProvider,
    ZenProvider,
    create_provider,
    register_provider,
    LLMProvider,
)
from academic_pe.core.llm import AnthropicProvider as AnthropicProviderCls


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

    def test_creates_google(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "sk-google-test")
        provider = create_provider("google")
        assert isinstance(provider, GoogleProvider)

    def test_creates_lm_studio(self):
        provider = create_provider("lm_studio")
        assert isinstance(provider, LMStudioProvider)

    def test_creates_zen(self, monkeypatch):
        monkeypatch.setenv("ZEN_API_KEY", "sk-zen-test")
        provider = create_provider("zen")
        assert isinstance(provider, ZenProvider)

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

    def test_openai_provider_reuses_client_for_same_key(self):
        first = OpenAIProvider(api_key="sk-cache-openai")
        second = OpenAIProvider(api_key="sk-cache-openai")

        assert first._client is second._client

    def test_openai_compatible_provider_reuses_client_for_same_base_url(self):
        first = CustomOpenAIProvider(base_url="http://localhost:11434/v1", api_key="sk-cache-custom")
        second = CustomOpenAIProvider(base_url="http://localhost:11434/v1", api_key="sk-cache-custom")
        other = CustomOpenAIProvider(base_url="http://localhost:5678/v1", api_key="sk-cache-custom")

        assert first._client is second._client
        assert first._client is not other._client


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
        import sys
        monkeypatch.setitem(sys.modules, "anthropic", None)
        with pytest.raises(ImportError, match="anthropic package"):
            AnthropicProviderCls()


from academic_pe.core.llm import RetryConfig as LLMRetryConfig
from academic_pe.core.llm import RetryProvider as RetryProviderCls

class TestRetryProvider:
    def test_passes_through_on_success(self):
        inner = MockProvider()
        rp = RetryProviderCls(inner, LLMRetryConfig(max_retries=3))
        result = rp.generate("sys", "hello", "m", 0.0)
        assert "mock response" in result

    def test_retries_on_failure_then_succeeds(self):
        class FlakyProvider(LLMProvider):
            def __init__(self):
                self.calls = 0
            def generate(self, system_prompt, user_prompt, model, temperature):
                self.calls += 1
                if self.calls < 3:
                    raise ConnectionError("API timeout")
                return "success"

        flaky = FlakyProvider()
        rp = RetryProviderCls(flaky, LLMRetryConfig(max_retries=5, base_delay=0.01))
        result = rp.generate("sys", "hello", "m", 0.0)
        assert result == "success"
        assert flaky.calls == 3

    def test_exhausts_retries_and_raises(self):
        class AlwaysFails(LLMProvider):
            def generate(self, system_prompt, user_prompt, model, temperature):
                raise RuntimeError("persistent failure")

        rp = RetryProviderCls(AlwaysFails(), LLMRetryConfig(max_retries=2, base_delay=0.01))

        with pytest.raises(RuntimeError, match="persistent failure"):
            rp.generate("sys", "hello", "m", 0.0)

    def test_zero_retries_passes_through(self):
        class FailingProvider(LLMProvider):
            def __init__(self):
                self.calls = 0
            def generate(self, system_prompt, user_prompt, model, temperature):
                self.calls += 1
                raise RuntimeError("fail")

        fail = FailingProvider()
        rp = RetryProviderCls(fail, LLMRetryConfig(max_retries=0))
        with pytest.raises(RuntimeError):
            rp.generate("sys", "hello", "m", 0.0)
        assert fail.calls == 1

    def test_create_provider_with_retry(self):
        rc = LLMRetryConfig(max_retries=3, base_delay=0.1)
        provider = create_provider("mock", retry_config=rc)
        assert isinstance(provider, RetryProviderCls)
        assert provider._config.max_retries == 3

    def test_create_provider_skips_retry_when_zero(self):
        rc = LLMRetryConfig(max_retries=0)
        provider = create_provider("mock", retry_config=rc)
        assert not isinstance(provider, RetryProviderCls)

    def test_create_provider_skips_retry_when_none(self):
        provider = create_provider("mock", retry_config=None)
        assert not isinstance(provider, RetryProviderCls)

    def test_config_integration(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        rc = LLMRetryConfig(max_retries=5, base_delay=2.0, max_delay=60.0)
        provider = create_provider("openai", retry_config=rc)
        assert isinstance(provider, RetryProviderCls)
        assert provider._config.max_retries == 5
        assert provider._config.base_delay == 2.0
        assert provider._config.max_delay == 60.0


from academic_pe.core.llm import (
    CircuitBreakerProvider,
    CircuitBreakerConfig as LLMCBCConfig,
    CircuitState,
)
from academic_pe.core.config import CircuitBreakerConfig as CfgCBConfig


class TestCircuitBreaker:
    def test_starts_closed(self):
        inner = MockProvider()
        cb = CircuitBreakerProvider(inner, LLMCBCConfig(failure_threshold=3))
        assert cb.state == CircuitState.CLOSED

    def test_passes_through_on_success(self):
        inner = MockProvider()
        cb = CircuitBreakerProvider(inner, LLMCBCConfig(failure_threshold=3))
        result = cb.generate("sys", "hello", "m", 0.0)
        assert "mock response" in result

    def test_opens_after_threshold(self):
        class Failing(LLMProvider):
            def generate(self, system_prompt, user_prompt, model, temperature):
                raise RuntimeError("fail")

        cb = CircuitBreakerProvider(Failing(), LLMCBCConfig(failure_threshold=3, recovery_timeout=999))
        for _ in range(3):
            try:
                cb.generate("sys", "hello", "m", 0.0)
            except RuntimeError:
                pass
        assert cb.state == CircuitState.OPEN

    def test_blocks_when_open(self):
        class Failing(LLMProvider):
            def generate(self, system_prompt, user_prompt, model, temperature):
                raise RuntimeError("fail")

        cb = CircuitBreakerProvider(Failing(), LLMCBCConfig(failure_threshold=2, recovery_timeout=999))
        for _ in range(2):
            try:
                cb.generate("sys", "hello", "m", 0.0)
            except RuntimeError:
                pass

        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            cb.generate("sys", "hello", "m", 0.0)

    def test_half_open_after_timeout(self):
        inner = MockProvider()
        cb = CircuitBreakerProvider(inner, LLMCBCConfig(failure_threshold=1, recovery_timeout=0.01))

        class FailOnce(LLMProvider):
            def __init__(self):
                self.called = False
            def generate(self, system_prompt, user_prompt, model, temperature):
                if not self.called:
                    self.called = True
                    raise RuntimeError("fail")
                return "recovered"

        fail_once = FailOnce()
        cb._inner = fail_once
        try:
            cb.generate("sys", "hello", "m", 0.0)
        except RuntimeError:
            pass
        assert cb.state == CircuitState.OPEN

        import time
        time.sleep(0.02)

        result = cb.generate("sys", "hello", "m", 0.0)
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        inner = MockProvider()
        cb = CircuitBreakerProvider(inner, LLMCBCConfig(failure_threshold=5))
        cb._failure_count = 4
        cb.generate("sys", "hello", "m", 0.0)
        assert cb._failure_count == 0

    def test_create_provider_with_circuit_breaker(self):
        cbc = CfgCBConfig(enabled=True, failure_threshold=10, recovery_timeout=60.0)
        provider = create_provider("mock", circuit_breaker_config=cbc)
        assert isinstance(provider, CircuitBreakerProvider)
        assert provider._config.failure_threshold == 10

    def test_create_provider_skips_cb_when_disabled(self):
        cbc = CfgCBConfig(enabled=False)
        provider = create_provider("mock", circuit_breaker_config=cbc)
        assert not isinstance(provider, CircuitBreakerProvider)
