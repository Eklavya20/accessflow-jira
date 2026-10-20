import hashlib
import json
from pathlib import Path

import httpx
import pytest

from accessflow.config import SafetyError
from accessflow.domain import Policy
from accessflow.extraction import ExtractionCache, ExtractionSettings, GroqExtractor
from accessflow.extraction_eval import CORPUS, CORPUS_SHA256, evaluate, load_cases, main


def test_reviewed_corpus_has_40_cases_and_required_categories():
    assert hashlib.sha256(CORPUS.read_bytes()).hexdigest() == CORPUS_SHA256
    cases = load_cases()
    assert len(cases) == len({case.id for case in cases}) == 40
    assert {
        "structured",
        "informal",
        "missing_permission",
        "ambiguous_application",
        "privileged",
        "contradictory",
        "multiple_applications",
        "unknown_application",
        "irrelevant",
        "prompt_injection",
    } <= {case.category for case in cases}


def test_corpus_change_is_blocked_before_provider(monkeypatch, tmp_path):
    path = tmp_path / "private.json"
    path.write_text('{"synthetic_only":true,"cases":[]}', encoding="utf-8")
    monkeypatch.setattr("accessflow.extraction_eval.CORPUS", path)
    with pytest.raises(SafetyError, match="review and repin"):
        load_cases()


def test_baseline_only_evaluation_cannot_claim_ai_improvement():
    policy = Policy.load(Path(__file__).resolve().parents[1] / "config/policy.json")
    report = evaluate(load_cases(), policy)
    assert report["baseline"] == report["assisted"]
    assert report["baseline"]["field_correct"] == {
        "application": 40,
        "access_level": 25,
        "justification": 20,
    }
    assert not report["success_criteria_met"]
    assert report["provider"]["attempts"] == 0
    assert report["baseline"]["privileged_false_negatives"] == 2


def test_offline_provider_fixture_is_not_presented_as_live_evidence(tmp_path):
    policy = Policy.load(Path(__file__).resolve().parents[1] / "config/policy.json")
    cases = [case for case in load_cases() if case.id == "natural-01"]
    data = {
        "application": {"value": "GitHub", "evidence": "GitHub"},
        "access_level": {"value": "Read-only", "evidence": "read-only"},
        "justification": {"value": "review pull requests", "evidence": "review pull requests"},
        "missing": [],
        "ambiguities": [],
        "manual_review": False,
    }
    calls = []

    def server(req):
        calls.append(req)
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(data)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )

    cache = ExtractionCache(tmp_path / "cache.sqlite3")
    try:
        extractor = GroqExtractor(
            ExtractionSettings(
                _env_file=None, accessflow_llm_enabled=True, groq_api_key="offline-test-credential"
            ),
            cache,
            transport=httpx.MockTransport(server),
        )
        first = evaluate(cases, policy, extractor)
        second = evaluate(cases, policy, extractor)
    finally:
        cache.close()
    assert first["assisted"]["field_accuracy"] == 1
    assert not first["success_criteria_met"]  # One smoke case is not a 30+ case evaluation.
    assert first["provider"]["observed_total_tokens"] == 150
    assert second["provider"]["cache_hits"] == 1
    assert second["provider"]["attempts"] == 0
    assert second["provider"]["observed_total_tokens"] == 0
    assert len(calls) == 1


def test_live_cli_needs_explicit_synthetic_confirmation(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACCESSFLOW_LLM_ENABLED", "true")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert main(["--live"]) == 1
    assert "evaluation_blocked" in capsys.readouterr().out
    assert not (tmp_path / "reports/groq-extraction-cache.sqlite3").exists()


def test_cli_cannot_enable_groq_when_configuration_is_disabled(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ACCESSFLOW_LLM_ENABLED", "false")
    assert main(["--live", "--confirm-synthetic"]) == 1
    assert not (tmp_path / "reports").exists()
