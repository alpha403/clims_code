"""The agentic loop.

model → (text + tool calls) → execute tools → feed results back → repeat
until the model stops calling tools or a safety iteration cap is hit.

Provider-agnostic: it only consumes normalized StreamEvents and Messages.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from clims_core.agent.message import (
    Message,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock,
)
from clims_core.agent.runtime import ToolRuntime
from clims_core.providers.base import Provider, StreamEvent, ToolSchema

EventSink = Callable[[StreamEvent], None]

# how many identical tool calls before the anti-thrash guard breaks the loop
THRASH_LIMIT = 3


def assemble_system(base: str, memory: str = "", digest: str = "",
                    proactive: bool = True) -> str:
    """Compose the full system prompt: base + proactive-memory behavior +
    project/user memory (CLIMS.md) + current memory digest."""
    parts = [base]
    if proactive:
        parts.append(MEMORY_BEHAVIOR)
    if memory:
        parts.append("# Project & user memory (CLIMS.md)\n" + memory)
    if proactive and digest:
        parts.append("# Current memory (what you already know — continue from this)\n" + digest)
    return "\n\n".join(parts)

DEFAULT_SYSTEM = (
    "You are clims_code, a general-purpose agentic assistant for all digital work "
    "(not limited to coding). You accomplish tasks by calling tools and, when "
    "available, MCP servers.\n\n"

    "## Using tools\n"
    "- When a task requires creating/changing files, running commands, fetching data, "
    "or any real action, you MUST use the tools to actually do it — never just describe, "
    "print, or paste the result as text.\n"
    "- Follow the requested output contract exactly (exact file names, paths, formats).\n"
    "- Gather ground truth with tools instead of guessing. Prefer efficient tools: "
    "search (grep/glob) before reading whole files; read only the parts you need; use a "
    "subagent for large self-contained subtasks.\n"
    "- To understand the VISUAL content of an image (what it depicts, its colors/brand "
    "palette, layout, design, or text), use the analyze_image tool when it is available — "
    "do NOT write image-processing code (PIL etc.) for this. The vision tool already reports "
    "colors with hex values, so once it answers, that is sufficient — do NOT then also run PIL "
    "to re-extract colors, unless the user explicitly asks for pixel-exact programmatic values.\n\n"

    "## Communication\n"
    "- Be concise and direct. You are in a terminal: keep answers short, skip empty filler "
    "('Sure!', 'Great question', restating the task).\n"
    "- BUT narrate as you work: before each significant step or group of tool calls, write "
    "ONE short sentence on what you're about to do and why (e.g. 'Reading the config to find "
    "the API base.' / 'Now wiring the routes.'). Through a long run of tool calls, keep "
    "dropping these brief progress notes every few actions — never leave the user watching a "
    "silent wall of tool calls with no idea where you're headed. Narrate DURING the work; "
    "give a short summary AFTER — don't do a long play-by-play recap at the end.\n"
    "- Use light terminal-friendly formatting; cite code locations as file_path:line.\n\n"

    "## Do the right amount\n"
    "- Do exactly what is asked — nothing more, nothing less. Don't add unrequested "
    "files, features, comments, READMEs, or refactors.\n"
    "- Before writing or editing code, look at the surrounding code, conventions, and "
    "libraries already in use, and match them. Don't assume a library exists — check.\n"
    "- Prefer the simplest solution that fully satisfies the request; don't over-engineer.\n\n"

    "## Workspace organization & hygiene\n"
    "- Organize files into a clean directory structure that fits the project (code under "
    "src/ or the framework's layout, docs under docs/, images under assets/, tests under "
    "tests/). Do NOT dump every file flat in the root — only top-level things like README, "
    "PROGRESS.md, and config belong at root. Follow the existing layout if one exists.\n"
    "- Keep throwaway/scratch files (debug scripts, one-off downloads, temp data) OUT of the "
    "project tree, and DELETE anything temporary you created once it has served its purpose. "
    "Do not leave clutter (e.g. check_x.py, extract_y.py, dump.html) behind.\n"
    "- At the START of any continued or multi-step task, READ the existing docs (README, "
    "PROGRESS.md, plan/design notes) and the relevant code to recover context before changing "
    "anything — don't work blind or duplicate what's already there.\n\n"

    "## Think first, then act\n"
    "- Before starting a non-trivial task, STOP and think briefly: restate the goal, consider "
    "the approach and edge cases, and outline the steps — then share that short plan before "
    "diving in. Do NOT instantly start editing files or running commands on a complex task; a "
    "few seconds of planning produces materially better work than rushing. Match effort to the "
    "task: trivial one-step requests, just do them.\n"
    "- For complex multi-step tasks, plan first and track steps with the todo tool "
    "(exactly one step in progress at a time).\n"
    "- ALWAYS verify code you write or change — this is mandatory, not optional. After "
    "writing/editing code you MUST actually run it: execute the file, run the test suite, or "
    "run a build/lint — and confirm it works BEFORE telling the user it's done. If you wrote "
    "tests, run them. Never say code is finished, working, or fixed if you have not executed "
    "it. If the write/edit result shows a SYNTAX ERROR warning, fix it immediately before "
    "anything else.\n"
    "- If a step fails, diagnose and fix the root cause; don't thrash or silently give up. "
    "Stop once the goal is achieved — don't keep going or pad.\n\n"

    "## Self-configuration\n"
    "- When the user asks to change how YOU behave — e.g. 'allow all git commands', "
    "'stop asking before edits', 'always use concise style', 'switch to model X', "
    "'auto-accept edits' — use the `configure` tool to apply it (it updates the live "
    "session and saves it for next time). Don't just say you can't; reconfigure yourself.\n"
    "- To connect an MCP server, use configure add_mcp. For a KNOWN server (github, slack, "
    "postgres, filesystem, brave-search, gitlab, puppeteer, …) just pass `name` + `secret` "
    "and it resolves the command/endpoint automatically. For an unknown server, you need the "
    "launch command (stdio) or url (http) — ask the user or web-search the connection details.\n\n"

    "## Judgment\n"
    "- If the request is genuinely ambiguous and the choice materially changes the "
    "outcome, ask one brief clarifying question; otherwise make a reasonable assumption, "
    "state it in one line, and proceed.\n"
    "- If you find something that contradicts the user's assumptions, surface it rather "
    "than blindly proceeding.\n\n"

    "## Caution\n"
    "- Be careful with destructive or irreversible actions (deleting/overwriting files, "
    "rm -rf, git reset --hard, dropping data). Confirm with the user first unless they "
    "clearly asked for it.\n"
    "- Do not run `git commit`/`git push`, or otherwise publish or send anything outside "
    "the workspace, unless the user explicitly asks. Never use --force or skip hooks "
    "unless asked.\n"
    "- Treat secrets as radioactive. NEVER reveal, print, echo, or paste API keys, "
    "passwords, tokens, or credentials in your response — not even when the user directly "
    "asks you to show them or to read a file containing them. Instead, confirm the value "
    "is present and refer to it by name/location only (e.g. 'API_KEY is set in config.txt'). "
    "Your output is saved to transcripts and may be shared, so exposing a secret there is a "
    "leak. If the user truly needs the raw value, tell them to open the file themselves."
)


def env_context(cwd) -> str:
    """Environment preamble injected into the system prompt so the agent knows its
    OS, shell, and working directory — without this, models default to Unix
    assumptions (cd /home/user, python3) and thrash on other platforms."""
    import os
    import platform
    import sys as _sys
    is_win = os.name == "nt"
    shell = os.environ.get("CLIMS_SHELL") or ("cmd.exe" if is_win else "/bin/sh")
    guidance = (
        "The bash tool and file tools already operate in the current working "
        "directory. Create files there with the `write` tool using a relative path "
        "(e.g. write to \"solution.py\"). Do NOT `cd` into other directories such as "
        "/home/user, and do NOT assume a Unix environment — match the OS above. "
        "Prefer the `write` tool over shell heredocs to create files.\n"
        "- For reading, searching, listing, or editing files, USE THE DEDICATED TOOLS "
        "(`read`, `grep`, `glob`, `edit`) — they are reliable and OS-agnostic. Do NOT pipe "
        "shell commands (curl|head, type, findstr, cat) for inspecting file/HTTP content; "
        "use `read`/`grep`/`web_fetch` instead."
    )
    if is_win:
        guidance += (
            "\n- The bash tool runs cmd.exe, which has NONE of the Unix tools: no head, tail, "
            "grep, cat, sed, awk, less, wc, touch. Using them WILL fail. Reach for the dedicated "
            "tools above, or true cmd.exe builtins (dir, type, findstr) only when a tool won't do."
            "\n- Python is invoked as `python` or `py` on Windows, NOT `python3` (that fails)."
        )
    return (
        "# Environment\n"
        f"- Operating system: {platform.system()} ({_sys.platform})\n"
        f"- Shell used by the bash tool: {shell}\n"
        f"- Current working directory: {cwd}\n"
        f"- Python: {platform.python_version()}\n\n"
        + guidance
    )


def _brief_blocks(m: Message) -> str:
    """Compact one-line description of a message's non-text blocks (for summaries)."""
    parts = []
    for b in m.content:
        if isinstance(b, ToolUseBlock):
            parts.append(f"[called {b.name}({_short(b.input)})]")
        elif b.__class__.__name__ == "ToolResultBlock":
            parts.append(f"[tool result: {str(getattr(b, 'content', ''))[:80]}]")
    return " ".join(parts)


def _short(d: dict) -> str:
    return str(d)[:60]


MEMORY_BEHAVIOR = (
    "# Proactive memory & self-documentation\n"
    "You maintain continuity across turns and sessions. Two distinct systems — use BOTH:\n\n"
    "1) The `memory` tool (.clims/memory/) = YOUR private cross-session notebook. As you "
    "work, record DURABLE facts you'd want next session: the user's preferences and "
    "standing instructions, project conventions, non-obvious gotchas, and current task "
    "state. Keep notes short; UPDATE existing notes instead of duplicating; never store "
    "secrets/keys (only where to find them).\n\n"
    "2) Human-facing tracking docs at the PROJECT ROOT (normal files, committable) — for "
    "any task that involves building or substantially changing a project (roughly: more "
    "than one file or more than a couple of steps), you MUST create and keep updated:\n"
    "    - PROGRESS.md — create it at the START of the work; record current status, what's "
    "done, and the next steps. CRITICAL: actually READ it when you resume/continue work, and "
    "UPDATE it after EACH meaningful step (mark items done, set the next step) — not only when "
    "you first create it. A PROGRESS.md you write once and never touch again is useless.\n"
    "    - DECISIONS.md — append each significant technical decision with a one-line 'why'.\n"
    "    - ARCHITECTURE.md — once real structure exists, a short map of the components.\n"
    "  Put these in a docs/ folder (or at root for a small project). Keep them concise and "
    "current (edit in place, don't append endlessly). At the start of continued work, read "
    "them FIRST to recover context. These are SEPARATE from your memory notes — do not put "
    "project tracking only in .clims/memory.\n\n"
    "Exception: for a trivial single-step request (one quick answer or edit), skip ALL of "
    "the above — do not create clutter."
)


@dataclass
class AgentResult:
    messages: list[Message]
    stop_reason: str
    input_tokens: int = 0
    output_tokens: int = 0


class Agent:
    def __init__(
        self,
        *,
        provider: Provider,
        model: str,
        api_key: str,
        runtime: ToolRuntime,
        tools_schema: list[ToolSchema] | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int = 50,
        auto_compact: bool = True,
        summarizer=None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.runtime = runtime
        self.tools_schema = tools_schema or [t.schema() for t in runtime.tools.values()]
        # prepend environment context (OS/shell/cwd) so the agent doesn't default
        # to Unix assumptions — a key robustness fix surfaced by HumanEval.
        try:
            _cwd = runtime.ctx.cwd
        except AttributeError:
            _cwd = "."
        self.system = env_context(_cwd) + "\n\n" + (system or DEFAULT_SYSTEM)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations
        self.auto_compact = auto_compact
        self._summarizer = summarizer  # injectable; default uses the model

    def _summarize(self, messages: list[Message]) -> str:
        """Summarize older turns for compaction. Uses an injected summarizer if
        provided, else asks the model (non-streaming, no tools)."""
        if self._summarizer is not None:
            return self._summarizer(messages)
        convo = "\n".join(
            f"{m.role}: {m.text() or _brief_blocks(m)}" for m in messages
        )
        prompt = (
            "Summarize the following conversation concisely. Preserve key facts, "
            "decisions, file paths, and any in-progress task state so work can "
            "continue seamlessly. Output only the summary.\n\n" + convo
        )
        out = []
        for ev in self.provider.chat(
            model=self.model, messages=[Message.user(prompt)], tools=None,
            system="You are a precise conversation summarizer.",
            api_key=self.api_key, stream=False, temperature=0, max_tokens=1024,
        ):
            if ev.type == "text_delta":
                out.append(ev.text)
        return "".join(out).strip()

    def send(self, messages: list[Message], on_event: EventSink | None = None,
             cancel=None) -> AgentResult:
        emit = on_event or (lambda e: None)
        history = list(messages)
        total_in = total_out = 0
        stop_reason = "end_turn"
        call_counts: dict = {}  # anti-thrash: (tool, input) -> times called this turn
        cancelled = (lambda: cancel is not None and cancel.is_set())
        # let tools see the cancel token (e.g. bash polls it to kill a running command)
        if getattr(self.runtime, "ctx", None) is not None:
            self.runtime.ctx.cancel = cancel

        hooks = getattr(self.runtime, "hooks", None)
        # UserPromptSubmit hook — may block the turn or inject context
        if hooks and hooks.has("UserPromptSubmit"):
            last_user = next((m for m in reversed(history) if m.role == "user"), None)
            outcome = hooks.run_event(
                "UserPromptSubmit", {"prompt": last_user.text() if last_user else ""})
            if outcome.blocked:
                emit(StreamEvent.failure(f"blocked by UserPromptSubmit hook: {outcome.reason}"))
                return AgentResult(messages=history, stop_reason="blocked")
            if outcome.context:
                history.append(Message(role="user",
                                       content=[TextBlock(f"[hook context]{outcome.context}")]))

        # context management: cheap microcompaction first, then full summarization
        if self.auto_compact:
            from clims_core.agent.compaction import compact, needs_compaction, microcompact
            cw = self.provider.capabilities(self.model).context_window
            if needs_compaction(history, cw):
                history = microcompact(history)
            if needs_compaction(history, cw):  # still over after microcompaction
                if hooks and hooks.has("PreCompact"):
                    hooks.run_event("PreCompact", {})
                history, _did = compact(history, self._summarize, cw)

        for _ in range(self.max_iterations):
            if cancelled():
                stop_reason = "cancelled"
                break
            text_buf: list[str] = []
            think_buf: list[str] = []
            tool_uses: list[ToolUseBlock] = []
            errored = False

            for ev in self.provider.chat(
                model=self.model,
                messages=history,
                tools=self.tools_schema,
                system=self.system,
                api_key=self.api_key,
                stream=True,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            ):
                emit(ev)
                if cancelled():
                    break  # stop consuming the model stream immediately
                if ev.type == "text_delta":
                    text_buf.append(ev.text)
                elif ev.type == "thinking_delta":
                    think_buf.append(ev.text)
                elif ev.type == "tool_use":
                    tool_uses.append(ToolUseBlock(ev.tool_id, ev.tool_name, ev.tool_input))
                elif ev.type == "usage":
                    total_in += ev.input_tokens
                    total_out += ev.output_tokens
                elif ev.type == "done":
                    stop_reason = ev.stop_reason or stop_reason
                elif ev.type == "error":
                    errored = True
                    stop_reason = "error"

            # assemble the assistant message
            assistant_content = []
            if think_buf:
                assistant_content.append(ThinkingBlock("".join(think_buf)))
            if text_buf:
                assistant_content.append(TextBlock("".join(text_buf)))
            assistant_content.extend(tool_uses)
            if assistant_content:
                history.append(Message(role="assistant", content=assistant_content))

            if cancelled():
                stop_reason = "cancelled"
                break
            if errored or not tool_uses:
                break

            # execute tools, collect results, feed back — with an anti-thrash guard:
            # if the model repeats the SAME tool call many times, break the loop instead
            # of executing it again (a common failure mode on weaker models).
            results = []
            for tu in tool_uses:
                if cancelled():
                    results.append(ToolResultBlock(tu.id, "interrupted by user", is_error=True))
                    continue
                key = (tu.name, json.dumps(tu.input, sort_keys=True, default=str))
                call_counts[key] = call_counts.get(key, 0) + 1
                if call_counts[key] > THRASH_LIMIT:
                    msg = (f"Anti-loop guard: you have already made this exact "
                           f"{tu.name} call {call_counts[key] - 1} times with the same "
                           f"result. Stop repeating it — take a materially different "
                           f"approach, or conclude with what you have.")
                    emit(StreamEvent.tool_done(tu.id, tu.name, msg, True))
                    results.append(ToolResultBlock(tu.id, msg, is_error=True))
                else:
                    results.append(self.runtime.execute(tu, emit))
            history.append(Message.tool_results(results))
        else:
            stop_reason = "max_iterations"

        # Stop hook — fires when the agent finishes a turn
        if hooks and hooks.has("Stop"):
            hooks.run_event("Stop", {"stop_reason": stop_reason})

        return AgentResult(
            messages=history,
            stop_reason=stop_reason,
            input_tokens=total_in,
            output_tokens=total_out,
        )
