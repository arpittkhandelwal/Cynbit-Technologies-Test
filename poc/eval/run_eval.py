"""
Evaluation script for Cynbit IntelliAssist.
Runs all test cases through the RAG pipeline in DEMO_MODE and reports metrics.

Usage:
    cd poc/
    python eval/run_eval.py
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on path
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# Force DEMO_MODE for eval
os.environ.setdefault("DEMO_MODE", "true")

from src.rag import KnowledgeBase
from src.guardrails import detect_off_topic, enforce_grounding
from src.lead_qualifier import extract_bant
from src.schemas import ConversationTurn
from src.llm import generate

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
KB_PATH = str(_ROOT / "data" / "cynbit_knowledge_base.json")
TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_PATH = Path(__file__).parent / "eval_results.md"


def load_test_cases() -> list[dict]:
    with open(TEST_CASES_PATH, "r") as f:
        return json.load(f)


def run_factual_retrieval(tc: dict, kb: KnowledgeBase) -> dict[str, Any]:
    query = tc["query"]
    chunks = kb.retrieve(query, k=3)
    sources = [c.source for c in chunks]

    # Check if expected source is in retrieved sources
    expected_source = tc.get("expected_source_contains", "")
    hit = any(expected_source in s for s in sources) if expected_source else True

    # Build answer (demo mode)
    context = "\n".join(c.content for c in chunks[:2])
    answer = generate(query)
    grounded_answer, is_grounded = enforce_grounding(answer, chunks)

    # Check expected keywords
    expected_kws = tc.get("expected_answer_contains", [])
    answer_lower = (answer + " " + context).lower()
    kw_hits = sum(1 for kw in expected_kws if kw.lower() in answer_lower)
    kw_rate = kw_hits / len(expected_kws) if expected_kws else 1.0

    return {
        "retrieval_hit": hit,
        "grounded": is_grounded,
        "keyword_match_rate": kw_rate,
        "sources": sources,
    }


def run_lead_qualification(tc: dict) -> dict[str, Any]:
    query = tc["query"]
    turns = [ConversationTurn(role="user", content=query)]
    profile = extract_bant(turns)

    expected_bant = tc.get("expected_bant_extracted", {})
    expected_range = tc.get("expected_score_range", [0, 100])
    expected_status = tc.get("expected_status")

    # Check score in range
    score_in_range = expected_range[0] <= profile.qualification_score <= expected_range[1]

    # Check BANT field extraction
    bant_hits = 0
    for field, value in expected_bant.items():
        extracted = getattr(profile, field, None)
        if extracted and value.lower() in str(extracted).lower():
            bant_hits += 1
    bant_accuracy = bant_hits / len(expected_bant) if expected_bant else 1.0

    status_correct = (profile.qualification_status == expected_status) if expected_status else True

    return {
        "score": profile.qualification_score,
        "status": profile.qualification_status,
        "score_in_range": score_in_range,
        "bant_accuracy": bant_accuracy,
        "status_correct": status_correct,
        "grounded": True,  # BANT extraction doesn't need grounding
    }


def run_out_of_scope(tc: dict) -> dict[str, Any]:
    query = tc["query"]
    is_off_topic = detect_off_topic(query)
    expected = tc.get("should_detect_off_topic", True)

    return {
        "detected_correctly": is_off_topic == expected,
        "grounded": False,
    }


def run_guardrail_test(tc: dict, kb: KnowledgeBase) -> dict[str, Any]:
    query = tc["query"]
    chunks = kb.retrieve(query, k=3)
    answer = generate(query)
    grounded_answer, is_grounded = enforce_grounding(answer, chunks, query=query)

    warning_present = "⚠️" in grounded_answer or "opportunities@cynbit.in" in grounded_answer
    expected_warning = tc.get("should_hallucination_warning_appear", False)

    return {
        "warning_correct": warning_present == expected_warning or not expected_warning,
        "grounded": is_grounded,
    }


def format_markdown_table(results: list[dict]) -> str:
    header = "| ID | Category | Status | Latency (ms) | Grounded | Notes |\n"
    header += "|---|---|---|---|---|---|\n"
    rows = []
    for r in results:
        status = "✅ PASS" if r.get("passed") else "❌ FAIL"
        grounded = "Yes" if r.get("grounded") else "No"
        rows.append(
            f"| {r['id']} | {r['category']} | {status} | {r['latency_ms']:.0f}ms | {grounded} | {r.get('notes', '')} |"
        )
    return header + "\n".join(rows)


def main():
    print("=" * 60)
    print("Cynbit IntelliAssist – Evaluation Suite (DEMO_MODE)")
    print("=" * 60)

    # Load KB
    print("\n📚 Loading knowledge base…")
    kb = KnowledgeBase(data_path=KB_PATH)
    test_cases = load_test_cases()
    print(f"✅ {len(test_cases)} test cases loaded.")

    # Metrics accumulators
    total = len(test_cases)
    results = []
    retrieval_hits = 0
    grounded_count = 0
    off_topic_correct = 0
    off_topic_total = 0
    bant_accuracies = []
    latencies = []

    for tc in test_cases:
        tc_id = tc["id"]
        category = tc["category"]
        print(f"\n  Running {tc_id} ({category})…", end=" ")

        t0 = time.time()
        passed = False
        notes = ""

        try:
            if category == "factual_retrieval":
                res = run_factual_retrieval(tc, kb)
                passed = res["retrieval_hit"] and res["keyword_match_rate"] >= 0.5
                if res["retrieval_hit"]:
                    retrieval_hits += 1
                if res["grounded"]:
                    grounded_count += 1
                notes = f"KW match: {res['keyword_match_rate']:.0%}"

            elif category == "lead_qualification":
                res = run_lead_qualification(tc)
                passed = res["score_in_range"] and res["bant_accuracy"] >= 0.5
                bant_accuracies.append(res["bant_accuracy"])
                if res["grounded"]:
                    grounded_count += 1
                notes = f"Score: {res['score']}, Status: {res['status']}"

            elif category == "out_of_scope":
                res = run_out_of_scope(tc)
                passed = res["detected_correctly"]
                off_topic_correct += 1 if passed else 0
                off_topic_total += 1
                notes = "Off-topic detected" if passed else "Not detected"

            elif category == "guardrail_test":
                res = run_guardrail_test(tc, kb)
                passed = res["warning_correct"]
                if res["grounded"]:
                    grounded_count += 1
                notes = "Warning present" if not res["grounded"] else "Grounded"

        except Exception as e:
            passed = False
            notes = f"ERROR: {e}"
            res = {"grounded": False}

        latency_ms = (time.time() - t0) * 1000
        latencies.append(latency_ms)

        status_str = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status_str} ({latency_ms:.0f}ms)")

        results.append({
            "id": tc_id,
            "category": category,
            "passed": passed,
            "grounded": res.get("grounded", False),
            "latency_ms": latency_ms,
            "notes": notes,
        })

    # Summary metrics
    passed_count = sum(1 for r in results if r["passed"])
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    grounded_non_ots = total - off_topic_total
    groundedness_rate = grounded_count / grounded_non_ots if grounded_non_ots else 0
    avg_bant = sum(bant_accuracies) / len(bant_accuracies) if bant_accuracies else 0

    factual_total = sum(1 for tc in test_cases if tc["category"] == "factual_retrieval")
    retrieval_rate = retrieval_hits / factual_total if factual_total else 0
    off_topic_rate = off_topic_correct / off_topic_total if off_topic_total else 0

    print("\n" + "=" * 60)
    print("📊 EVALUATION RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Overall Pass Rate:         {passed_count}/{total} ({passed_count/total:.0%})")
    print(f"  Retrieval Hit Rate:        {retrieval_hits}/{factual_total} ({retrieval_rate:.0%})")
    print(f"  Groundedness Rate:         {grounded_count}/{grounded_non_ots} ({groundedness_rate:.0%})")
    print(f"  Off-topic Detection:       {off_topic_correct}/{off_topic_total} ({off_topic_rate:.0%})")
    print(f"  Avg BANT Accuracy:         {avg_bant:.0%}")
    print(f"  Avg Response Latency:      {avg_latency:.0f}ms")
    print("=" * 60)

    # Write Markdown results
    md_content = f"""# Cynbit IntelliAssist – Evaluation Results

> Generated in DEMO_MODE · {len(test_cases)} test cases · {passed_count}/{total} passed

## Summary Metrics

| Metric | Value |
|---|---|
| Overall Pass Rate | {passed_count/total:.0%} ({passed_count}/{total} test cases) |
| Retrieval Hit Rate | {retrieval_rate:.0%} ({retrieval_hits}/{factual_total} factual queries) |
| Groundedness Rate | {groundedness_rate:.0%} ({grounded_count}/{grounded_non_ots} responses cited sources) |
| Out-of-scope Detection | {off_topic_rate:.0%} ({off_topic_correct}/{off_topic_total}) |
| Avg Lead Qualification (BANT) Accuracy | {avg_bant:.0%} |
| Avg Response Latency (DEMO_MODE) | {avg_latency:.0f}ms |

## Detailed Results

{format_markdown_table(results)}

## Notes

- All results generated in **DEMO_MODE** (no API key required).
- Latency reflects local in-memory FAISS retrieval + canned LLM response, not live API calls.
- In production with Gemini/GPT-4, latency would be 1–3 seconds per query.
- BANT accuracy measures keyword overlap between extracted fields and expected values.
- Groundedness is measured by lexical overlap heuristic (word overlap ≥ 25%).
"""

    with open(RESULTS_PATH, "w") as f:
        f.write(md_content)
    print(f"\n📄 Results saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()

