# Groq extraction prototype: measured review

Evaluated October 20, 2026 on `feature/groq-request-extraction`. **Keep disabled. Do not integrate with the Jira worker yet.** The prototype improves candidate extraction on this synthetic sample, but its readiness gate fails and it increases manual triage.

## Business case and measured result

**Problem:** employees describe access needs informally. **Existing limitation:** the deterministic parser recognizes catalogue applications in prose, but expects labelled permissions and business justifications. **Enhancement:** Groq proposes source-backed fields; local guards validate them and the existing classifier makes the decision. **Measured improvement:** 85/120 correct fields became 113/120. **Remaining risk:** raw candidate errors, provider failures, conservative over-referral and unreviewed external-data privacy.

Forty authored synthetic cases cover structured/informal requests, absent fields, ambiguous/unknown applications, privileged intent, contradictions, multiple applications, irrelevant text, requester corrections and injection attempts. Labels were written and the corpus hash pinned before the full provider run. One exploratory synthetic preflight exposed purpose-prefix segmentation; deterministic connector normalization was added before that run. Gold labels were not changed to match model output. These are development examples, not an independent held-out benchmark or production accuracy estimate.

| Measure | Original parser | Guard-only control | Groq + guards |
| --- | ---: | ---: | ---: |
| Field correctness, including correct absence | 85/120 (70.8%) | 85/120 (70.8%) | 113/120 (94.2%) |
| Application fields correct | 40/40 | 40/40 | 40/40 |
| Permission fields correct | 25/40 | 25/40 | 39/40 |
| Justification fields correct | 20/40 | 20/40 | 34/40 |
| All three fields correct | 19/40 | 19/40 | 34/40 |
| Exact missing-field set | 47.5% | 47.5% | 85.0% |
| Outcome matches label | 55.0% | 70.0% | 92.5% |
| Privileged indications detected | 8/10 | 10/10 | 10/10 |
| Privileged cases marked ready | 0 | 0 | 0 |
| Incorrect non-null fields in decisions | 0 | 0 | 0 |
| Manual-triage rate | 32.5% | 47.5% | 57.5% |

The application field shows no measured AI gain. The privileged-detection gain comes from deterministic review guards for uncatalogued sensitive intent, **not the model**. Those guards exist only in this prototype; the operational classifier is unchanged. Baseline cases with an unflagged sensitive term still required missing information/manual triage and were never marked ready. The model supplied eight incorrect non-null raw candidates against the labels; the guarded decisions accepted no incorrect non-null field on this sample. This is not proof that hallucinations or prompt injection have been eliminated.

## Provider reliability, latency and usage

The first 40-case run reused one earlier preflight response and made 39 new requests: 37 extracted successfully and two returned HTTP 400. Both failures fell back to the original deterministic classifier. Initial provider coverage was 38/40 including the preflight. Its decision results were replayed offline through the final guard after additional conflict/error-handling checks; scores were unchanged. The original run and both failures are preserved.

- First full run: API latency p50 **0.487 s**, p95 **1.130 s**, over its 39 outbound attempts, including errors and excluding the cache hit and deliberate ten-second pacing. This is not end-to-end worker latency or a service-level commitment.
- Including the separate preflight: **40 attempts**, **22,222 observed prompt tokens**, **6,201 observed completion tokens**, **28,423 observed total tokens** on successful responses. Two failed attempts supplied no usage; their billing/token use is unknown.
- Input estimate for those attempts: **27,740 tokens**, from serialized UTF-8 bytes divided by four and rounded up. This is a rough request-size estimate, not a tokenizer or completion forecast. Observed completion usage includes whatever the provider reports; no reasoning text is saved.
- A fresh-process repeat reused 38 successful entries and made two attempts for the previously failed cases. One recovered; the requester-correction case again returned HTTP 400 with allowlisted code `json_validate_failed`. It observed **789** additional tokens and one attempt without usage. Its field/safety scores were unchanged. The two-pass observed total plus preflight is **29,212 tokens**; three failed attempts remain unaccounted for.

The readiness gate was declared before the full run: at least 30 cases, complete validated provider coverage, at least ten percentage points of field improvement, no privileged downgrade/unsafe-ready regression, and no increase in incorrect non-null decision fields. Improvement and the sampled safety conditions pass; complete provider coverage fails. The result is **leave disabled**. Even a future passing synthetic gate would still require human review, privacy approval, wider evaluation and a separate integration decision.

## Boundaries and implementation

- `extraction.py` contains a separate settings model, strict Pydantic output schema, fixed HTTPS Groq endpoint, bounded timeouts/retries, a synthetic response cache and grounding/review guards. Existing HTTPX/Pydantic dependencies are reused.
- `extraction_eval.py` reads only the hash-pinned bundled corpus. There is no arbitrary-file/text input or Jira client. Model inputs contain synthetic summary/description/mapped fields/requester corrections and catalogue vocabulary; labels, Jira identities and credentials are not sent as request content.
- The worker, ingestion, processor, original domain/parser and Jira write gates have no extraction hook. Enabling the prototype setting cannot enable worker AI or Jira writes.
- All JSON object properties are required, closed to extras and nullable where appropriate. Strict schema adherence is followed by local validation, exact source-quote checks, catalogue matching, explicit-field precedence and purpose-clause checks. Valid JSON alone grants no authority.
- Conflicts, multiple applications/levels, ambiguous candidates, instruction-like content and sensitive unknown roles require human review. Model uncertainty can add a review requirement. It cannot remove deterministic privileged flags, grant permission, decide approval, change status/assignment or send comments. No tools/tool choices are supplied; any returned tool call is rejected.
- Provider failures, invalid/refused/truncated output, excessive waits and corrupt cache reads fall back to the exact original decision. Retry-After is respected; permanent 400/401/403 responses are not automatically retried. A later explicitly launched evaluation may retry an unsuccessful uncached case.
- Cache identity includes source text, model, prompt version, schema and the vocabulary sent to the model. Only validated successful responses are cached; facts are re-grounded and classified under the current deterministic policy on every read. Policy decisions and provider usage are not replayed as new observations. There is no exactly-once inference/billing guarantee after a timeout.

Source quotes establish provenance, not truth or business suitability. The purpose-clause and instruction-pattern checks are deliberately limited; two clearly useful purpose phrases still required manual review. Catalogue-only grounding rejects unconfigured synonyms such as `view` and `write` rather than silently assigning a permission. These trade-offs should be reviewed before expanding scope.

## Reproduce and demonstrate

From the repository root after installing the locked development environment:

```powershell
# No provider key or network required:
.\.venv\Scripts\python.exe -m accessflow.extraction_eval --output reports/groq-baseline.json
.\.venv\Scripts\python.exe scripts/check.py
```

Configure `GROQ_API_KEY` privately in the process environment or ignored `.env`; keep the saved `ACCESSFLOW_LLM_ENABLED=false`. Default `GROQ_MODEL=openai/gpt-oss-20b`. A live run requires both synthetic confirmation and an enabled process setting:

```powershell
$previousLlm = $env:ACCESSFLOW_LLM_ENABLED
try {
    $env:ACCESSFLOW_LLM_ENABLED = 'true'
    .\.venv\Scripts\python.exe -m accessflow.extraction_eval --live --confirm-synthetic
} finally {
    if ($null -eq $previousLlm) {
        Remove-Item Env:ACCESSFLOW_LLM_ENABLED -ErrorAction SilentlyContinue
    } else { $env:ACCESSFLOW_LLM_ENABLED = $previousLlm }
}
```

Use `--case natural-01` to demonstrate the same source in baseline and live modes: **“Please give me read-only GitHub access so I can review pull requests.”** The original parser finds GitHub and asks for permission level/justification. The assisted path grounds `Read-only` and the exact source phrase `review pull requests`, then the deterministic classifier returns ready for **human** fulfillment. No approval or access grant occurs. For `multiple-01`, application choice remains unresolved and requires manual review.

`reports/groq-extraction-cache.sqlite3` is a separate ignored synthetic cache; it is not the Jira action database. Repeating unchanged successful inputs, including after a fresh process, reuses responses with zero new model calls for those entries. Failed cases can make new attempts. Do not delete the operational journal to manipulate an evaluation.

Reviewed synthetic evidence: [corpus](../evals/access_requests.json), [first run with failures](../evals/groq_first_run.json), [fresh-process repeat](../evals/groq_restart_run.json). Local raw originals, preflight, cache and offline JUnit remain ignored under `reports/`. The regression suite now has **252 cases**: the original 186 plus 66 focused prototype cases. Provider evaluation is explicit and separate from offline CI; no Groq/Jira secrets are needed by CI.

Groq's current primary references: [strict structured output and supported models](https://console.groq.com/docs/structured-outputs), [model catalogue](https://console.groq.com/docs/models), [rate-limit headers](https://console.groq.com/docs/rate-limits), [OpenAI-compatible endpoint](https://console.groq.com/docs/openai). Actual HTTP 400 observations above qualify any provider schema-reliability claim.
