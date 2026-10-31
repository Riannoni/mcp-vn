# Native ChatGPT workers — controlled alternative to browser shims

**2026-10-31. Draft research only; not production.** Always read [../AGENTS.md](../AGENTS.md) and [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md). The render-v1 goal is [issue #20](https://github.com/Riannoni/web-vn/issues/20). The user explicitly stopped the old `vn-night` runner and its quota/watchdog timers. Do not restart them without a new request.

## Why we changed direction

Google's official [supported-browser sign-in guidance](https://support.google.com/accounts/answer/7675428) says Google can block browser sessions controlled through software automation. This happened with `tab2api` + Playwright Chromium during Google SSO. Replacing it with another automated Chromium and disguising automation is not a reliable or approved user-login workflow. OpenAI's personal [Terms](https://openai.com/policies/terms-of-use/) additionally prohibit programmatic extraction of Output and bypassing rate limits.

A more reliable engineering test uses the **ChatGPT product itself**, with connected GitHub or SSH plugins. No Chrome CDP reverse bridge, CLIProxyAPI, account cookies, or Codex CLI is required for each scheduled ChatGPT task. The official [Scheduled Tasks](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt) explicitly support GitHub-connected reads and may perform work in Chat. They still **consume the Chat plan allowance or workspace credits**, and separate tasks are not evidence of unlimited capacity.

## Direct two-task pilot (requested immediately)

Two separate **one-time** ChatGPT Scheduled tasks have been created for a controlled proof-of-concept and an immediate `run_now` was requested for each. Because the platform starts runs asynchronously, success of `run_now` only means the requests were accepted: **do not report completed coding or quota independence before checking their actual run summaries and GitHub evidence**.

| Task | Automation ID | Fixed scope | GitHub writes |
| --- | --- | --- | --- |
| A — render review | `6ae5739d48dc8191a727b779c1c83ea0` | Read latest PR #49 vs issue #20, handoff, 3 evidence-grounded source gaps / negative regressions | **No** |
| B — coordinator review | `6ae5739f737481919763aad1ca43d46d` | Read PR #51's `scripts/parallel_task_coordinator.py`, identify one real concurrency flaw and draft a negative regression diff | **No** |

Both are designed to avoid local worktree collisions and GPU. Each must mark missing connector access/unfinished tests honestly. Once results are collected, pause the tasks to prevent a redundant scheduled next-day repeat. On Plus, [task limits](https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt) currently cap the number of active tasks; check actual account permissions instead of assuming a plan from code.

**Acceptance matrix:**

1. Task A and B actually start in ChatGPT (not Codex); platform records distinct run IDs and status.
2. Both can read current connected GitHub source and cite exact SHA/paths.
3. The results are independently useful; the analysis is verified manually against the exact branch.
4. No read-only task makes commits, changes production, or touches private save/CG.
5. If both run overlaps, their `started_at`–`completed_at` intervals show genuine *concurrency*; if not, record serialization.
6. Read Codex 5h/7d OAuth usage before/after and separately check Chat plan usage if surfaced; do **not** infer independent quota from one ambiguous snapshot. Other sessions may run concurrently.
7. Only after this pilot can ChatGPT tasks perform a small source-only patch in separate draft branches with independent review.

## Official Linux desktop alternative

[ChatGPT Linux desktop preview](https://learn.chatgpt.com/docs/linux/linux-app) has supported Fedora 44 x86_64 packages and Linux local projects/parallel chats. Bazzite 44 is Fedora-based but an *immutable derivative*, not explicitly in the supported distribution list. `chatgpt` is not installed on the PC. Installing an RPM through system layering would affect the OS and potentially require restart: **do not do so automatically**. A user-owned or disposable packaging evaluation is preferable. Linux Computer Use is not yet fully supported in preview. The built-in app could allow manually signed-in Chat sessions and local worktrees without Playwright's Google-login issue; however, Codex/work sessions still have their own usage rules.

For manual ChatGPT sessions on web, the same concept needs no installation: open two separate ChatGPT chats, connect GitHub/SSH plugins, pin independent source branches. The existing SQLite task pilot records leases/evidence, but does **not** itself turn chat messages into API calls.

## Explicit STOP

- Do not install stealth/challenge-bypass plugins, share cookies, alter OAuth assertions or impersonate interactive user behavior from local Python/Node code.
- Do not restart the old night agent, enable a browser proxy against the account, deploy or merge PR #49/#51.
- If Scheduled tasks cannot use connected GitHub tools, report the blocker. No unsupported claims of 24/7 automation.
- G2 visual QA is UNVERIFIED and G3 render-v1 remains NO-GO.

## Empirical results — both ChatGPT tasks completed

**Native Chat task A**: run `1c18ee1d-0288-8325-82d4-b4d4818f2931`, started 2026-10-31T04:51:29Z and completed **04:52:15Z** (~46.4 s), status **completed**, no failure/approval. The linked ChatGPT task reported actual GitHub reads of `main` SHA `5e4e0bfb9cdb74ed3d2e50187780db1513b851b5`, draft PR #49 SHA `da1e6f1cede9b2ec28967edb415a229b8920777f`, issue #20 and source. It identified three plausible source-evidence gaps (mixed-frame provenance, missing principal-index association, `hold_both_hands` not distinguished from touch) with proposed negative tests. No writes and no new tests claimed.

**Native Chat task B**: run `5ca73f36-aca8-832a-ab26-9934fc6037c8`, started **04:51:22Z**, completed **04:53:14Z** (~112.1 s), status **completed**, no failure/approval. It read PR #51 and identified a real `worker()` evidence-file race: a stale lease holder could overwrite `<task_id>.json` even though SQLite `complete()` rejects its fence. It proposed per-lease immutable evidence paths with exclusive creation, and a negative concurrency regression.

**Actual overlap:** tasks A and B were both in progress from **04:51:29Z to 04:52:15Z (~46 seconds)**, with distinct ChatGPT run records. This confirms two simultaneous **native ChatGPT task executions** through GitHub, not two separate local Codex models or browser tabs. It does not guarantee limitless 24/7 usage.

**Independent validation and application after task B:** a separate interactive ChatGPT turn reviewed current PR #51 source, implemented an exclusive per-attempt `persist_evidence` helper using a SHA256 filename derived from task ID + lease fence, `O_CREAT|O_EXCL`, optional `O_NOFOLLOW`, restricted `0600`, and flush/fsync. Added two negative regression tests for stale-worker overwrite and duplicate filename/path traversal. Executed the **entire 11-test unittest suite on the home host: 11 PASS (0.305 s)**. Changes were committed only to the **existing draft research PR #51 branch**, as GitHub commits `707e96a4f9f605f5a6d0461f56038b46ce1919df` and `aa665198cee7f959e85aea1c0cdea816caf0026d`. No merge/main/deploy, no private assets.

**Quota observation:** while these two ChatGPT Scheduled tasks were running/completing, the local read-only Codex OAuth snapshot showed **5h 87% used / 7d 36% used**, and **the same integer percentages** were still reported after both completed. This indicates there was no visible whole-percent increase in the local Codex quota gauge during this controlled window, but does **not prove** the tasks incur zero Codex usage: percent rounding, accounting delays, other user activity, or a shared allowance can prevent exact attribution. Official docs state completed Scheduled tasks in Chat use plan usage allowance or workspace credits. Check the account's Chat usage screen before treating this as a separate free pool.

Both test schedules were **paused after immediate runs** to prevent next-day reruns. The old `vn-night` and both watchdog/quota timers remain stopped; no browser proxy authenticated to ChatGPT. The result is a successful **two-parallel-native-ChatGPT research/coding pilot**, not an always-on hosted night-agent. For ongoing work, explicitly agree on schedule, model, permitted GitHub write branches and resource budget.


## Native ChatGPT Scheduled Task — real SSH-MCP infrastructure canary (verified)

A dedicated **read-only one-time Scheduled Task** was run to test whether cloud-hosted ChatGPT tasks can operate the user's real PC via connected SSH-MCP. This is separate from the earlier GitHub-only tasks A and B.

- Task ID: `6ae57539f2508191bea889ae906231a5`; run ID `5e6f3b9a-3eac-8326-9329-00cc674775c5`.
- Started **2026-10-31 04:58:24Z**, completed **04:58:58Z**, task status `completed` without approval or failure.
- The cloud Scheduled Task reported successful SSH-MCP `infra_exec(host="home")` → SSH to `Xavok@192.168.50.27` → real `xavok-pc`, executing as `Xavok`, Linux.
- Read-only command returned the PC isolated checkout short SHA **`ca10be4`**; `mcp-vn-worker.service` was **active**; old `vn-night-quota-resume.timer` and `vn-night-watchdog.timer` both **inactive** (deliberately stopped by owner).
- Exit 0; command execution reported ~1.6 s. No source changes, deployments, GPU jobs, restarts, private files or credentials accessed.
- This automation was **disabled after completion**, so it will not rerun unexpectedly.

**Result:** cloud ChatGPT tasks **CAN run real read-only checks on the user's infrastructure through the existing SSH-MCP connector**. The model remains in the cloud; actual tests and shell commands run on the PC. This confirms availability of the access path, **not** that two scheduled tasks have simultaneously executed SSH workloads or that arbitrary visual QA / GPU / deployments are safe unattended. For production-quality automation: two isolated Git worktrees, task leases, one owner of GPU, sanitized logs, independent tests and visual evidence; no automatic merge into main.


## Native ChatGPT A/B — two concurrent SOURCE CODING workers on PC (2026-10-31)

**Run root on PC:** `~/.local/share/web-vn-chat-workers/runs/pilot-20261031-1203/`. Deliberately isolated from live game, old Codex worktree, accepted image assets and production services. Both Scheduled ChatGPT tasks ran separately through connected SSH-MCP → home → Xavok-PC and independently read full source rules before modifying source. **No Codex CLI, paid model API, Work, browser shim, production deployments, GitHub pushes or GPU jobs.**

| Lane | Scheduled Task ID | Cloud runtime (UTC) | Local base/branch | Delivered result |
| --- | --- | --- | --- | --- |
| A | `6ae5765f0c408191a87c8e12e2a4fd15` | 05:03:02.971–05:06:29.251 | PR #49 SHA `da1e6f1` → `pilot/native-chat-a-20261031-1203` | Fixed false-accept risk combining actor pose/object/atomic contact from different source frames; 6 initially red regressions, 16 atomic + 8 prop-scale tests green; **uncommitted local diff SHA256 `785585a16f33407842eee40895148c500dcea79a6437a9289368af1452edb025`** |
| B | `6ae5766127d881919c328086756610db` | 05:02:59.712–05:06:19.586 | main SHA `5e4e0bf` → `pilot/native-chat-b-20261031-1203` | Built source-only JSON golden-set manifest validator and negative tests, human labels/provenance/duplicate source claims; **local commit `5a3ccd97ec11c6b8f9418db8d3ca6e3efc7f23a2`**; 24 unittest passed; synthetically validated 30-case CLI input |

**Proven concurrency:** Both native ChatGPT executions overlapped from **05:03:02Z to 05:06:19Z (3 min 16 sec)** and actually wrote and tested independent files on the same PC. This is more than concurrent conversations: real PC operations and separate worktrees confirmed. No overlapping write scopes: A `worker/atomic_prop_gate.py` + `tests/atomic-prop-gate.test.py`; B `scripts/render_golden_set_audit.py` + `scripts/tests/test_render_golden_set_audit.py`.

**Independent verification in a separate ChatGPT turn using real Xavok-PC SSH:** `python3 tests/atomic-prop-gate.test.py` **16/16 PASS** and `python3 tests/prop-scale-evidence.test.py` **8/8 PASS** in A; `python3 scripts/tests/test_render_golden_set_audit.py` **24/24 PASS** in B; Python AST source parsing for all 4 changed files **PASS**, Git diff/check (A) and Git commit/check (B) **PASS**. **48 total independently re-run source tests**. A remains uncommitted, B is committed **locally only**; results are not published source PRs and have not passed code-owner review or visual acceptance. The agent's source metadata provenance checks cannot prove upstream actually bound a claim to original PNG bytes; golden-set synthetic case validation cannot verify G2 or generalize to 30 real cases.

### Codex quota measurement during two native ChatGPT runs

Baseline `~/.local/bin/vn-proxy-quota --provider codex --json` at **2026-10-31 05:01:51 UTC**: short 5h **87% used**, weekly **36% used**. Host-side non-inference user-systemd sampling at 20-second intervals captured **10 successful readings** from **05:03:51 through 05:06:59 UTC**, all **87% / 36%**. The final independent reading **05:07:38 UTC** was still **87% / 36%**. Each native ChatGPT worker also independently captured two matching pre/post private quota JSON snapshots under `evidence/{a,b}/`. Local sampling unit `vn-native-chat-quota-watch-20261031.service` finished and is inactive.

**Evidence-based conclusion:** **two simultaneous, real source-coding native ChatGPT runs consumed no *observable whole-percent* additional Codex OAuth usage** in this 6-minute observation. They demonstrably bypassed the need to run Codex CLI, but this is NOT proof of unlimited ChatGPT allowance or zero billing: the Codex gauge rounds whole percentages and does not expose ChatGPT scheduled-task usage. Recheck remaining plan limits before any 24/7 design.

**Safety/recovery:** Both Scheduled Tasks were disabled after one successful immediate run; old `vn-night-quota-resume.timer` and `vn-night-watchdog.timer` remain inactive; `mcp-vn-worker.service` and original CLIProxyAPI are still active. No code was sent to main/production. Human G2 is UNVERIFIED, G3 remains NO-GO.

**Next controlled increment:** independently inspect A's local diff and B's local commit, compare against latest PR #49/main and full test rules, then create separate draft PRs with no merge; verify source version safety and, separately, a sustained 2-worker cost/usage cycle and GPU mutex before enabling 4–5 workers.
