import sys
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import main
from main import HELP_CENTER_DIR, import_excel_tickets, pending_approach, rag_triage, triage
from rag import retrieve_articles


@pytest.fixture(autouse=True)
def disable_live_model_calls(monkeypatch):
    """Unit tests use deterministic behavior unless a test supplies a fake model."""
    monkeypatch.setenv("ENABLE_OPENAI_TRIAGE", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_roster_login_case_selects_a_playbook_but_requires_human_review():
    result = triage("Student cannot log in", "A student is missing from the roster after an SSO error.")
    assert result["status"] == "open"
    assert result["requires_human"]
    assert result["category"] == "Login or Missing Entity"
    assert result["recommended_article"] == "Failed login / missing user, section, or enrollment"


def test_high_risk_playbook_sets_priority_and_suggestion():
    result = triage("Deactivate a grade", "Please deactivate all students in this grade.")
    assert result["category"] == "User Deactivation"
    assert result["priority"] == "high"
    assert "written authorization" in result["suggested_approach"]


def test_password_reset_is_low_risk_not_a_security_escalation():
    result = triage("Password reset", "A teacher forgot their password.")
    assert result["category"] == "Password Reset"
    assert result["priority"] == "low"
    assert result["status"] == "open"


def test_urgent_security_request_escalates():
    result = triage("Urgent charge", "I was hacked and need help immediately")
    assert result["status"] == "escalated"
    assert result["priority"] == "critical"
    assert result["requires_human"]


def test_uncertain_request_requires_human():
    result = triage("Could you add this?", "Could you add a new reporting option?")
    assert result["status"] == "open"
    assert result["requires_human"]


def test_new_cases_start_untriaged_until_an_agent_requests_an_approach():
    result = pending_approach()
    assert result["ai_mode"] == "not_requested"
    assert result["rag_articles"] == []
    assert result["requires_human"]


def test_excel_import_creates_untriaged_tickets_without_running_rag(monkeypatch):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Subject", "Customer", "Message"])
    sheet.append(["Invoice request", "Taylor", "Where can I download my invoice?"])
    contents = BytesIO()
    workbook.save(contents)
    monkeypatch.setattr(main, "save_ticket", lambda ticket: ticket)

    imported, skipped = import_excel_tickets(contents.getvalue())

    assert not skipped
    assert imported[0]["source"] == "excel_beta_import"
    assert imported[0]["ai_mode"] == "not_requested"
    assert imported[0]["rag_articles"] == []


def test_excel_import_accepts_case_export_format(monkeypatch):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Case Number", "Account Name", "Subject", "Case Reason", "Case Sub Reason", "Product"])
    sheet.append(["01540700", "Test District A SD", "Student report update", "General Inquiry", "Roster", "iReady"])
    contents = BytesIO()
    workbook.save(contents)
    monkeypatch.setattr(main, "save_ticket", lambda ticket: ticket)

    imported, skipped = import_excel_tickets(contents.getvalue())

    assert not skipped
    assert imported[0]["customer"] == "Test District A SD"
    assert "Case Number: 01540700" in imported[0]["message"]
    assert imported[0]["imported_case_fields"]["Product"] == "iReady"
    assert imported[0]["case_reason"] == "General Inquiry"


def test_retriever_returns_relevant_help_center_article():
    results = retrieve_articles(HELP_CENTER_DIR, "A student cannot log in because of an SSO error")
    assert results[0]["slug"] == "failed-login-missing-entity"


def test_agentic_rag_uses_aliases_and_returns_a_playbook_grounded_plan():
    result = rag_triage("Teacher sees no classes", "The teacher receives the oops error after signing in.")
    assert result["category"] == "No Classes Assigned"
    assert result["recommended_article"] == '"Oops! You are currently not assigned to any classes"'
    assert result["rag_articles"][0]["matched_aliases"]
    assert "Provisioning Notes" in result["suggested_approach"]


def test_agentic_rag_stops_for_missing_required_procedure():
    result = rag_triage("Start syncing admins", "Please enable the admin sync setting.")
    assert result["category"] == "Syncing Admin Behavior"
    assert result["status"] == "escalated"
    assert "Stop: this playbook says the required procedure is unavailable" in result["suggested_approach"]


def test_retriever_never_suggests_a_reference_document():
    results = retrieve_articles(HELP_CENTER_DIR, "security authorization and provisioning notes")
    assert all(article["slug"] not in {"guardrails", "SKILL", "README"} for article in results)


def test_rag_uses_enabled_model_without_agent_notes_and_keeps_final_priority(monkeypatch):
    called = {}

    def fake_model(result, subject, message, matches, agent_notes):
        called["notes"] = agent_notes
        result["suggested_approach"] = "AI-grounded password reset guidance."
        result["ai_advisory_priority"] = "high"
        result["ai_priority_rationale"] = "The teacher cannot access the system."
        result["ai_mode"] = "openai_rag_refined"
        return result

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ENABLE_OPENAI_TRIAGE", "true")
    monkeypatch.setattr(main, "apply_model_assist", fake_model)
    result = rag_triage("Password reset", "A teacher forgot their password.")
    assert called["notes"] is None
    assert result["ai_mode"] == "openai_rag_refined"
    assert result["ai_advisory_priority"] == "high"
    assert result["priority"] == "low"


def test_model_failure_keeps_deterministic_priority(monkeypatch):
    import openai
    base = triage("Password reset", "A teacher forgot their password.")
    monkeypatch.setattr(openai, "OpenAI", lambda: (_ for _ in ()).throw(RuntimeError("model unavailable")))
    result = main.apply_model_assist(base, "Password reset", "A teacher forgot their password.", [], None)
    assert result["priority"] == "low"
    assert result["ai_advisory_priority"] is None
    assert result["ai_mode"] == "rule_based_rag_fallback"
