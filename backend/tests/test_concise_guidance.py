"""Intent, retrieval relevance, customer boundaries and concise evidence output."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import guidance
import main
import rag


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setenv("ENABLE_FAISS", "false")
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "false")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.mark.parametrize("description,kind", [
    ("How does Clever choose the role for SSO?", "answer"),
    ("How do I reset a password?", "procedure"),
    ("Can you reset a password?", "procedure"),
    ("Why does Clever choose this role? Please change the role.", "mixed"),
    ("A teacher forgot their password.", "procedure"),
    ("Please explain what the role means.", "answer"),
    ("Hello", "clarification"),
])
def test_intent_distinguishes_explanation_from_action(description, kind):
    assert guidance.response_kind(description, True) == kind


def test_fallback_is_short_cited_evidence_with_full_conditions_available():
    result = main.rag_triage("Reset password", "How does Clever choose the role for SSO when a teacher is also an admin?")
    assert result["response_type"] == "answer"
    assert 1 <= len(result["answer_bullets"]) <= 6
    assert all(len(item["text"].split()) <= 65 and item["source_ids"] for item in result["answer_bullets"])
    assert "highest" in result["suggested_approach"].lower()
    assert result["evidence_details"] and not result["agent_steps"]
    assert not result["reply_available"]
    assert not result["missing_information"]


def test_unrelated_vector_procedure_is_not_added(monkeypatch):
    unrelated = next(item for item in rag.load_documents(main.HELP_CENTER_DIR) if item["slug"] == "user-deactivation")
    unrelated.update(matched_sections=unrelated["sections"], matched_aliases=[], title_matches=0, score=.95)
    monkeypatch.setattr(main, "retrieve_evidence", lambda *args: ([unrelated], "faiss_hybrid"))
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert "user-deactivation" not in {item["slug"] for item in result["rag_articles"]}


def test_hard_sso_excludes_manual_reset_and_soft_branch():
    doc = next(item for item in rag.load_documents(main.HELP_CENTER_DIR) if item["slug"] == "password-reset")
    selected = guidance.applicable_sections(doc, "Hard SSO district", full=True)
    headings = " ".join(item["heading"] for item in selected)
    assert "Hard SSO" in headings
    assert "Soft SSO" not in headings and "Step 3" not in headings and "Step 2" not in headings


def test_single_term_question_retrieves_glossary_answer():
    result = main.rag_triage("Question", "What is PDS?")
    assert result["response_type"] == "answer"
    assert any("Provisioning Data Services" in item["text"] for item in result["answer_bullets"])
    assert not result["agent_steps"] and not result["reply_available"]


def model(monkeypatch, alter=None):
    from google import genai
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        evidence = json.loads(kwargs["input"])["evidence"]
        source = next(item["source_id"] for item in evidence if item["source_id"].startswith("password-reset#"))
        data = {"case_summary": "A teacher needs help signing in.", "response_type": "procedure",
                "answer_bullets": [], "steps": [{"text": "Verify the affected account before preparing a reset.", "source_ids": [source]}],
                "missing_information": ["Which account is affected?"],
                "reply_draft": "- Please confirm the affected account so support can review the login issue.",
                "reply_source_ids": [source], "escalation_needed": False, "escalation_reason": "",
                "advisory_priority": "low", "priority_rationale": "One affected teacher."}
        if alter:
            alter(data, evidence)
        return SimpleNamespace(status="completed", output_text=json.dumps(data))
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(close=lambda: None, interactions=SimpleNamespace(create=create)))
    monkeypatch.setenv("ENABLE_GEMINI_TRIAGE", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic")
    return captured


def test_structured_output_and_prompt_keep_copyable_reply(monkeypatch):
    captured = model(monkeypatch)
    result = main.rag_triage("Help", "A teacher forgot their password. Soft SSO.")
    assert result["ai_mode"] == "gemini_rag_refined"
    assert result["agent_steps"] and result["reply_draft"].startswith("- ")
    schema = captured["response_format"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])
    assert "beginner" in captured["system_instruction"] and "customer-ready" in captured["system_instruction"]


@pytest.mark.parametrize("alter", [
    lambda data, _: data.update(reply_draft="- Click Forgot Password to reset your password."),
    lambda data, _: data["steps"][0].update(text="Explain " * 70),
    lambda data, _: data.update(reply_draft="word " * 251),
    lambda data, _: data.update(reply_draft="Use " + data["reply_source_ids"][0]),
    lambda data, _: data.update(response_type="answer"),
    lambda data, _: data.update(reply_draft="- Your password has been reset."),
    lambda data, _: data.update(response_type="mixed"),
    lambda data, _: data["steps"][0].update(text="word " * 41),
    lambda data, _: data.update(case_summary="word " * 26),
])
def test_invalid_or_unsafe_output_falls_back(monkeypatch, alter):
    model(monkeypatch, alter)
    result = main.rag_triage("Help", "A teacher forgot their password. Soft SSO.")
    assert result["ai_mode"] == "rule_based_rag_fallback"
    assert not result["reply_available"]


def test_answer_requires_topic_evidence(monkeypatch):
    def alter(data, evidence):
        data.update(response_type="answer", steps=[], reply_source_ids=[next(item["source_id"] for item in evidence if item["source_id"].startswith("guardrails#"))])
    model(monkeypatch, alter)
    result = main.rag_triage("Question", "What is a password reset?")
    assert result["ai_mode"] == "rule_based_rag_fallback"


def test_soft_sso_reply_can_explain_customer_cannot_reset(monkeypatch):
    model(monkeypatch, lambda data, _: data.update(reply_draft="- You cannot reset your own password. Support needs to review the affected account."))
    result = main.rag_triage("Help", "A teacher forgot their password. Soft SSO.")
    assert result["ai_mode"] == "gemini_rag_refined"


def test_procedural_fallback_uses_compact_review_steps_not_playbook_dump():
    result = main.rag_triage("Help", "A teacher forgot their password.")
    assert 1 <= len(result["agent_steps"]) <= 3
    assert all(len(item["text"].split()) <= 25 for item in result["agent_steps"])
    assert len(result["suggested_approach"].split()) < 100
    assert result["evidence_details"] and not result["reply_available"]


def test_description_changes_clear_all_structured_guidance(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "TICKETS_DIR", tmp_path)
    case = {"Id": "500000000000001AAA", "Subject": "Help", "Description": "Original"}
    ticket = main.mirror_salesforce_case(case, "https://example.my.salesforce.com")
    ticket.update(answer_bullets=[{"text": "Old answer", "source_ids": ["old"]}], agent_steps=[{"text": "Old step", "source_ids": ["old"]}], evidence_details=[{"text": "Old evidence"}], response_type="mixed")
    main.save_ticket(ticket)
    case["Description"] = "Changed"
    updated = main.mirror_salesforce_case(case, "https://example.my.salesforce.com")
    assert not updated["answer_bullets"] and not updated["agent_steps"] and not updated["evidence_details"]
    assert updated["response_type"] is None and updated["guidance_stale"]
