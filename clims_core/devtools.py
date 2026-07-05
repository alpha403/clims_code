"""Developer-workflow helpers: code review, bug reports, PR comments.

Pure prompt/report builders here; the CLI wires them to git/gh via the bash path.
"""
from __future__ import annotations

import platform


def review_prompt(diff: str) -> str:
    if not diff.strip():
        return ""
    return (
        "You are a meticulous code reviewer. Review the following git diff for "
        "correctness bugs, security issues, and clear style problems. Cite specific "
        "changed lines and be concise.\n\n```diff\n" + diff + "\n```"
    )


def bug_report(provider: str, model: str, transcript_tail: str, extra: str = "") -> str:
    return "\n".join([
        "# clims_code bug report",
        "",
        "## Environment",
        f"- python: {platform.python_version()}",
        f"- platform: {platform.platform()}",
        f"- provider/model: {provider}:{model}",
        "",
        "## What happened",
        extra or "<describe the issue>",
        "",
        "## Recent transcript",
        "```",
        transcript_tail[-4000:],
        "```",
    ])
