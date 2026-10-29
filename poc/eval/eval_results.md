# Cynbit IntelliAssist – Evaluation Results

> Generated in DEMO_MODE · 15 test cases · 15/15 passed

## Summary Metrics

| Metric | Value |
|---|---|
| Overall Pass Rate | 100% (15/15 test cases) |
| Retrieval Hit Rate | 100% (5/5 factual queries) |
| Groundedness Rate | 83% (10/12 responses cited sources) |
| Out-of-scope Detection | 100% (3/3) |
| Avg Lead Qualification (BANT) Accuracy | 95% |
| Avg Response Latency (DEMO_MODE) | 230ms |

## Detailed Results

| ID | Category | Status | Latency (ms) | Grounded | Notes |
|---|---|---|---|---|---|
| tc001 | factual_retrieval | ✅ PASS | 2076ms | Yes | KW match: 100% |
| tc002 | factual_retrieval | ✅ PASS | 444ms | Yes | KW match: 100% |
| tc003 | factual_retrieval | ✅ PASS | 488ms | Yes | KW match: 100% |
| tc004 | factual_retrieval | ✅ PASS | 9ms | Yes | KW match: 100% |
| tc005 | factual_retrieval | ✅ PASS | 9ms | No | KW match: 100% |
| tc006 | lead_qualification | ✅ PASS | 0ms | Yes | Score: 57, Status: warm |
| tc007 | lead_qualification | ✅ PASS | 0ms | Yes | Score: 80, Status: hot |
| tc008 | lead_qualification | ✅ PASS | 0ms | Yes | Score: 0, Status: unqualified |
| tc009 | lead_qualification | ✅ PASS | 0ms | Yes | Score: 75, Status: hot |
| tc010 | out_of_scope | ✅ PASS | 0ms | No | Off-topic detected |
| tc011 | out_of_scope | ✅ PASS | 0ms | No | Off-topic detected |
| tc012 | out_of_scope | ✅ PASS | 0ms | No | Off-topic detected |
| tc013 | guardrail_test | ✅ PASS | 284ms | Yes | Grounded |
| tc014 | guardrail_test | ✅ PASS | 37ms | Yes | Grounded |
| tc015 | guardrail_test | ✅ PASS | 98ms | No | Warning present |

## Notes

- All results generated in **DEMO_MODE** (no API key required).
- Latency reflects local in-memory FAISS retrieval + canned LLM response, not live API calls.
- In production with Gemini/GPT-4, latency would be 1–3 seconds per query.
- BANT accuracy measures keyword overlap between extracted fields and expected values.
- Groundedness is measured by lexical overlap heuristic (word overlap ≥ 25%).
