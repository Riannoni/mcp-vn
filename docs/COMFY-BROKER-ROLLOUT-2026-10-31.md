# P0 ComfyUI single-owner broker — source candidate and guarded rollout (2026-10-31)

**State: SOURCE CANDIDATE, NOT MERGED, NOT DEPLOYED, NOT E2E VERIFIED.** Independent Chief/security/operations review required before any service restart, port switch or GPU job. Read AGENTS.md and full docs/DEVELOPMENT-AND-TESTING.md first.

## Observed live facts and bypass inventory

Read-only PC snapshot ~18:57 Asia/Novosibirsk on 2026-10-31: mcp-vn-comfy, mcp-vn-worker, mcp-vn-vision, mcp-vn-model-lab and web-vn-first-shot-autonomous.timer all **active**. Podman/pasta listened on 127.0.0.1:8188, with empty queue_running and queue_pending **at that instant only**. The autonomous timer was ALREADY deployed; the prior dispatcher 27/27 PASS is historical, not evidence of cross-client GPU exclusivity.

Known independent Comfy submit sinks:
- Live mcp-vn/worker.py (~1118) and repo worker/worker.py: POST /prompt.
- Live mcp-vn-model-lab/server.py (~276) and repo standalone-web/server.py: POST /prompt.
- scripts/first_shot/autonomous_dispatch.py (~153) and run_one.py (~112): POST /prompt, previously protected only by a lab flock.
- worker/pose_reference_pipeline.py (~241) and pose_geometry_runtime.py (~40): POST /prompt.
- scripts/smoke-local-repair.py (~67); PC smoke-v62.py, v63-real-render-test.py, v64-portrait-smoke.py, model-compare-bench.py, worker_candidate.py: direct POST /prompt.
- **Additional discovered bypass: POST /api/prompt.** Installed Comfy server.py registers a /api-prefixed alias for every route, including prompt, queue, history, interrupt, free and ws.
- mcp-vn-kobold-gateway POST /free followed by ROCm KoboldCpp: not a Comfy submit, but it competes for the same physical GPU and needs an external lease.

Installed Comfy custom_nodes were also searched for prompt_queue.put and custom POST handlers: no additional queue insertion was found; Comfy Manager and rgthree expose management/configuration POST routes, not identified as GPU prompt submissions. Backups and isolated worktrees contain historical sinks, but are not active services. WebSocket /ws and /api/ws are event streams, not additional known submit sinks. Comfy server.py accepts a supplied prompt_id and queues it via prompt_queue.put; this enables a durable preallocated UUID. This audit cannot protect against a privileged host admin modifying Podman/firewall or running directly inside the container.

## Architecture

Stable URL 127.0.0.1:8188 becomes a local HTTP/WebSocket broker; Comfy's container port stays 8188 but its **host** publish changes to guarded 127.0.0.1:8189:8188. A dedicated static comfybroker UID owns the broker process. An nftables output-hook table rejects host loopback TCP port 8189 for all other socket UIDs; install and verify the rule before moving the backend. No client may fall back to 8189. Both /prompt and /api/prompt are intercepted.

SQLite WAL, synchronous FULL, BEGIN IMMEDIATE, exclusive process flock, unique idempotency key and unique preallocated prompt UUID implement one durable owner. The singleton owner row stores prompt_id and a diagnostic lease_until. A lease expiry **never** permits takeover. SUBMITTING is committed before the sole backend POST, with the exact same UUID injected into Comfy. After crash, recovery reconciles /queue and /history/{uuid}; if the job is absent or ambiguous, it holds UNCERTAIN without resubmitting. Only known terminal history (success/error/interrupted) and absence from queue releases the owner. Backend 500, malformed history, unknown queue item or foreign job fail closed.

POST /prompt returns a prompt_id receipt immediately while the job is durably queued. This avoids legacy clients' 12–15s HTTP timeout while waiting behind another GPU job. The actual backend POST is serialized until prior terminal history. A first-shot dispatcher sets an 8-second bounded queue-wait header so its 90-second GPU timer cannot admit a late 120-second queued job; other clients retain the 120-second maximum. A rejected graph or queue expiry becomes a synthetic **error** history for that UUID; never a fake success. Queue capacity is 64; only requests bearing the same explicit Idempotency-Key and matching graph payload reuse a UUID, including after restart; unkeyed /prompt and /api/prompt return 428, and different authorized action keys never deduplicate by graph equality. To deliberately repeat identical graph and seed, use a new explicit key. Private payloads are in 0700/0600 local state, not GitHub.

GET /queue and /api/queue include broker-held pending work. /history, /view, /upload/image, static HTTP routes and /ws + /api/ws text/binary pass through. Mutating /queue, /interrupt and /history are blocked. POST /free requires a matching external GPU lease. Kobold gateway now acquires a durable external lease before freeing Comfy memory, holds it through ROCm inference and process cleanup, then releases in finally; both preflight queue contention and lease-acquisition contention fall back to CPU without tripping the ROCm circuit breaker. If gateway crashes, the external lease remains fail-closed until operator inspection; no unsafe TTL takeover.

Health/metrics: /broker/health, /broker/metrics, /broker/jobs/{prompt_id}; queue depth, owner, external owner, foreign jobs, fault, stale diagnostic lease. No private prompt content in metrics.

**Protocol review risk:** broker returns number=-1 and broker_queued before backend validation; frontend, worker and Model Lab compatibility must be tested without GPU before rollout. A real Comfy 400 is surfaced later through error history. Rootless Podman admin privileges are outside the host firewall threat boundary.

## Tests and regression

CPU-only fake-Comfy tests, **zero GPU submits**: 28/28 broker, 5/5 Kobold integration, 28/28 first-shot suite PASS in the isolated home checkout (Python 3.10, aiohttp 3.13.5; Pillow installed only in isolated test target).
- Two simultaneous distinct submitters, same-key retries, restart with active prompt, crash between reservation and POST, HTTP 500 before/after acceptance, malformed queue, invalid graph, foreign queue, foreign disappearance without history, history HTTP 500, queue timeout, /api/prompt alias, websocket text/binary, raw and real multipart /api/upload/image, view/history, unsafe mutations, external lease and restart.
- Kobold gateway no-GPU tests cover lease scope, free authorization header, exception cleanup, CPU fallback without false ROCm circuit break.
- Dispatcher regression exercises pending -> running -> review_pending. Previously the code attempted path.replace from the stale pending path, causing FileNotFoundError; it now uses saved running_path.

Commands in isolated checkout:
- python3 -m unittest discover -s tests -p test_comfy_broker.py -v
- python3 -m unittest discover -s tests -p test_kobold_broker_lease.py -v
- python3 -m unittest discover -s scripts/first_shot/tests -p test_autonomous_dispatch.py -v
- python3 -m py_compile scripts/comfy_broker/broker.py deploy/kobold-gateway.py
- git diff --check

The actual PC uses Python 3.14.7 and lacks system aiohttp. An **isolated, additive review checkout** of branch 027a19ab6ade483eaed298f40a3dd2c49e7ab8e3 was staged on PC with pinned aiohttp 3.13.5 in a private test-only target: 28/28 broker, 5/5 Kobold, 28/28 first-shot PASS and py_compile PASS on Python 3.14.7, with **zero GPU jobs and zero service changes**. This is NOT an installed production venv or live client compatibility test. nftables v1.1.6 syntax was checked with **nft -c** on the PC, without applying a rule.

## External Kobold lease authentication (source-only candidate)

The external GPU lease is now **credential-gated**, not based on the caller-supplied
`client: kobold-gateway` string or the remote source IP. Both
`/broker/external/acquire` and `/broker/external/release` reject missing/invalid
bearer authorization with HTTP 401 before changing durable lease ownership.
A valid lease still persists after broker restart until an authenticated matching
release or separately approved operator reconciliation. A missing credential fails
closed; CPU fallback remains available. Source tests are **not** proof of a live
deployment or protection against root/same-UID host administration.

**Separate approved provisioning step, NOT performed by this source patch:**
generate a high-entropy random token (at least 32 bytes, e.g. 64 hex characters)
using an OS CSPRNG. Store its plaintext *only* in a `0600` regular file owned
by the gateway's distinct service UID, under a private directory; set the
gateway user service's `VN_BROKER_LEASE_TOKEN_FILE` to that absolute file path.
Never put the token itself in systemd `Environment=`, CLI arguments, Git,
journals, browser responses or PRs. Compute its SHA-256 digest offline and
provision only that lowercase digest in
`/etc/comfy-broker/external-lease.sha256`, a root-owned
`0640 root:comfybroker` regular file. The proposed broker unit requires this
digest file during startup; it must be present with correct ownership/mode
before a cutover. No automatic secret creation or rotation happens in this PR.

An unrelated local HTTP client knowing the Kobold name or even a lease ID must
not acquire/release GPU ownership without the matching token. GPU-mutating
POST /free and POST /api/free require BOTH the same bearer capability and the
current X-GPU-Lease-ID. Broker must not forward its bearer credential to ComfyUI
or backend extensions. Integration preflight must reject known lease UUIDs with
missing/wrong bearer, exercise both aliases, assert zero backend free calls,
and verify the authorized gateway supplies its file-backed capability.
The remaining preflight includes authorized acquire/release,
restart persistence and fail-closed missing-config behavior on disposable
fake-Comfy before any real GPU. The gateway and broker must receive the *same*
credential version; rotation while a lease is outstanding must retain HOLD
until a human verifies the process group and safely reconciles ownership.
This shared-token scheme does **not** authenticate individual processes that
can read the gateway UID's private file; use a separate least-privileged gateway
service UID and assess same-UID access during independent security review.
It cannot prevent a privileged Podman administrator from bypassing the OS guard.

## Explicit deployment gates — DO NOT EXECUTE UNTIL INDEPENDENT REVIEW

**G0 independent Chief review and impact:** review exact SHA, browser protocol, Model Lab, gateway, all /api aliases, lease race/timeout, firewall and rollback. Check actual live game/worker status, first-shot timer and proposal state, foreign processes and backend queue/history. R-13 already produced prompt 7b3b344b-fd8c-4068-8bd6-e541266ec174 and PNG SHA a10c347a814d4a212b8e6b02245d0c0e4ad85fb0a244457ea59d1005cc2f43ef; **never repeat**. Record a private queue snapshot and backups; do not publish prompt, image or save.

**G1 additive-only preparation:** in a separate root-owned /opt/comfy-broker install code and venv, create static comfybroker system user and private /var/lib/comfy-broker, install reviewed firewall script and units but do not move Comfy port. Validate systemd-analyze verify, nft check-only, dependency wheels, hashes, and no 8189 listener. Installing the firewall guard is permitted only in an approved maintenance window; verify non-broker UID blocked and broker UID allowed before cutover. Do not restart Comfy, worker, Lab, gateway or dispatcher in this stage.

**G2 separately approved maintenance cutover:** safely pause first-shot timer, worker, Lab and Kobold only after draining user game jobs and taking private snapshots. Verify empty backend queue and no GPU process. Back up original Quadlet, gateway, units, state and logs. Stop Comfy; change host publish only to 8189; user daemon-reload and start Comfy. Verify firewall blocks Xavok/root to 8189 and permits comfybroker. Start broker on 8188; read-only health, queue, history, view, upload and WS checks, no GPU job. Deploy matching reviewed Kobold gateway integration before resuming clients. Abort and rollback on any failed check.

**G3 after separate approval:** one disposable controlled E2E, original PNG SHA and independent G2 review, browser/worker/Model Lab compatibility, external GPU lease, restart/rollback and latency. Never change accepted assets or live saves. G3 render-v1 remains NO-GO pending broader human-labeled suite.

**Rollback order:** pause clients; inspect owner and queue; stop broker and Comfy 8189 only after known terminal history or fail closed; restore backed-up original Comfy host mapping 8188 and gateway, restart original Comfy; **only after 8189 listener is gone** remove the nft guard; resume clients after health. Keep broker SQLite and uncertain jobs for investigation, never silently retry. A stuck external lease requires proof the Kobold process group is dead before manual recovery.

## STOP / open risks

No real production-client protocol/cutover, UID/firewall enforcement or GPU E2E has been performed; only isolated PC fake-backend tests passed. No live service restarted. Any unknown direct submitter, Comfy alias, Podman admin bypass or external GPU process must be investigated before deployment. This source PR is not production readiness.

**Model: MODEL_UNVERIFIED.** Actual execution model/effort metadata was not exposed; a request for GPT-6 Astra High is not proof of execution.

## 2026-10-31 P0 review: unspecified-loopback bypass fixed in source (NO live cutover)

**Concrete counterexample to the original nft guard:** on Linux, a TCP listener bound to `127.0.0.1:8188` can also be reached with `connect("0.0.0.0", 8188)`; on this PC both read-only `GET /queue` calls returned HTTP 200 and `ip route get 0.0.0.0` reported `dev lo`. Therefore an OUTPUT filter restricted to `ip daddr 127.0.0.1` would NOT block Xavok's `0.0.0.0:8189` direct backend bypass after a naive cutover.

**Changes in this PR:** `deploy/comfy-broker-firewall` now guards **all loopback egress** to TCP 8189 by `meta oifname "lo" ... meta skuid != comfybroker_uid reject`, independent of IPv4/IPv6 destination aliases, and its `check` requires the actual full rule and an output hook. The proposed `deploy/comfyui.container` adds a rootless user Quadlet `ExecStartPre=/usr/bin/sudo -n /usr/local/libexec/comfy-broker-firewall check` so Comfy cannot bind 8189 early during an ordinary boot/restart before the SYSTEM guard is installed. This PC's Xavok has passwordless `sudo -n`; **other deployments must provision a narrowly authorized check-only sudo command**, not permit arbitrary sudo. The original quadlet must be backed up and rollback restores it.

**Actual negative/positive proof, without modifying any production firewall:** `sudo -n unshare -n` made a disposable Linux network namespace with its own `lo` and its own nft table. A synthetic broker UID (root within the test namespace) successfully connected to a dummy localhost:8189 listener using BOTH `127.0.0.1` and `0.0.0.0`. An unprivileged UID was rejected for BOTH destinations. Output: `ISOLATED_NETNS_GUARD_PASS`. The **host** nft tables were never changed. `sudo nft -c -f` against the actual proposed heredoc passed syntax-check-only. A separate isolated Podman Quadlet `-dryrun -user` generated the expected `ExecStartPre` and the new host-port `8189:8188`, without user daemon-reload or service changes.

**Regression suite on PC independent review checkout**: broker 28/28, Kobold 5/5, host firewall negative tests 6/6, first-shot tests 28/28, `py_compile` and `git diff --check` PASS. All are CPU/source-only. No Comfy POST, GPU job, active game/save mutation, firewall apply, host-port move, or service restart. Model actual runtime remains `MODEL_UNVERIFIED`.

**Required additional cutover check:** after independently reviewed G0, before resuming ANY submitter, prove from an **unprivileged** user both `GET http://127.0.0.1:8189/queue` AND `GET http://0.0.0.0:8189/queue` fail; prove the dedicated `comfybroker` UID can reach 8189 read-only and all clients reach the broker on 8188; verify firewall is loaded and Comfy boot preflight would fail if guard missing. The proposed OS rule cannot prevent a privileged host administrator from deliberately changing nftables or executing inside Xavok-owned Podman; this remains outside its trust boundary. Boot-time checks are not a substitute for monitoring later privileged ruleset mutation.

**Status unchanged:** broker is SOURCE/ISOLATED-TESTED only, PR #78 stays DRAFT pending independent reviewer + Chief, NOT MERGED / NOT DEPLOYED / NOT E2E VERIFIED. Installed Comfy still listens directly on 127.0.0.1:8188 and the already-existing first-shot timer is active. R-13 not resubmitted.
