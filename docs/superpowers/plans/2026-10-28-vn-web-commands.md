# VN Web Commands Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task by task.

**Goal:** Add the requested commands to the deployed VN Web and document the standalone client and image fixes.

**Architecture:** Parse commands on the server, persist command context with the player action, and use existing versioned game storage. Keep OOC/recap outside canonical history; reuse existing artwork workers.

**Tech Stack:** Node ES modules, Python standard library HTTP backend, vanilla JS/CSS.

**Spec:** `docs/superpowers/specs/2026-10-28-vn-web-commands-design.md`

## Global Constraints

Preserve existing saves and unfinished source changes. No credentials or personal game data in Git. Keep the existing layout and Russian labels. No automatic video generation.

## Review Focus

- Concurrent/stale retries and undo must not remove a newer turn.
- Retrying a dice action must reuse its original result.
- OOC/recap and rejected commands must not change story state.
- Local episodes must keep their own transcript and visual state.
- In-flight UI requests must not render into another selected save.

## Task 1: Server command behavior

Files: `src/story-commands.mjs`, `src/game-store.mjs`, `src/narration-packet.mjs`, `src/local-scene.mjs`, `src/local-narrator.mjs`, `server.mjs`, `standalone-web/vn_web.py`, `standalone-web/server.py`; tests in `tests/story-commands.test.mjs` and `standalone-web/test_commands.py`.

- [x] Add failing tests for validation, server dice, retry rollback, stale writes and read-only OOC/recap.
- [x] Implement parseCommand/commandInstruction and version-checked persistence for commands/retry/undo.
- [x] Route narrator requests and video through existing services, preserving command context on resume.
- [x] Run focused tests, then complete Node and Python suites.

## Task 2: Web UI

Files: `standalone-web/web/vn/{index.html,app.js,style.css,commands.js}`.

- [x] Add command picker and keyboard navigation; command result and video previews.
- [x] Remove memory/undo buttons and persistent implementation messages; format latency as text.
- [x] Verify command selection, OOC and readable latency in the desktop browser fixture; confirmation is covered by API/unit checks. Mobile layout and full video rendering remain manual checks.

## Task 3: Documentation and deployment

Files: README, installation/architecture/operations/changelog and `docs/VN-WEB.md`.

- [x] Document current standalone topology, endpoints, commands, image lifecycle and recovery.
- [x] Review diff for secrets, validate builds/tests, deploy backend and frontend with backups.
- [x] Verify live health and temporary-save flows; save tested changes and documentation in Git.

## Execution notes

- Work is performed on an isolated source snapshot of the live server, retaining its unfinished VN Web changes; no player saves are used by tests.
- The initial macOS test run could not bind loopback for two existing local model stubs. The full suite was therefore run in a disposable Linux container with network disabled; loopback stubs work there.
- Fresh review found missing local timing rows and a stale video-dialog response. Both were reproduced by failing tests and fixed. The reviewer session stopped at its usage limit; the remaining final review was performed by the implementer.
- Additional checks covered undo after a failed local model request and rejection of video frames without provenance.
- The test UI uses synthetic story data. The in-app browser forwards chunked HTTP requests; its fixture decodes this transport, while the production Model Lab remains intended for normal LAN browser requests with Content-Length.
- Browser checks exercised command menu/filtering/keyboard selection, OOC display and readable latency. Live authenticated API checks used a separate temporary save: dice, retry with the same roll, undo, unknown-command rejection, latency and model catalog passed; the temporary save was removed. This check used synthetic narration and did not invoke a live model.

## Verified deployment

- 2026-10-28: Docker build passed 115/115 Node tests and Vite build; Python suite passed 11/11.
- Home game reports version 0.7.0. VN Web service is active and all four `/vn/` static files match deployed source.
- Source and save backups: `/opt/mcp-vn-backups/pre-v070-commands-20261028/`; PC source backup: `~/.local/share/mcp-vn-model-lab-backups/pre-v070-commands-20261028/`.
- Existing saves were preserved. No active turns or art jobs were interrupted. Full GPU video generation was not rerun.
