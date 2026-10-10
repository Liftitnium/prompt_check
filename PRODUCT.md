# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Plain HTML/CSS/JS (no framework, no build step), served as static files by the same FastAPI process. Chosen by the user because the container (course Dockerfile template) cannot run a build step, and so there are no new Python dependencies.

## Users
The 8 engineers on the AI team of a Spanish e-commerce startup. Their customer-support assistant runs on ~20 prompts that they change weekly. They sit at a laptop before a prompt change goes live and need to know whether it breaks behaviour that worked before. Secondary viewer: the course grader evaluating the assignment.

## Product Purpose
PromptCheck is regression testing for LLM prompts. Engineers save each version of a prompt with a set of test cases, run a version through an LLM, and compare two runs to see exactly which test cases regressed. The run comparison gives a `ship` or `block` verdict. Success means a silent regression (wrong language, invalid JSON, missing refund policy) is caught before customers see it.

## Positioning
Deterministic, rule-based checks (contains, regex, valid JSON, ...) instead of an LLM judge, so a verdict is reproducible and free to compute (ADR-5). Prompt versions can't be changed after publishing, and every run snapshots what it tested, so old runs stay accurate (ADR-3).

## Operating Context
The workflow: create a prompt → publish versions (each change makes a new version, with a line diff between versions) → attach test cases (input variables + checks) → start a run (asynchronous: 202, then poll until completed/failed) → read per-case results (rendered prompt, output, which check passed or failed, latency, tokens) → compare a base run with a candidate run → decide ship or block. A completed run can be re-scored against the current checks without calling the LLM. By default the LLM is a deterministic fake that echoes the rendered prompt; a real Anthropic provider is optional through env vars. The JSON API and `/docs` stay available alongside the UI.

## Capabilities and Constraints
- Full workflow in the UI: prompts, versions, diffs, test cases (add/archive), runs, results, comparison, rescore.
- Test cases can't be edited, only archived and re-added. Prompts can't be deleted.
- Check types: contains, not_contains, equals, regex, max_length, valid_json, json_has_keys (from `GET /checks`).
- Single process, single container, SQLite, no build step, ~12 Python packages max. No auth: internal tool on a trusted network.
- Demo data ships in `promptcheck/prompts/seed.json`: prompt `refund-reply`, v1 (Spanish, mentions the refund policy) and v2 (English rewrite), 3 test cases. Comparing a v1 run with a v2 run gives `block` with 2 regressions.

## Evidence on Hand
Only the seeded demo data and whatever users enter. No customers, testimonials, metrics or logos exist; don't invent any.

## Product Principles
1. The verdict is the product: whether to ship must be clear at a glance and traceable to the exact case and check that failed.
2. Show what was actually tested: the snapshotted template, inputs, output and check details, never a reconstruction.
3. Nothing is silently overwritten: versions are immutable, test cases are archived rather than deleted, and re-scoring creates a new run.
4. Fast for people who already think in diffs and test results; the UI shouldn't hide the underlying API concepts.
