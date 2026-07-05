# PROGRESS — clims_code development tracker

> **Read this first when resuming development.** It is the single source of truth for "where are we."
> Update it at the end of every working session: flip checkboxes, append to the session log, set "Next action."

## Esc-anytime interrupt (threaded) + bash hardening + TUI polish
- **Threaded interrupt**: turn runs on a worker thread; main thread watches Esc/Ctrl-C
  (clims_cli/interrupt.py: msvcrt Windows, termios/select POSIX) → sets a cancel Event. Agent.send(cancel=)
  checks it between iterations + mid-stream; tools poll ToolContext.cancelled(). Tested: pre-cancel = no model
  call; cancel-on-tool_use skips exec; bash killed in 0.15s.
- **bash hardening**: stdin=DEVNULL (no hang on interactive cmds); reader-thread + poll kills child on
  cancel/timeout (no orphans/deadlock).
- **TUI**: ⏺/⎿ tool lines, markdown responses, pixelated CLIMS logo, highlighted input bar, yellow status
  toolbar; UTF-8 forced before rich (fixes cp1252 crash). Plan mode = read+web+memory+.md writes, no code/shell.
- Self-config (configure tool + add_mcp by registry name), MCP registry (~12), `pip install -e .` → global `clims`.
  202 tests.

## Snapshot

- **Phase:** COMPLETE — full Claude Code feature parity reached.
- **Overall status:** 🟢 **7 providers + 15 tools + subagents + hooks + compaction + safety guard + 25+ slash commands + rich TUI + MCP(stdio+http, tools/resources/prompts/OAuth) + HTTP API (+OpenAI shim) + memory tool + sqlite sessions + skills + vim + telemetry + auto-update.** **116/116 unit tests pass.** Validated LIVE on DeepSeek.
- **Benchmark:** **100.0% (141/141) at temp 0**; multiple regression re-runs 47/47. See [MORNING_REPORT.md](MORNING_REPORT.md).
- **Parity:** **116/116 applicable = 100%** (1 N/A: account login under BYOK) — see [docs/02-FEATURE-PARITY.md](docs/02-FEATURE-PARITY.md)
- **Next action:** consolidate/package for release; optional live-validation of non-DeepSeek providers (needs their keys).
- **Last updated:** 2026-06-07 (overnight autonomous session, continued)

## Added in continuation (parity push) — 31 → 67 tests, parity 44% → 64%
- **Hooks**: PreToolUse (block), PostToolUse (annotate), UserPromptSubmit (block/inject), Stop. Config-driven. Tested.
- **Subagents** (+ file-defined `.clims/agents/*.md` with agent_type selection). Recursion-bounded. Tested.
- **Gemini provider** (5th provider): functionCall/functionResponse dialect; wire-tested.
- **Context auto-compaction**: summarize old turns near window; safe boundaries; tested.
- **web_search tool**: DuckDuckGo form-POST; parser tested; live-verified.
- **MCP HTTP transport**: Streamable HTTP JSON-RPC + bearer token; tested w/ mock server.
- **OpenAI-compatible API shim** (`POST /v1/chat/completions`, stream+non-stream): tested.
- **Headless output formats** (text/json/stream-json).
- **Custom slash commands** (`.clims/commands/*.md` + $ARGUMENTS): tested.
- **bash_output + kill_shell** (poll/stop background jobs): tested.
- **@file-mentions** (expand @path to file content; ignores emails): tested.
- Earlier: sqlite sessions, 9 CLI slash commands.
- **Regression benchmark re-run: 47/47 (100%) at temp 0** — no regression from loop changes.

## Second continuation (user picked: safety + TUI + slash commands)
- **Safety/sandbox**: PathGuard (workspace boundary + .clims-ignore deny globs, runtime-enforced) + SessionStart/PreCompact/Notification hooks. Tested.
- **Rich TUI**: render module (markdown/diff/spinner/status), edit-tool unified diffs, spinner + status line in REPL. Graceful fallback w/o rich. Tested.
- **Slash commands**: +/init /compact /agents /commands /export /permissions /config /doctor /status (now 18 total). Tested.
- Tests 67 → **83**. Parity 64% → **83%**.

## Remaining (~6 items — all interactive/long-tail, lower value for a backend product)
- /review, /bug, /pr-comments, /terminal-setup, vim mode (J7), IDE diagnostics (I9).
- Partials: streaming-markdown (J1), live /model switch (G7/D8), CLI /resume (G14/I2), exec sandbox (E8),
  output styles (C12), MCP resources/prompts (C6), skills (C9), prompt caching (A14), git/PR helpers (I10).
- Deferred niche: Bedrock/Vertex (D6), notebook edit (B13), conversation rewind (A11), microcompaction (A10),
  queued input (A6), interrupt (A5), auto-update (J8), telemetry (J9), proxy (H8), agent memory dir (H5).

## Orchestration engine (closes the "agentic orchestration" gap) — NEW
- **clims_core/orchestrate.py**: `parallel(thunks)` + `pipeline(items, *stages)` (real thread concurrency — model
  calls are I/O-bound; providers are stateless per-call so concurrent chat() is safe) + `spawn_agent(...)` to run
  child agents. This is the layer clims_code was missing (was sequential-only).
- **clims_core/research.py**: `deep_research()` harness — fan-out queries → parallel search → parallel fetch →
  parallel note-extraction → cited synthesis → optional adversarial verification. Deps injected (search/fetch/llm)
  so fully unit-tested without network.
- **/research <question>** CLI command wires real DuckDuckGo search + web fetch + the model.
- Structured helpers added: `search_web()` (web_search), `fetch_url_text()` (web_fetch).
- Tests: 8 (parallel order/concurrency/error-isolation, pipeline, spawn_agent, deep_research e2e + no-sources). 128/128 total.
- Built PARALLEL to the running HumanEval benchmark (separate process; no API used by unit tests). Live /research
  demo deferred to avoid competing API calls with the benchmark.
## Globally installable (pip install -e .) + Windows UTF-8 fix
- `pip install -e .` → `clims` command on PATH, callable from any directory (operates on cwd). Editable: code changes live.
- **Real Windows bug found by the global test + fixed**: CLI printed UI glyphs (→ ✓ ✗ 🔔) but Windows console
  is cp1252 → UnicodeEncodeError crash on first tool call. Fix: main()._force_utf8_output() reconfigures stdio to
  utf-8/replace. Verified: `clims -p "create proof.txt" --mode bypass` from a temp dir created the file, ✓ glyph printed.
- Usage from anywhere: `clims` (interactive) · `clims -p "..."` · `clims --resume`. 187/187 tests.

## MCP server registry + resolve-by-name — LIVE-VERIFIED
- clims_core/mcp/registry.py: curated specs for popular MCP servers (github/gitlab/slack/brave/google-maps/
  postgres/puppeteer/memory/gdrive/sentry/filesystem + aliases). resolve(name, secret) routes the secret to the
  right env var / connection-string arg / positional, returns ready conf. known_servers()/describe().
- configure add_mcp now resolves by NAME: "connect github with <token>" → registry builds npx command +
  GITHUB_PERSONAL_ACCESS_TOKEN env. Unknown name w/o command/url → helpful error listing known servers.
  OAuth servers (gdrive) → asks for proper flow. /mcp lists known servers; system prompt teaches it.
- **Live-verified:** plain chat "connect the filesystem MCP server for <dir>, use its name" → agent called
  configure(add_mcp, name=filesystem) → registry resolved → connected to REAL npx server, 14 tools added live.
- 187/187 tests (9 new).

## Connect MCP from chat + secret redaction — LIVE-VERIFIED
- `configure` tool gained **add_mcp**: the agent connects to an MCP server on a plain-chat request, adds its tools
  to the LIVE runtime + refreshes the model's tool schema. Creds (env/token) used in-memory, NEVER persisted;
  only non-secret connection info saved to settings.local.json for reconnect.
- **Secret redaction** (clims_core/redact.py): SQLiteSessionStore.set scrubs common secret shapes (sk-/ghp_/AKIA/
  key=… etc.) from the PERSISTED transcript only (in-memory history untouched) — so a credential typed in chat
  never hits disk.
- **Live-verified:** "connect to MCP server echo with command X" → agent called configure(add_mcp) itself →
  runtime MCP tools went []→['mcp:echo:echo','mcp:echo:add']. Redaction test: ghp_ token not present in the sqlite file.
- 178/178 tests (4 new).

## Self-configuration (closes a real gap the user found) — LIVE-VERIFIED
- `configure` tool: agent reconfigures clims_code on chat request — allow/deny/ask rules, permission mode,
  model, temperature, output style. Applies LIVE (shared policy / live agent) + persists to settings.local.json.
  Never persists secrets. Gated as MUTATING (user approves once) so the agent can't silently escalate permissions.
- selfconfig.py persistence; system prompt now instructs self-configuration; wired into build_agent w/ session holder.
- **Live-verified:** "allow all git commands without asking" → agent called configure → policy.allow=['Bash(git *)']
  live + persisted to settings.local.json. 174/174 tests (6 new).

## MCP — LIVE-VALIDATED against a real server (+ Windows fix)
- Connected clims_code's MCP client to the official @modelcontextprotocol/server-filesystem via npx;
  discovered 14 real tools; successful live calls (list_directory, read_file returned actual content).
- **Real bug found+fixed by the live test**: StdioMCPClient couldn't launch npm-based servers on Windows
  (npx -> npx.cmd; WinError 2). Fix: shutil.which() resolution + shell launch for .cmd/.bat shims. 168/168 tests pass.
- MCP credentials confirmed: stdio via env vars, HTTP via bearer token / OAuth client-credentials.

## Deps + image-in-tool-result + deeper tools (latest)
- **Optional [full] deps installed** (tiktoken, pypdf, rich, prompt_toolkit). pyproject `[full]` extra added.
  Engine core stays zero-dep; these are auto-used when present. tiktoken now powers token counting; pypdf powers PDF Read.
- **Image-in-tool-result (multimodal tool results)**: ToolResult/ToolResultBlock carry `images`; Read returns the
  ACTUAL image for image files; adapters wire it per dialect — Anthropic native image block in tool_result,
  OpenAI/DeepSeek follow-up user image_url message, Gemini inlineData. Wire-tested across all 3.
- **Deeper tools**: MultiEdit (atomic multi-edit, read-before-edit, all-or-nothing); Read now lists directory contents
  instead of erroring; PDF via pypdf; binary/image detection. Tested.
- Tests: +13. **168/168 total.** No regression (agentic 12/12; a 20-sample HumanEval dip was confirmed stochastic —
  failures were a transient blip + a zero-tool-call model-answers-as-text + one hard problem, NOT a guard block).
- 16 built-in tools now.

## Harness-depth (closing the non-model harness gap)
- **File-state tracking (Claude Code parity)**: ToolContext tracks file reads (mtime); EDIT requires a prior read,
  WRITE-overwrite requires a prior read, and both detect STALE files (changed on disk since read). Our own
  write/edit re-marks the file so consecutive edits work. Prevents blind/stale edits. Tested + agentic 12/12 (no regress).
- **ripgrep-backed grep**: uses `rg` when on PATH (faster, better defaults); pure-Python fallback otherwise. Tested.
- **PDF/image/binary-aware Read**: PDFs via pdftotext (when installed); images → vision hint (-i flag); binaries → described, not garbage. Tested.
- **Tokenizer-aware context counting**: estimate_tokens uses tiktoken cl100k_base when installed, else chars/4. Tested.
- Tests: 7 new. **157/157 total.** (1 prior test updated to read-before-edit.)
- Remaining harness gap: multimodal tool-RESULTS (image-in-tool-result plumbing), even-deeper tool impls, and the
  irreducible ~10% model–harness co-training residual (not third-party closable).

## Reliability + UX polish (latest)
- **Anti-thrash guard** (agent/loop.py): detects repeated identical tool calls (THRASH_LIMIT=3) and injects an
  anti-loop error instead of executing again — breaks the thrashing failure mode we saw on the OS issue. Tested.
- **Adversarial-verify primitive** (orchestrate.verify_claim): N skeptics each with a DIFFERENT lens, parallel,
  majority vote. Reusable in workflows. Tested.
- **Research self-revision** (research.deep_research revise=True): if the adversarial fact-check finds issues,
  one revision pass fixes the report using only cited info. Tested.
- **UX (render.py)**: rich tasks table (/tasks), bordered plan panel (plan-approve), markdown research report,
  status_summary. Graceful stdlib fallback. Tested.
- Tests: 10 new. **150/150 total.**

## Orchestration family — COMPLETE (all built + tested; deep-research live-verified)
- **Background agents** (clims_core/background.py): run agent tasks in threads; /bg, /tasks, /bg-result; bell on completion. Tested.
- **Scheduler** (clims_core/scheduler.py): persisted interval schedules + SchedulerLoop runner; /schedule add|list|remove. Tested (injected clock).
- **Specialized agent types** (clims_core/agent_types.py): explore/plan/reviewer/researcher (tuned system + read-only tool allowlist + iteration budget); wired into spawn_agent + subagent agent_type. Tested.
- **Plan-mode approve→execute** (repl.py): agent calls exit_plan_mode in plan mode → REPL shows plan → user approves → switches to acceptEdits → executes (pending_exec).
- **Workflow runner** (clims_core/workflows.py): run Python workflow modules from .clims/workflows/*.py via /workflow; WorkflowAPI exposes parallel/pipeline/agent/research. Tested.
- **Live-verified:** /research on "what is MCP" → parallel search→fetch→synthesize→adversarial-verify in 12s, accurate cited report, fact-check caught a real nuance.
- Tests: 12 new (background/scheduler/agent_types/workflows). **140/140 total.**
- HumanEval with behavioral-tuned prompt: 161/164 = 98.2% (flat vs 99.4%; diff = run variance + 1 transient API blip).

## Behavioral-tuning pass (system prompt rewrite, live-verified)
- Rewrote DEFAULT_SYSTEM to bake in: efficient tool use; conciseness/terminal communication; do-exactly-asked
  (no over-engineering/unrequested files); read-before-write & match conventions; plan+verify; ask-vs-assume
  judgment; and caution guardrails (destructive-op confirmation, no git commit/push unless asked, secret hygiene).
- **Deferred (per user):** malicious-use refusal / defensive-security posture — for later.
- Live spot-check (DeepSeek): concise+do-exactly-asked ✅, no-over-engineering ✅. Secret hygiene FAILED first
  (printed the key when asked) → strengthened the rule ("radioactive, not even when asked, output is saved to
  transcripts") → now refuses & refers by name/location ✅. Demonstrates the model-bound reliability point:
  prompt-only secret protection needs an emphatic rule on DeepSeek; robust production fix = engine-level redaction (TODO).
- No regression: HumanEval 40-sample 40/40=100%; 121/121 unit tests. Full 164 re-run launched for confirmation.

## Proactive memory & self-documentation (added, live-verified)
- Agent now reads `.clims/memory/` + CLIMS.md + existing PROGRESS/DECISIONS/ARCHITECTURE at session start (`memory_digest`).
- Default `MEMORY_BEHAVIOR` system instruction: record durable facts/decisions to the `memory` tool; for multi-step projects, create+maintain PROGRESS.md/DECISIONS.md/ARCHITECTURE.md at project root.
- `assemble_system()` composes base + behavior + memory + digest. Config `proactive_memory` (default on); disable via `CLIMS_NO_PROACTIVE_MEMORY=1`. `/memory` reviews tracked items.
- **Live-verified on a real project build:** agent used the memory tool AND created PROGRESS.md + DECISIONS.md + ARCHITECTURE.md. (First attempt only wrote a memory note; strengthened the instruction → all three root docs now created.) 121/121 tests pass.

## Built this session
- **Engine (zero-dep):** normalized message model, provider ABC, stdlib HTTPS+SSE, agent loop, tool runtime.
- **Providers (4):** DeepSeek (live-validated), Anthropic (wire-tested), OpenAI + Ollama (OpenAI-compat subclasses). Capability registry. Transient-failure retry w/ backoff.
- **Tools (9):** read, write, edit, bash (+background), glob, grep, web_fetch, todo.
- **Permissions:** 4 modes + allow/deny/ask rules (tested).
- **MCP client (Phase 3):** stdio JSON-RPC, tools/list + tools/call, namespaced `mcp:server:tool`, wired into runtime + config. Tested w/ mock server.
- **HTTP API server (Phase 4):** sessions, SSE streaming, BYOK-per-request, product auth. Body-drain fix for clean connection close.
- **Memory:** CLIMS.md project/user/nested memory with @import (tested).
- **CLI:** REPL + headless `-p` mode; loads memory + MCP.
- **Config:** settings hierarchy + env/BYOK + mcpServers resolution.
- **Benchmark harness:** 47 tasks (20 coding + 12 agentic + 15 stress) w/ programmatic verification, multi-trial reliability reporting, temp control.
- **Tests:** 29/29 offline pass (message norm, both wire formats, loop, plan-mode, tools, retry, server, memory, MCP, providers).
- **Docs:** USAGE.md added.

## Known reliability findings (from benchmarking)
- Transient SSE read-timeout could crash a turn → FIXED with retry-with-backoff wrapper (+4 tests).
- At high temperature, the model sometimes answers coding tasks as TEXT instead of calling `write` (0 tool calls), or drifts from the exact filename → mitigated by temperature=0 default for eval + stronger system prompt ("you MUST use tools to perform actions; follow the output contract exactly").

## External benchmark — HumanEval (OpenAI, 164 problems, official tests)
- Agentic run (agent writes solution.py, can self-test; official check() verifies). pass@1.
- **First run (25-sample): 72%** — but ALL failures were "solution.py not created", zero wrong answers.
- **Root cause (real robustness bug):** the agent's system prompt didn't state OS/shell/cwd, so the
  model assumed Unix — ran `cd /home/user`, tried `python3`, never called `write`. Empty workdir.
- **Fix:** inject `env_context()` (OS, shell, cwd, "use write tool, don't cd elsewhere") into every
  agent's system prompt (clims_core/agent/loop.py). This is something Claude Code always does.
- **After env fix (same 25): 100%.**
- **Full 164 run: 160/164 = 97.6% pass@1.** 4 failures dissected: 1 flaky (passes on rerun),
  1 harness (agent thrashed in bash, never wrote file), 2 genuine DeepSeek reasoning bugs.
- **Optimization 2:** runner prompt now "write solution.py FIRST, then self-test against the
  docstring examples and fix"; max_iterations 10→16. Re-running the 4: 3/4 recovered (incl.
  HumanEval/127, a previously "genuine" model error — the agent self-tested, caught its bug, fixed it).
  The 4th (145) hit a transient empty API response (0 tool calls), not a real failure.
- **Full optimized 164 re-run: 163/164 = 99.4% pass@1.** Sole failure = HumanEval/145
  (negative-digit order_by_points): agent self-tested 127s, fixed the example, but DeepSeek still
  got a hidden-test edge case wrong. Genuine model-reasoning limit — deliberately NOT special-cased
  (gaming a single problem would violate benchmark integrity).
- **Journey: 72% → 100% (25) → 97.6% (164) → 99.4% (164 optimized)** via two real fixes:
  (1) inject OS/shell/cwd env-context into the system prompt; (2) write-file-first + self-test-against-
  docstring guidance + more iterations. For reference DeepSeek-V3 single-shot HumanEval is ~88-90%;
  the agentic harness lifts it to 99.4%.
- **Key lesson:** an external benchmark found a real robustness gap my own self-made suite missed
  (missing OS/cwd context). The remaining failure is model-bound (DeepSeek), not harness —
  consistent with the honest assessment that intelligence ≈ the model you plug in. CONTAMINATION
  CAVEAT: HumanEval may be in DeepSeek's training data; the meaningful signal is the harness
  improvement (72%→99.4% via real bug fixes), not the absolute number alone.

## Benchmark — first full run (DeepSeek deepseek-chat)
- **32/32 passed (100%)**: 20 coding (easy→hard) + 12 agentic. Avg ~6s/task.
- Hard coding solved: LRU cache, edit distance, coin change, topological sort, JSON flatten.
- Agentic solved: multi-file scaffold, bug-fix, cross-file search-replace, CSV sum, build-and-run, refactor-rename, grep-report.
- 100% means the suite isn't discriminating yet → adding a harder STRESS tier + repeated trials to find the failure boundary.

## Phase 1 — DONE ✅ (validated)
- Engine builds & imports clean on Python 3.10.11.
- Offline suite: 7/7 pytest pass (message normalization, both adapter wire formats, full loop, plan-mode denial).
- **Live DeepSeek: 3/3** — plain chat (PONG), write-tool round-trip, multi-step bash+reasoning.
- Exit criterion met on DeepSeek. (Anthropic adapter unit-tested for wire format; needs an Anthropic key for live confirmation.)

## Locked decisions (see docs/09-DECISIONS.md)

- Python 3.11+; engine = stdlib only; CLI may use minimal deps.
- Model-agnostic via hand-rolled provider adapters.
- API-first, headless engine; CLI is one client.
- BYOK, key per request, never persisted.
- Self-hosted behind reverse proxy.
- Capable (native tool-calling) models only.
- General-purpose (not coding-only); MCP-forward.
- Full Claude Code feature parity is the bar.
- Phase 1 providers: DeepSeek + Anthropic.

## Phase 1 checklist — Engine core & provider proof

- [ ] Package skeleton (`clims_core/`, `pyproject.toml`, Python 3.11 target)
- [ ] `agent/message.py` — Message + ContentBlock types
- [ ] `providers/base.py` — Provider ABC, StreamEvent, ModelCapabilities, ToolSchema
- [ ] `http.py` — stdlib HTTPS POST + SSE line reader
- [ ] `providers/deepseek.py`
- [ ] `providers/anthropic.py`
- [ ] `providers/registry.py` — capabilities for phase-1 models
- [ ] `tools/base.py` + `tools/read.py`, `tools/write.py`, `tools/bash.py`
- [ ] `permissions/policy.py` — minimal ask/allow/deny + modes
- [ ] `agent/runtime.py` — tool dispatch
- [ ] `agent/loop.py` — agentic loop with streaming
- [ ] `clims_cli/repl.py` — minimal REPL
- [ ] **Exit criterion:** one real file+shell task completes on BOTH DeepSeek and Anthropic by changing one config value.
- [ ] Tests for message normalization + both adapters (mocked HTTP)

## Upcoming phases (summary)

- Phase 2 — general tool suite (edit/glob/grep/web/todo/notebook), CLI streaming render, more providers (OpenAI/Gemini/Ollama), images, background bash.
- Phase 3 — MCP client (stdio + HTTP/SSE, OAuth, tool aggregation).
- Phase 4 — HTTP API (sessions, SSE protocol, BYOK, product auth, OpenAI-compat shim).
- Phase 5 — full experience: slash commands, memory, subagents, hooks, skills, settings hierarchy, plan/auto-accept modes, compaction, cost, sessions resume, headless mode, status line, notifications, vim, IDE hooks.
- Phase 6 — productize: sandbox, packaging, licensing/auth, docs, telemetry, /doctor, /bug.

Full detail: [docs/08-ROADMAP.md](docs/08-ROADMAP.md). Full feature list: [docs/02-FEATURE-PARITY.md](docs/02-FEATURE-PARITY.md).

## Open questions / parking lot

- Search provider for `web_search` (BYOK search API vs MCP-only)? — decide in Phase 2.
- Windows shell strategy for `bash` tool (powershell vs cmd vs configurable) — decide in Phase 1 when building the tool.
- Conversation rewind/checkpoint storage model — design in Phase 5.

## Session log

### 2026-06-07
- Completed planning & discussion. Locked all core product decisions.
- Wrote full docs set: README, 00-OVERVIEW, 01-ARCHITECTURE, 02-FEATURE-PARITY (95-item matrix),
  03-PROVIDERS, 04-API, 05-MCP, 06-TOOLS, 07-PERMISSIONS, 08-ROADMAP, 09-DECISIONS.
- Created this tracker.
- **Next:** begin Phase 1 — scaffold `clims_core` + `agent/message.py`.
```
