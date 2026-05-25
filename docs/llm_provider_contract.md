# LLM Provider Contract

This document fixes the supported LLM provider contract for the backend.

## Supported providers

Current supported providers:

- `gigachat`
- `openai`
- `mock`

## Environment variables

Common AI settings:

- `AI_PROVIDER`
- `AI_DEFAULT_MODEL`
- `AI_FALLBACK_PROVIDER`
- `AI_FALLBACK_MODEL`
- `AI_REQUEST_TIMEOUT`
- `AI_MAX_RETRIES`
- `AI_TEMPERATURE`

GigaChat settings:

- `GIGACHAT_API_KEY`
- `GIGACHAT_BASE_URL`

OpenAI settings:

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_TIMEOUT`

## Local mock mode

`AI_PROVIDER=mock` is the local and test-friendly mode for deterministic runs.

Typical local setup:

```env
AI_PROVIDER=mock
AI_DEFAULT_MODEL=mock-model
```

This mode is intended for:

- tests
- demos
- provider-switching contract checks

It must not be enabled in production.

## Fallback behavior

The orchestrator can be configured with a fallback provider.

Behavior:

- primary provider is created from `AI_PROVIDER`
- fallback provider is created from `AI_FALLBACK_PROVIDER` when set
- fallback model is taken from `AI_FALLBACK_MODEL`
- fallback is used only when the primary provider fails

## Production guardrails

Production safety rules are enforced in settings validation:

- `AI_PROVIDER=mock` is rejected in production
- `AI_FALLBACK_PROVIDER=mock` is rejected in production

Provider-specific secrets must also be configured before the client can be created:

- `GIGACHAT_API_KEY` for GigaChat
- `OPENAI_API_KEY` for OpenAI

## How to add a new provider

To add a new LLM provider, keep the contract narrow:

1. Add the provider name to `LLMProvider` in `app/core/config.py`.
2. Add a dedicated client in `app/ai/clients/`.
3. Extend `create_llm_client()` in `app/ai/factory.py`.
4. Add provider-specific settings only when the client needs them.
5. Add contract tests for the factory.
6. Keep prompts, use cases, and model routing unchanged unless a separate PR is explicitly scoped for that.

## Testing commands

Recommended checks for provider changes:

```powershell
python -m compileall app tests
python -m pytest -q tests/test_llm_provider_factory.py
python -m pytest -q tests/test_ai_orchestrator.py
python -m pytest -q
```

For quick local contract validation:

```powershell
python -m pytest -q tests/test_llm_provider_factory.py tests/test_ai_orchestrator.py
```
