import json
from types import SimpleNamespace

import pytest
import main
import rag
import guidance
import salesforce


def test_answer_can_have_no_procedure_steps(monkeypatch):
    from google import genai
    monkeypatch.setenv("ENABLE_FAISS", "false")
    def create(**kwargs):
        evidence = json.loads(kwargs["input"])["evidence"]
        source = next(item["source_id"] for item in evidence if item["source_id"].startswith("clever#"))
        return SimpleNamespace(status="completed", output_text=json.dumps({
            "response_type": "answer", "case_summary": "The highest-level role is used for SSO.",
            "steps": [], "missing_information": [], "reply_draft": "When you hold multiple roles, Clever SSO opens the highest-level i-Ready role.",
            "reply_source_ids": [source], "escalation_needed": False, "escalation_reason": "",
            "advisory_priority": "low", "priority_rationale": "Informational question."}))
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(close=lambda: None, interactions=SimpleNamespace(create=create)))
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "true")
    result = main.rag_triage("Question", "How does Clever choose the role for SSO when a teacher is also an admin?")
    assert result["response_type"] == "answer"
    assert result["reply_available"]
    assert not result["missing_information"]


def test_fallback_quotes_evidence_instead_of_canned_clarification(monkeypatch):
    monkeypatch.setenv("ENABLE_FAISS", "false")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "false")
    result = main.rag_triage("Question", "How does Clever choose the role for SSO when a teacher is also an admin?")
    assert "highest" in result["suggested_approach"].lower()
    assert not result["reply_available"]
    assert "exact symptoms" not in result["reply_draft"]


def test_describe_omits_optional_fields_but_requires_description(monkeypatch):
    session = SimpleNamespace(instance_url="https://example.my.salesforce.com", access_token="fake")
    monkeypatch.setattr(salesforce, "_json_request", lambda *a, **k: {"fields": [{"name": name} for name in ["Id", "Subject", "Description"]]})
    assert salesforce.readable_case_fields(session) == "Id, Subject, Description"
    monkeypatch.setattr(salesforce, "_json_request", lambda *a, **k: {"fields": [{"name": "Id"}]})
    with pytest.raises(salesforce.HTTPException) as error:
        salesforce.readable_case_fields(session)
    assert error.value.status_code == 403


def test_vector_failure_is_labeled(monkeypatch):
    import vector_store
    monkeypatch.setenv("ENABLE_FAISS", "true")
    def fail(*args):
        raise OSError("Model not installed")
    monkeypatch.setattr(vector_store, "search", fail)
    articles, mode = rag.retrieve_evidence(main.HELP_CENTER_DIR, "forgot password")
    assert articles and mode == "lexical_fallback"


def test_faiss_persistence_invalidation_and_late_query_window(tmp_path, monkeypatch):
    import numpy as np
    import vector_store
    class Encoder:
        tokenizer = SimpleNamespace(encode=lambda text, **kwargs: list(text), decode=lambda ids: "".join(ids))
        def encode(self, texts, **kwargs):
            rows = np.array([[1., float("password" in text), float("Clever" in text)] for text in texts], dtype="float32")
            return rows / np.linalg.norm(rows, axis=1, keepdims=True)
    monkeypatch.setattr(vector_store, "_model", Encoder())
    monkeypatch.setattr(vector_store, "CACHE", tmp_path)
    docs = [{"path": "case.md", "slug": "case", "title": "Account", "content": "Clever roles", "sections": [{"section_id": "case#roles", "heading": "Roles", "content": "Clever roles"}]}]
    first = vector_store.search(docs, "background " * 100 + "Clever")
    assert first and first[0][0] == ("case", "case#roles")
    assert len(list(tmp_path.glob("*/index.faiss"))) == 1
    assert vector_store.search(docs, "Clever")
    assert len(list(tmp_path.glob("*/index.faiss"))) == 1
    docs[0]["content"] += " updated"
    vector_store.search(docs, "Clever")
    assert len(list(tmp_path.glob("*/index.faiss"))) == 2
