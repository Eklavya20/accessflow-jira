"""Evaluate only the pinned synthetic corpus; no Jira calls or processing commands."""

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from accessflow.config import SafetyError
from accessflow.domain import Policy, RequestInput, digest
from accessflow.extraction import (
    FIELDS,
    PROMPT_VERSION,
    Extraction,
    ExtractionCache,
    ExtractionSettings,
    FieldName,
    GroqExtractor,
    assisted_decision,
    purpose_value,
)
from accessflow.parsing import classify

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evals/access_requests.json"
CORPUS_SHA256 = "dcc984064434712ff5d8eca56704a2cd917cb35b909614fc4574f2051d385d29"


class Expected(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    application: str | None
    access_level: str | None
    justification: str | None
    missing: list[str]
    privileged: bool
    outcome: str


class SyntheticCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    category: str
    summary: str
    description: str
    mapped_fields: dict[FieldName, str]
    requester_updates: list[str]
    expected: Expected

    def request(self):
        return RequestInput(
            issue_id="1",
            issue_key="SYNTHETIC-1",
            request_type_id="1",
            request_type="Synthetic evaluation only",
            status="Not connected to Jira",
            **self.model_dump(
                include={"summary", "description", "mapped_fields", "requester_updates"}
            ),
        )


def load_cases():
    raw = CORPUS.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORPUS_SHA256:
        raise SafetyError("Synthetic corpus changed; review and repin before external evaluation")
    data = json.loads(raw)
    if data.get("synthetic_only") is not True:
        raise SafetyError("Only the reviewed synthetic corpus may be evaluated")
    cases = [SyntheticCase.model_validate(row) for row in data["cases"]]
    if len(cases) < 30 or len({case.id for case in cases}) != len(cases):
        raise SafetyError("Invalid synthetic evaluation manifest")
    return cases


def normalized(value):
    return purpose_value(value).rstrip(".!?").casefold() if isinstance(value, str) else value


def score(cases, decisions):
    n = len(cases)
    field_correct = Counter()
    incorrect_present = 0
    missing_matches = outcomes = privileged_tp = privileged_fn = privileged_fp = unsafe_ready = 0
    for case, decision in zip(cases, decisions, strict=True):
        gold = case.expected
        for field in FIELDS:
            value, expected = getattr(decision, field), getattr(gold, field)
            correct = normalized(value) == normalized(expected)
            field_correct[field] += correct
            incorrect_present += int(not correct and value is not None)
        missing_matches += set(decision.missing) == set(gold.missing)
        outcomes += decision.outcome == gold.outcome
        privileged_tp += gold.privileged and decision.privileged
        privileged_fn += gold.privileged and not decision.privileged
        privileged_fp += not gold.privileged and decision.privileged
        unsafe_ready += gold.privileged and decision.outcome == "ready_for_human_fulfillment"
    positives = sum(case.expected.privileged for case in cases)
    return {
        "cases": n,
        "field_correct": dict(field_correct),
        "field_accuracy": sum(field_correct.values()) / (3 * n),
        "all_three_fields_correct": sum(
            all(
                normalized(getattr(decision, field)) == normalized(getattr(case.expected, field))
                for field in FIELDS
            )
            for case, decision in zip(cases, decisions, strict=True)
        ),
        "missing_set_accuracy": missing_matches / n,
        "outcome_accuracy": outcomes / n,
        "incorrect_non_null_fields": incorrect_present,
        "privileged_labelled_cases": positives,
        "privileged_true_positives": privileged_tp,
        "privileged_false_negatives": privileged_fn,
        "privileged_false_positives": privileged_fp,
        "privileged_recall": privileged_tp / positives if positives else None,
        "privileged_cases_marked_ready": unsafe_ready,
        "manual_triage_rate": sum(d.outcome == "manual_triage" for d in decisions) / n,
        "privileged_review_rate": sum(d.outcome == "privileged_review" for d in decisions) / n,
    }


def evaluate(cases, policy, extractor=None, *, pause_seconds=0, progress=None):
    rows, baseline, assisted, guard_only, results = [], [], [], [], []
    for index, case in enumerate(cases):
        request = case.request()
        before = classify(request, policy)
        guarded, _ = assisted_decision(
            request,
            policy,
            Extraction(
                application=None,
                access_level=None,
                justification=None,
                missing=[],
                ambiguities=[],
                manual_review=False,
            ),
        )
        result = extractor.extract(request, policy, synthetic_confirmed=True) if extractor else None
        after, issues = assisted_decision(request, policy, result.extraction if result else None)
        baseline.append(before)
        assisted.append(after)
        guard_only.append(guarded)
        if result:
            results.append(result)
        raw = result.extraction if result else None
        raw_errors = [
            field
            for field in FIELDS
            if raw
            and getattr(raw, field) is not None
            and normalized(
                (policy.canonical(getattr(raw, field).value, field) or getattr(raw, field).value)
                if field != "justification"
                else getattr(raw, field).value
            )
            != normalized(getattr(case.expected, field))
        ]
        rows.append(
            {
                "id": case.id,
                "category": case.category,
                "expected": case.expected.model_dump(),
                "baseline": before.model_dump(),
                "assisted": after.model_dump(),
                "provider": result.model_dump() if result else {"status": "not_called"},
                "guard_issues": issues,
                "raw_candidate_errors_against_labels": raw_errors,
            }
        )
        if progress:
            progress(case.id, result.status if result else "baseline")
        if result and result.attempts and pause_seconds and index + 1 < len(cases):
            time.sleep(pause_seconds)
    a, b = score(cases, baseline), score(cases, assisted)
    safety_regressions = [
        case.id
        for case, before, after in zip(cases, baseline, assisted, strict=True)
        if (before.privileged and not after.privileged)
        or (case.expected.privileged and after.outcome == "ready_for_human_fulfillment")
    ]
    gain = b["field_accuracy"] - a["field_accuracy"]
    complete = bool(results) and len(results) == len(cases) and all(r.extraction for r in results)
    success = (
        complete
        and len(cases) >= 30
        and gain >= 0.10
        and not safety_regressions
        and b["privileged_false_negatives"] <= a["privileged_false_negatives"]
        and b["incorrect_non_null_fields"] <= a["incorrect_non_null_fields"]
    )
    latencies = sorted(r.latency_seconds for r in results if r.attempts)
    observed = [r for r in results if r.attempts]
    return {
        "created_utc": datetime.now(UTC).isoformat(),
        "synthetic_only": True,
        "corpus_sha256": CORPUS_SHA256,
        "policy_sha256": digest(policy.model_dump()),
        "prompt_version": PROMPT_VERSION,
        "mode": "provider_evaluation" if extractor else "baseline_only",
        "baseline": a,
        "guard_only": score(cases, guard_only),
        "assisted": b,
        "field_accuracy_gain": gain,
        "safety_regressions": safety_regressions,
        "complete_provider_coverage": complete,
        "success_criteria_met": success,
        "recommendation": (
            "Measured prototype improvement; keep disabled pending human/privacy review and "
            "a separate worker-integration decision."
            if success
            else "Leave disabled: improvement/safety/provider-coverage gate not met."
        ),
        "provider": {
            "model": extractor.settings.groq_model if extractor else None,
            "status_counts": dict(Counter(r.status for r in results)),
            "attempts": sum(r.attempts for r in results),
            "cache_hits": sum(r.cache_hit for r in results),
            "latency_seconds_p50": statistics.median(latencies) if latencies else None,
            "latency_seconds_p95": latencies[math.ceil(len(latencies) * 0.95) - 1]
            if latencies
            else None,
            "input_token_estimate": sum(r.estimated_input_tokens * r.attempts for r in results),
            "token_estimate_method": (
                "UTF-8 serialized request bytes / 4, rounded up; not a tokenizer"
            ),
            "observed_prompt_tokens": sum(r.observed_prompt_tokens or 0 for r in observed),
            "observed_completion_tokens": sum(r.observed_completion_tokens or 0 for r in observed),
            "observed_total_tokens": sum(r.observed_total_tokens or 0 for r in observed),
            "attempts_without_observed_usage": sum(
                r.attempts - int(r.observed_total_tokens is not None) for r in observed
            ),
            "raw_incorrect_non_null_candidates": sum(
                len(row["raw_candidate_errors_against_labels"]) for row in rows
            ),
        },
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Use Groq for the pinned corpus only")
    parser.add_argument("--confirm-synthetic", action="store_true")
    parser.add_argument("--case", help="One case ID from the fixed synthetic corpus")
    parser.add_argument("--pause-seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, default=Path("reports/groq-evaluation.json"))
    parser.add_argument("--cache", type=Path, default=Path("reports/groq-extraction-cache.sqlite3"))
    args = parser.parse_args(argv)
    cache = None
    try:
        if not math.isfinite(args.pause_seconds) or not 0 <= args.pause_seconds <= 60:
            raise SafetyError("Pause must be between zero and sixty seconds")
        cases = load_cases()
        if args.case:
            cases = [case for case in cases if case.id == args.case]
            if not cases:
                raise SafetyError("Unknown synthetic case ID")
        policy = Policy.load(ROOT / "config/policy.json")
        settings = ExtractionSettings()
        extractor = None
        if args.live:
            if not args.confirm_synthetic or not settings.accessflow_llm_enabled:
                raise SafetyError(
                    "Live evaluation requires synthetic confirmation and enabled config"
                )
            if not settings.groq_api_key.get_secret_value():
                raise SafetyError("Configure GROQ_API_KEY locally; never paste it")
            cache = ExtractionCache(args.cache)
            extractor = GroqExtractor(settings, cache)
        report = evaluate(
            cases,
            policy,
            extractor,
            pause_seconds=args.pause_seconds,
            progress=(
                lambda case_id, status: print(
                    json.dumps({"case": case_id, "status": status}), flush=True
                )
            )
            if args.live
            else None,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "rows"}))
        return 0
    except (SafetyError, ValidationError, OSError, sqlite3.Error) as exc:
        # Never expose provider bodies, inputs, credentials or Pydantic input values.
        print(json.dumps({"event": "evaluation_blocked", "error_type": type(exc).__name__}))
        return 1
    finally:
        if cache:
            cache.close()


if __name__ == "__main__":
    raise SystemExit(main())
