"""Gemini transport, schema, confidentiality and source-free visible guidance."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import errors, types

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import guidance
import main
from test_concise_guidance import model


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("ENABLE_FAISS", "false")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_gemini_sdk_roundtrip_uses_stateless_google_endpoint(monkeypatch):
    # A mock HTTP transport verifies the real SDK serialization without any network.
    actual_client = genai.Client
    captured = {}
    def handle(request):
        captured["host"] = request.url.host
        captured["body"] = payload = json.loads(request.content)
        evidence = json.loads(payload["input"])["evidence"]
        source = next(item["source_id"] for item in evidence if item["source_id"].startswith("password-reset#"))
        draft = {"case_summary": "A teacher needs help signing in.", "response_type": "procedure", "answer_bullets": [],
                 "steps": [{"text": "Confirm the affected account before changing access.", "source_ids": [source]}],
                 "missing_information": ["Which account is affected?"], "reply_draft": "- Please confirm the affected account.",
                 "reply_source_ids": [source], "escalation_needed": False, "escalation_reason": "",
                 "advisory_priority": "low", "priority_rationale": "One affected teacher."}
        return httpx.Response(200, json={"id": "synthetic", "status": "completed", "model": "gemini-3.8-flash",
                                       "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(draft)}]}]})
    transport_client = httpx.Client(transport=httpx.MockTransport(handle))
    def client(**kwargs):
        captured["options"] = kwargs["http_options"]
        return actual_client(api_key="synthetic", http_options=types.HttpOptions(
            httpx_client=transport_client, timeout=40000, retry_options=types.HttpRetryOptions(attempts=1)))
    monkeypatch.setattr(genai, "Client", client)
    monkeypatch.setattr(main, "apply_model_assist", lambda result, subject, message, matches, notes:
                        guidance.refine(result, subject, message, matches, notes, "gemini-3.8-flash"))
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "true")
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert result["ai_mode"] == "gemini_rag_refined"
    assert captured["host"] == "generativelanguage.googleapis.com"
    assert captured["body"]["store"] is False
    assert captured["body"]["model"] == "gemini-3.8-flash"
    assert captured["body"]["response_format"]["mime_type"] == "application/json"
    assert not captured["body"].get("tools") and not captured["body"].get("previous_interaction_id")
    assert captured["options"].timeout == 40000
    # Injected transports are caller-owned; the test closes its own HTTP client.
    transport_client.close()
    assert result["agent_steps"][0]["source_ids"] and "#" not in result["suggested_approach"]


def test_schema_adapts_unsupported_constraints_but_keeps_enums():
    schema = guidance.gemini_schema()
    def visit(value):
        if isinstance(value, dict):
            assert not {"pattern", "minLength", "maxLength", "default"} & value.keys()
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(schema)
    assert schema["properties"]["response_type"]["enum"] == ["procedure", "answer", "mixed", "clarification"]
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("code,reason", [(400, "configuration"), (401, "configuration"), (403, "configuration"),
                                        (404, "configuration"), (429, "rate_limited"), (500, "unavailable")])
def test_provider_errors_do_not_expose_payload(monkeypatch, code, reason):
    def fail(**kwargs):
        raise errors.ClientError(code, {"error": {"message": "private provider payload"}})
    monkeypatch.setattr(genai, "Client", fail)
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "true")
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert result["ai_unavailable_reason"] == reason
    assert result["ai_mode"] == "rule_based_rag_fallback" and not result["reply_available"]
    assert "private provider payload" not in json.dumps(result)


@pytest.mark.parametrize("alter", [
    lambda data, _: data["steps"][0].update(text="Read the password-reset playbook."),
    lambda data, _: data.update(case_summary="Read Sources and reasoning."),
    lambda data, _: data.update(missing_information=["Read cases/password-reset.md"]),
    lambda data, _: data.update(priority_rationale="Use " + data["reply_source_ids"][0]),
])
def test_visible_references_are_rejected_but_internal_citations_retained(monkeypatch, alter):
    model(monkeypatch, alter)
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert result["ai_mode"] == "rule_based_rag_fallback"
    assert "Sources and reasoning" not in result["suggested_approach"]
    assert "playbook" not in result["suggested_approach"].lower()
    assert result["rag_articles"] and result["evidence_details"]


def test_openai_settings_cannot_enable_generation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-old-key")
    monkeypatch.setenv("ENABLE_OPENAI_TRIAGE", "true")
    monkeypatch.setattr(genai, "Client", lambda **kwargs: pytest.fail("Disabled Gemini must not call a provider"))
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert result["ai_mode"] == "rule_based_rag"


def test_timeout_falls_back_safely(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "true")
    def fail(**kwargs):
        raise httpx.ReadTimeout("private timeout details")
    monkeypatch.setattr(genai, "Client", fail)
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert result["ai_mode"] == "rule_based_rag_fallback"
    assert "private timeout" not in json.dumps(result)


@pytest.mark.parametrize("recover", [True, False])
def test_rate_limit_retries_once_and_closes_client(monkeypatch, recover):
    import time
    model(monkeypatch)
    original = genai.Client
    captured = {"calls": 0, "closed": False}
    def client(**kwargs):
        instance = original(**kwargs)
        create = instance.interactions.create
        def retry(**body):
            captured["calls"] += 1
            if captured["calls"] == 1 or not recover:
                raise errors.ClientError(429, {"error": {"message": "private rate-limit details"}})
            return create(**body)
        instance.interactions.create = retry
        instance.close = lambda: captured.update(closed=True)
        return instance
    monkeypatch.setattr(genai, "Client", client)
    monkeypatch.setattr(time, "sleep", lambda _: None)
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert captured["calls"] == 2 and captured["closed"]
    assert result["ai_mode"] == ("gemini_rag_refined" if recover else "rule_based_rag_fallback")
    assert "private rate-limit" not in json.dumps(result)
