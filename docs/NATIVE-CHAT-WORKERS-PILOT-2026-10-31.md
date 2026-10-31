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
