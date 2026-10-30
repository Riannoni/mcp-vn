# Browser-backed ChatGPT agent bridges: isolated evaluation (2026-10-31)

> **DRAFT / source-only research.** Before any deployment read root [AGENTS.md](../AGENTS.md), [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md), [NIGHT-AGENT.md](NIGHT-AGENT.md). This experiment does **not** authorize a live browser bridge, account-sign-in automation, rate-limit bypass, new GPU work, game modifications or a merge into `main`. Render-v1 #20 remains G2 UNVERIFIED / G3 NO-GO.

## 1. Question and scope

The current GPT-6 Astra CLI night runner used 88% of its 5-hour Codex quota within its first ~23 minutes, with about 2.95M cumulative input tokens for four complete source-only turns. The owner wants to evaluate whether an alternative ChatGPT browser adapter could provide useful local agent assistance, then—**only if proven workable**—develop a coordinated four/five-worker architecture.

An MIT-licensed adapter can be installed and audited, but that license is not a grant of access or an exemption from upstream ChatGPT terms/quotas. Current personal [OpenAI Terms of Use](https://openai.com/policies/row-terms-of-use/) restrict automated/programmatic extraction of Output and circumvention of rate limits. A browser shim cannot be represented as an officially supported unlimited ChatGPT API. Distinguish (a) tests of open-source code using synthetic fixtures from (b) calls to the signed-in ChatGPT service. This lab performs **only (a)**.

## 2. Exact source revisions and isolated test location

Cloned read-only-from-upstream into an independent private PC lab:
- `leeguooooo/chatgpt-use` at `ecb204d4f4a4aef127851240af17dcf1a321afbc`; Rust, current `Cargo.toml` package version `0.0.11` (README version statements can lag).
- `Octo-Lex/ChatGPT-Web2API` at `497527dceabfa3f95961e23c291e618c5570f1ac`; Python, `pyproject.toml` version `0.2.0`.

Lab files: `~/.local/share/web-vn-bridge-eval/20261031/` on `Xavok-PC`. Only the two GitHub source clones, private test reports and separate container images/caches were added. Nothing is installed into game venv, worker, ComfyUI, home server, global browser profile or existing CLIProxyAPI. No tokens/cookies/management passwords were read, copied or mounted in tests.

**Safety properties:** rootless Podman; disposable filesystem/process; `--network=none` during actual tests, `--cap-drop=all`, `--security-opt=no-new-privileges`, memory/CPU limits, and mounts restricted to lab source and disposable build cache. Package download/build and Rust crate fetching occurred in isolated bootstrap containers *before* offline tests, without home profiles. `W2A_E2E_RUN` never enabled. Upstream's 31 real-account E2E cases are excluded.

**Rust verification** (Fedora 44 toolbox image + cargo fetched dependencies; offline testing):
```bash
cargo fetch --locked                         # earlier dependency bootstrap
cargo test --offline --locked -- --test-threads=2
```
Result observed: **218 passed, 0 failed, 2 ignored** (213+2+3 passed, 2 ignored). This establishes unit/tool-protocol behavior, not browser/Codex interoperability.

**Python verification** (initial Fedora 44 / Python 3.14 image, network disabled):
```bash
python -m pytest -m 'not e2e' -q --disable-warnings
```
The large suite reached **83%** but stopped making progress; a lab-only timeout/stop ended the container. This is **NOT** a full passing suite; may be a test deadlock, environment limitation or genuine regression. A focused concurrency subset likewise stalled during an owned-tab isolation test. Reproduction under **Python 3.12** with `pytest-timeout` is being separately recorded; do not report it as passed without the actual final exit code.

## 3. Architecture and functional suitability

| Feature | chatgpt-use | ChatGPT-Web2API |
| --- | --- | --- |
| Primary API | Rust CLI/MCP `ask`/`run`, experimental Anthropic-style `serve` | OpenAI-compatible REST + MCP server |
| Implementation | `chrome-use`, signed-in Chrome; macOS-first | Python + Chrome CDP, requires browser and account login |
| Tool calls | Emulated JSON/text protocol, no native web function calling | Emulated/protocol transport; tool interface tested with mocks |
| Worktree isolation | Local project commands, approvals configurable | Chat interface only, external agent owns file writes |
| Multiple requests | **One active browser request/channel; process-global advisory lock** | Single tab default, experimental owned-tab pool and optional MCP session pool |
| 4–5 independent account quotas? | **No.** Browser serialization and server-side accounting | **No.** Multiple tabs do not create distinct account quotas |
| Images for CG visual QA | Not validated | README: image input not implemented |
| Stability | Experimental; open [#18](https://github.com/leeguooooo/chatgpt-use/issues/18) reports October 2026 UI redesign breaking model/composer interaction | Mock coverage sizeable; real-account E2E opt-in, UI drift/429 and session races documented |
| Tested here | Rust test suite passed, browser path NOT tested | Offline pytest partial; browser path NOT tested |
| Production ready? | **NO** | **NO** |

Important: the `chatgpt-use/AGENTS.md` upstream explicitly warns maintainers **never to run live ChatGPT tests**: around 23 fresh full-page loads triggered “Too many requests” on its author's account. `ChatGPT-Web2API` README defaults to serial requests; its B1 tab pool is marked experimental, recommends pool size 2 first and account-level burst/rate-limit checks before raising capacity.

The mere availability of `/v1/chat/completions` or a compatible SDK schema does not establish full agent correctness. The test matrix must cover: exactly-once prompts, tool-call structure, multi-turn continuity, retry/no duplicate submissions, process crash and recovery, tab isolation, malformed/partial responses, observed cost per accepted source change, non-default model choice, client disconnects and permissions. Image-in support is additionally needed before a model can independently inspect private CG pixels. **No fake G2 visual approval.**

## 4. Other open-source candidates discovered

- [Jisiyong-A/chatgpt-web-provider](https://github.com/Jisiyong-A/chatgpt-web-provider): fail-closed semantic UI locator, exactly-once and crash-resume architecture; Node.js; very small user base, not locally tested.
- [cromat/chatgpt-web-session-proxy](https://github.com/cromat/chatgpt-web-session-proxy): local Pi/OpenAI chat-completions proxy with session affinity, Xvfb Chrome on Linux; not locally tested.
- [tang-vu/tab2api](https://github.com/tang-vu/tab2api): recent TypeScript browser bridge including text and image claims; not locally tested, still experimental.
- [int04/ChatCmd](https://github.com/int04/ChatCmd): Rust/SQLite/MCP permission-scoped local worker and management UI; an interesting orchestration alternative with browser integration, not a proven replacement for model subscription limits.
- [stufently/gpt-web-gateway](https://github.com/stufently/gpt-web-gateway): Chrome/patchright bridge; README warns of account/ToS risk; not tested.
- [halochamp/MCP-LinkGPT](https://github.com/halochamp/MCP-LinkGPT): bounded ChatGPT Web reviewer over MCP; source-only second opinion rather than multi-worker model backend.
- [damianofalcioni/browser-llm-bridge](https://github.com/damianofalcioni/browser-llm-bridge): browser REST PoC, not tested.

Do not infer compatibility or security from GitHub star counts. Re-evaluate active version/commit and issue trackers before using any candidate.

## 5. Next phase architecture — design only, NOT deployed

A serious five-worker system for `web-vn` should **not** use five Chrome tabs as five independent accounts. Separate *parallel source work* from *shared rate-limited inference*:

```text
                       master goal #20 / newest RENDER-HANDOFF
                                        |
                          SQLite WAL job coordinator
                      task DAG / priority / leases / events
                                        |
       +---------------+----------------+--------------+----------------+
       |               |                |              |                |
    worker 1         worker 2         worker 3       worker 4        reviewer
    Source A         Source B         Tests          Docs       independent QA
       |               |                |              |                |
       +---------------+------- model request broker ----+----------------+
                                       |
                        single permitted upstream capacity
                      (initial concurrency=1, measured/fenced)
                                       |
                           local source-only evidence
                                       |
                            draft PR(s), NOT main
```

**Contracts to implement only after backend smoke success:**
1. **Single authoritative task ledger**, e.g. SQLite WAL: `task_id`, `goal_id`, `parent_sha`, `deps[]`, `owner`, `state`, `lease_until`, `attempt`, `idempotency_key`, `branch`, `changed_paths`, `evidence_path`, `test_outcome`, `reviewer`, `gpu_lease`, `created_at`, `updated_at`.
2. Atomic task claims/heartbeats; crash-safe leases and exactly-once *commit/publish* fence. Retry is not permission to duplicate ChatGPT sends or GPU jobs. Limit attempts to 2–3, classify failures and record BLOCKED.
3. Four **independent git worktrees/branches** pinned to a known base SHA, separate caches/logs. No two writers to the same source paths without explicit integration; a coordinator resolves overlapping diffs and stale handoffs.
4. One serialized **GPU lease** across all workers, preserving the canonical game save and existing accepted assets. One source validator or CG reviewer cannot silently consume the only GPU while others use it.
5. A model request broker: per-provider / per-account quota, rate-limit backoff, bounded token/context budget, explicit upstream error, no model fallback without user approval. Start at inference concurrency=1 for one ChatGPT account; increase only if both service rules and measured correctness permit.
6. Completion requires independent source tests, negative regression, diff review and an evidence checksum. Source stage DONE is not G2/G3 accepted. A reviewer must inspect exact original PNG for any genuine CG claim.
7. Local reporting every 30–60 seconds from a read-only aggregator; **ChatGPT Automation** checks summarized state hourly, compares PRs/handoff and can execute bounded safe repairs only. Its published status must show stale heartbeats and blocked tasks honestly.
8. Draft PR from an independent reviewable branch, never auto merge to `main`; no credentials, CG or private story in GitHub.

## 6. Explicit decision gates

**Gate A — Offline:** unit tests for transport, parser, queues, locks, session pooling and failure modes pass on supported Python/Rust; otherwise fix or exclude the candidate. This lab evaluates Gate A only.

**Gate B — Live functional canary:** would require a separately authorized, logged-in, dedicated Chrome profile and lawful service access. Validate one task end-to-end with isolated non-private input, no automated mass submission, and explicit measurement of UI limits. The current task does **not** perform this step and does not claim that the browser surface has a supported automated API.

**Gate C — Source task quality:** accepted patch + negative test + independent review on an isolated copy of web-vn, no production changes.

**Gate D — Coordination:** concurrency 4–5 for *independent source/CPU* workers, request broker honors actual account restrictions and a single GPU lock, with measured no-duplicate/crash-recovery results.

**Gate E — Render quality:** separately verified G1/G2/G3 from [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md); mock API tests alone do not satisfy any visual gate.

### Current disposition

**No browser bridge has been connected to the actual account or enabled as a nightly model provider.** Existing Codex, quota monitor, timers and ChatGPT hourly reporting are unchanged. This is a deliberately separate **draft research PR** to keep the experiment reviewable and avoid accidental production deployment.
