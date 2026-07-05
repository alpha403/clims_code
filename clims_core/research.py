"""Deep-research harness — fan-out search → parallel fetch → extract → synthesize.

Mirrors the structured deep-research pattern: generate diverse queries, search them
in parallel, fetch the top sources concurrently, pull relevant notes from each, then
synthesize a cited report. Optional adversarial verification of the draft.

All external effects are injected (search_fn / fetch_fn / llm_fn) so the harness is
fully unit-testable without network or a model.
"""
from __future__ import annotations

from typing import Callable

from clims_core.orchestrate import parallel

# search_fn(query) -> list[{"url","title","snippet"}]
# fetch_fn(url) -> str (page text)
# llm_fn(prompt) -> str
SearchFn = Callable[[str], list]
FetchFn = Callable[[str], str]
LLMFn = Callable[[str], str]

MAX_PAGE_CHARS = 6000


def _gen_queries(question: str, llm_fn: LLMFn, n: int) -> list[str]:
    prompt = (
        f"Break this research question into {n} diverse, specific web-search queries "
        f"that together cover it well. Output ONE query per line, no numbering, no extra text.\n\n"
        f"Question: {question}"
    )
    try:
        out = llm_fn(prompt)
    except Exception:
        out = ""
    queries = [ln.strip(" -*\t").strip() for ln in out.splitlines() if ln.strip()]
    queries = [q for q in queries if q][:n]
    return queries or [question]


def _dedupe_urls(hit_lists: list, max_sources: int) -> list[str]:
    seen, urls = set(), []
    for hits in hit_lists:
        for h in (hits or []):
            url = (h or {}).get("url", "")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
                if len(urls) >= max_sources:
                    return urls
    return urls


def _extract(question: str, url: str, page: str, llm_fn: LLMFn) -> str:
    if not page:
        return ""
    prompt = (
        "From the source text below, extract ONLY the facts relevant to the question, "
        "as terse bullet points. If nothing is relevant, reply 'NONE'.\n\n"
        f"Question: {question}\nSource URL: {url}\n\nSource text:\n{page[:MAX_PAGE_CHARS]}"
    )
    try:
        return llm_fn(prompt).strip()
    except Exception:
        return ""


def _synthesize(question: str, sourced_notes: list, llm_fn: LLMFn) -> str:
    blocks = []
    for i, (url, notes) in enumerate(sourced_notes, 1):
        if notes and notes.strip().upper() != "NONE":
            blocks.append(f"[{i}] {url}\n{notes}")
    if not blocks:
        return "No usable sources were found for this question."
    corpus = "\n\n".join(blocks)
    prompt = (
        "Write a clear, well-organized answer to the question using ONLY the sourced "
        "notes below. Cite sources inline as [n] matching the numbers. Be accurate and "
        "concise; do not invent facts not present in the notes. End with a 'Sources:' "
        "list mapping [n] to URLs.\n\n"
        f"Question: {question}\n\nSourced notes:\n{corpus}"
    )
    try:
        return llm_fn(prompt).strip()
    except Exception as e:
        return f"(synthesis failed: {e})"


def _revise(question: str, report: str, critique: str, llm_fn: LLMFn) -> str:
    prompt = (
        "Revise the research answer to fix the issues the fact-checker raised, using "
        "ONLY information already present (do not invent new facts). Keep the [n] "
        "citations and the Sources list. Output only the revised answer.\n\n"
        f"Question: {question}\n\nFact-checker issues:\n{critique}\n\nCurrent answer:\n{report}"
    )
    try:
        return llm_fn(prompt).strip() or report
    except Exception:
        return report


def _verify(question: str, report: str, llm_fn: LLMFn) -> str:
    prompt = (
        "You are a skeptical fact-checker. Review the research answer below for claims "
        "that are unsupported by its own cited sources, internal contradictions, or gaps. "
        "List concrete issues as bullets, or reply 'No major issues found.'\n\n"
        f"Question: {question}\n\nAnswer:\n{report}"
    )
    try:
        return llm_fn(prompt).strip()
    except Exception:
        return ""


def deep_research(
    question: str,
    *,
    search_fn: SearchFn,
    fetch_fn: FetchFn,
    llm_fn: LLMFn,
    max_queries: int = 4,
    max_sources: int = 6,
    verify: bool = True,
    revise: bool = True,
    on_log: Callable[[str], None] | None = None,
    max_workers: int = 8,
) -> dict:
    log = on_log or (lambda m: None)

    log("generating search queries…")
    queries = _gen_queries(question, llm_fn, max_queries)
    log(f"queries: {queries}")

    log("searching (parallel)…")
    hit_lists = parallel([(lambda q=q: search_fn(q)) for q in queries], max_workers)
    urls = _dedupe_urls(hit_lists, max_sources)
    log(f"{len(urls)} sources: {urls}")

    log("fetching sources (parallel)…")
    pages = parallel([(lambda u=u: fetch_fn(u)) for u in urls], max_workers)

    log("extracting notes (parallel)…")
    notes = parallel(
        [(lambda u=u, p=p: _extract(question, u, p, llm_fn)) for u, p in zip(urls, pages)],
        max_workers,
    )

    log("synthesizing report…")
    report = _synthesize(question, list(zip(urls, notes)), llm_fn)

    verification = ""
    revised = False
    if verify and report:
        log("verifying (adversarial)…")
        verification = _verify(question, report, llm_fn)
        if revise and verification and "no major issues" not in verification.lower():
            log("revising report to address fact-check…")
            report = _revise(question, report, verification, llm_fn)
            revised = True

    return {
        "question": question,
        "queries": queries,
        "sources": urls,
        "report": report,
        "verification": verification,
        "revised": revised,
    }
