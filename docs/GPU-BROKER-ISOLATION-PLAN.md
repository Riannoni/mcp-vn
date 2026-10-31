# S-09 — ComfyUI single-broker OS isolation migration (NO APPLY)

**Decision: BLOCKED for live authority; source-only proposal and tests only.**
Issue #20, G2 **UNVERIFIED**, G3 **NO_GO**. Do not deploy, restart, submit
GPU jobs, edit live saves or reinterpret mock claims as OS proof.

## Observation and one falsifiable hypothesis

Read-only PC inspection on 2026-10-31 (private evidence:
\`evidence/reliability/S-09-topology/inspection-private.txt\`, SHA256
\`714691999a49ccb3884ce568369a00f8bd77d2e6c95ba2e339afa17e2ad4a0f1\`):

- \`mcp-vn-worker\` and \`mcp-vn-vision\` are active **user** systemd services
  under UID 1000, in the host network namespace. Worker launches the
  Python worker directly. No \`PrivateNetwork\` or \`NetworkNamespacePath\`.
- \`mcp-vn-comfy\` is an active user Quadlet/Podman container, **rootless
  pasta** network, \`127.0.0.1:8188:8188\` host publish. Its container
  network namespace differs from the host; the host \`pasta\` listener
  is nevertheless reachable from local processes. Same user controls
  Podman and worker. SELinux is enforcing, but Comfy's launch includes
  \`--security-opt label=disable\`; this is **not** a broker ACL.
- Socket inventory confirms a host \`127.0.0.1:8188\` pasta listener.
  This is a read-only point-in-time observation, **not** a durable
  queue/history or proof of exclusive ownership.
- Six executable literal \`/prompt\` source sinks were found by the S-07
  scanner (paths/lines only; active worker duplicates repository code):

  | Sink | Observed line | Migration requirement |
  | --- | ---: | --- |
  | \`active/worker.py\` | 1118 | remove direct POST; use broker |
  | \`worker/worker.py\` | 1118 | remove direct POST; use broker |
  | \`worker/pose_geometry_runtime.py\` | 40 | remove direct POST; use broker |
  | \`worker/pose_reference_pipeline.py\` | 241 | remove direct POST; use broker |
  | \`standalone-web/server.py\` | 276 | remove direct POST; use broker |
  | \`scripts/smoke-local-repair.py\` | 67 | remove direct POST; use broker |

  Dynamic route construction, imported packages, other local processes,
  unlisted plugins and container peers remain **UNKNOWN**, not absent.

**Hypothesis:** with both worker and Podman controlled by the same UID and
Comfy published on host loopback, a client can bypass any voluntary
SQLite broker fence with a direct socket connection. This is supported by
the service topology and source sinks, not by a live POST experiment.
**Falsifier:** after a separately approved OS migration, independently
demonstrate that every non-broker identity (including same-host scripts,
web server, a container peer and foreign process) cannot even establish
a direct Comfy connection, while the isolated broker can, and that
crash/unknown-prompt reconciliation remains fail-closed. No such live
proof exists yet.

## Proposed owner-approved boundary — NOT implemented

1. Create **root-managed** service identities, e.g. \`webvn-comfy\` and
   \`webvn-broker\`, distinct from each other and from the interactive
   \`Xavok\` UID. Give neither untrusted clients nor the interactive
   user sudo/Podman management access to the new service identities.
   Preserve required AMD \`/dev/kfd\`, \`/dev/dri\`, model mounts and
   ROCm permissions with the narrowest reviewed access. Separate
   source/save ownership from Comfy model/cache ownership.
2. Create a root-owned **private network namespace** with loopback
   available to the broker and Comfy only, no host port publish, no
   unreviewed veth/pasta forwarding or container-peer join. Run both
   services in that namespace but with different UIDs. Rootless Podman
   \`pasta\` must **not** silently re-expose \`8188\`: validate actual
   namespace membership and effective listener after migration. A
   different Podman network mode or a non-containerized Comfy launch
   may be required; compatibility on Bazzite/ROCm is **UNPROVEN**.
3. Expose a **root-managed Unix-domain socket** for the broker API
   with peer-credential verification and restrictive group ACL.
   The broker, not clients, owns Comfy's private TCP connection and
   a durable single-writer journal. Client-supplied \`reviewer_sha\`,
   \`queue_generation\` or claimed isolation hashes are **not trusted**.
4. Route every known direct sink through the broker; discover and
   constrain dynamic/foreign routes before claiming coverage.
   Reject all unknown clients, unverified scene/save/version,
   expired fence, history gap, foreign prompt, ambiguous post-submit
   outcome or restart. Record intent durably **before** POST, then
   prompt ID and recovery state; never blind retry after a timeout.
5. Obtain independent OS/namespace/socket ACL attestation and
   negative bypass probes from all actor classes. Verify exact source
   save hashes and accepted assets unchanged. Only an owner-approved
   separate live change may enable GPU; S-09 code **never does**.

### No-apply service/network template (illustrative, not runnable)

These are configuration *sketches* for an owner-reviewed root-managed
migration, **not commands to execute or install**. Exact service wrappers,
user namespaces, Quadlet integration, GPU permissions, socket activation,
SELinux labels and systemd version compatibility must be engineered and
tested in a disposable staging namespace first.

\`\`\`ini
# PROPOSAL ONLY: root-managed system service for Comfy
[Service]
User=webvn-comfy
Group=webvn-comfy
NetworkNamespacePath=/run/netns/webvn-gpu-private
NoNewPrivileges=yes
# ExecStart=<reviewed Comfy wrapper, NO --publish, NO pasta host forward>
# DeviceAllow=<reviewed AMD GPU device rules>
# ReadWritePaths=<only Comfy private cache/output>
\`\`\`

\`\`\`ini
# PROPOSAL ONLY: broker system service, distinct UID, same private netns
[Service]
User=webvn-broker
Group=webvn-broker
NetworkNamespacePath=/run/netns/webvn-gpu-private
NoNewPrivileges=yes
# ExecStart=<reviewed durable broker executable>
# StateDirectory=<root-managed broker journal>
# RuntimeDirectory=<broker socket directory>
# Socket peer-credential + ACL must be enforced by the actual broker
\`\`\`

\`\`\`ini
# PROPOSAL ONLY: root-managed socket unit
[Socket]
ListenStream=/run/webvn-broker/admit.sock
SocketMode=0660
SocketGroup=webvn-client
# SocketUser/RuntimeDirectory/SELinux labels to be verified on target OS
\`\`\`

A \`PrivateNetwork=yes\` on **only** the worker, an app-level token, a
loopback listener, a source scan, \`iptables -m owner\` alone, or a mock
localhost request is **insufficient** to prove all bypasses blocked.
The existing rootless same-UID Podman setup cannot establish a trusted
boundary without owner-approved OS identity/network/service changes.

## Migration, negative verification and rollback (all deferred)

**Preflight/approval:** owner authorizes a maintenance window, a distinct
privileged operator, temporary disruption, backup of current user units,
Quadlet, service account/group membership and Podman settings, tested
ROCm access, and rollback. Record exact service/image/source SHA and
live queue/history before any change; if unknown, STOP.

**Staged cutover:** prepare a disposable private namespace; validate
Comfy + broker there; keep admission DENY. Migrate six sinks and discover
dynamic clients. Test host-loopback, direct worker, pose, reference,
web, smoke, foreign and container-peer **TCP denial** (no GPU POST).
Use independent reviewer/attestor, not the migration operator. Verify
only the broker can reach Comfy. Demonstrate durable queue generation,
intent-before-POST, unknown-response quarantine, prompt history recovery,
restart and version-fence tests in an isolated disposable environment.
Do not enable GPU if any mandatory check is unobservable.

**Rollback:** set broker admission DENY and stop new requests; preserve
durable journal, prompt IDs and current queue; reconcile in-flight/
unknown submissions and original save/asset hashes before stopping
anything. Restore backed-up user services/network **only with owner
approval and a safe controlled maintenance plan**. Never reopen an
unfenced direct \`/prompt\` path as an automatic fallback. If the
legacy mode must be restored for gameplay, explicitly mark GPU broker
authority **disabled**, require a separate risk decision and do not
claim G2/G3.

## Source-only negative gate

\`scripts/render_gpu_os_isolation_plan.py\` is a **pure, DENY-only**
checklist; \`assess_isolation_plan\` always returns
\`can_submit_gpu=false\`. Six known sinks, distinct UIDs, removed host
publish, private namespace, container-peer isolation, independent
attestation and a complete bypass matrix, durable intent and unknown
prompt/history/restart reconciliation are all required even for a
\`candidate_unverified\`. Self-reported strings/hashes are **not**
trusted live proof. Unit tests include every sink omitted individually,
direct localhost/container-peer bypass, same-UID, self-attestation,
missing actor, crash and history gap. A fully claimed plan still denies
GPU authorization.

**Exact unverified OS preconditions:** privileged account and namespace
migration approved; real rootless Podman/pasta isolation feasible on
target Bazzite/ROCm; GPU device permissions; root-owned broker-only UDS;
complete dynamic/foreign process inventory; independent negative
host/container-peer probes; trustworthy queue generation/history and
atomic crash recovery; full visual G2 and 30+ labeled G3. Until then:
**BLOCKED live integration / G2 UNVERIFIED / G3 NO_GO**.
