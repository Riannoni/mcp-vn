# P0 render handoff — 2026-10-30, 21:07 Asia/Novosibirsk (safe after chat loss)

**READ FIRST:** \`AGENTS.md\` → \`docs/DEVELOPMENT-AND-TESTING.md\` → this file → \`docs/ROADMAP.md\`, issue [#20](https://github.com/Riannoni/web-vn/issues/20), then relevant issues/PRs. **The user requested the first-attempt production-grade sequence of one correct sprite + three consecutive complex CG, not just isolated examples. THIS HAS NOT BEEN ACHIEVED. G3/RELEASE: NO-GO.** Do not restart a GPU job or publish anything just because this file exists.

This is a **durable operational handoff**, not a successful acceptance report. A private evidence manifest on the PC, \`render-fix-20261030/private-handoff-20261030.json\` under the current user's local VN research directory, includes exact paths, SHA256s, prompt/job IDs and source references. Keep that manifest/CG/save bytes off GitHub. It existed with **16/16** referenced files at the time of this handoff (manifest SHA256 \`bc6bbc94aaa6523db873a146fbd3e98714531bb92b79ea7d448a72fb15678d46\`). If absent later, STOP and inspect before any rerun.

## UPDATE — 2026-10-30, later continuation: prop geometry experiments — NO-GO

PC SSH access via [REMOTE-ACCESS.md](REMOTE-ACCESS.md) verified; worker, vision and Comfy user services active; Comfy queue empty after testing. Original private source-job SHA256 `0bb1a6c953f3000f0a60b228015e48374e31e378c5e6810f8d3922bbee1a8231` unchanged. Production was not modified.

[Issue #44](https://github.com/Riannoni/web-vn/issues/44) now documents the current blocking defect. [Draft PR #45](https://github.com/Riannoni/web-vn/pull/45) supplies shadow-only projected object-to-shoulder scale detection (8 tests passed on PC; real prior map/shoulder ratio 2.1418 versus required maximum 1.0). [Draft PR #43](https://github.com/Riannoni/web-vn/pull/43) remains source-tested only; neither was deployed.

Controlled private GPU experiments, each exactly one attempt and without publishing:
- Bent-arm pose reference, 10.01s, Comfy prompt `8bc88b35-95bd-4dba-a941-45376eae85ca`: map too wide, **G2 FAIL**.
- Small prepositioned map in source, same other variables, 4.01s, prompt `b49e248d-3256-4fda-aeba-c227982edbf1`: map enlarged anyway, **G2 FAIL**.
- Same source/seed/pose/text, narrow edit mask with immutable map core, 4.01s, prompt `939fcb70-5148-41ca-957b-6e0a96d969c9`: small map retained but hands/contact broken, sleeve artifacts, **G2 FAIL**. Fully locked original pixels **589,170 unchanged**. Read-only production assessment: REJECT because atomic evidence unavailable, although broad semantic status was passed; QA 12.92s.

Direct original pixels inspected for all. Private candidate PNG SHA256s are indexed in issue #44 / PC private research directory; no PNG or private story in Git. **STOP random Klein prompt/mask/pose rerolls for this defect.** Next architectural step: independently controlled actor-limb staging and exact prop layer with limited contact-seam editing, or evaluate installed SDXL ControlNet structural guidance. Installed ControlNetLoader only offers `xinsir-openpose-sdxl-1.0.safetensors`, not Klein-compatible native pose conditioning. This is NOT merged/deployed, NOT first-attempt 1 sprite + 3 CG E2E, and NOT render-v1 release.

## UPDATE — 2026-10-30 22:21–22:31 Asia/Novosibirsk — PC connection + real guard regression

**Exact, tested SSH path is now documented permanently:** [docs/REMOTE-ACCESS.md](REMOTE-ACCESS.md), linked from `AGENTS.md`. Use SSH-MCP `infra_exec(host="home", as_root=true)` and, *on home*, `ssh -i /opt/homeassistant/config/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes Xavok@192.168.50.27 '<command>'`. PC is `xavok-pc`, remote login is **capital-X `Xavok`**; production VN services are **`systemctl --user`**, not system services. Do not use missing `ssh pc` alias. Never put the key contents in Git.

**Live preflight 22:21:** three `systemctl --user is-active` services `mcp-vn-comfy`, `mcp-vn-worker`, `mcp-vn-vision` were `active`; ComfyUI local `:8188/queue` running/pending both empty. Live `vision_daemon.py` SHA256 `627a2bdac2a7890a63b7936c5fcc622a535a3dc9e1d3a9e050f34f390f091f2b` and `wardrobe_contract.py` SHA256 `17804a721b3d7e435b8d1033c203e3f1ff7d7024866aec8bdd1c1ad28f7aad96` match prior PR #40 deployment; worker untouched. PC private handoff manifest exists but its SHA has changed since original 21:27 update (no longer use historical manifest digest as live); **verify current bytes every time**. Queue was a snapshot, not an indefinite GPU grant.

**Isolated code progression:** New [draft PR #43](https://github.com/Riannoni/web-vn/pull/43) depends on PR #36 and is **NOT MERGED / NOT DEPLOYED**. Adds optional typed stationary-upper-body edit mask preflight, deriving an immutable lower-shin/boots boundary from independently observed, attributed bilateral OpenPose18 knees/ankles. Missing/ambiguous landmarks fail closed; pre-existing stale-hand guard and locked pixel postcheck remain. Tests on actual PC Python: **8 new + 6 original passed**. Real private bad first-shot mask failed pre-GPU for `non_target_lower_body_editable`; real previous bounded A/B mask passed with derived lock y=427, both original hands fully editable, **535,492 exactly locked source pixels unchanged** on earlier composed output. No GPU submit, worker restart, save mutation or asset publish from this continuation.

**Original pixel images reviewed directly:** first-shot map CG (private SHA `b109d0f8...`) visibly has truncated boots (G2 FAIL). Previous bounded A/B corrected CG (private SHA `94bfaf47...`) has intact soles, map, two apparent edge-holding hands, market; however map is visibly **wider than the shoulders** against the prompt's narrower-than-shoulders instruction, and waist-length jacket accuracy is uncertain. Therefore don't call the corrected candidate full G2 PASS; contact remains at most plausible, not 3D verified. See [issue #42 latest comment](https://github.com/Riannoni/web-vn/issues/42) for details. The next independent cause to investigate is explicit actor-relative required prop geometry/scale (typed contract and positive/negative measurement), rather than further random prompt rerolls.

**Still not achieved:** clean first-attempt 1 sprite + 3 sequential complex CG, actual game/save disposable E2E, 30+ human-labeled scenes, live staged dispatcher integration and G3 release. All remain **NO-GO**. Old isolated worktree at `/opt/mcp-vn-render-wardrobe-20261030` with uncommitted work remains untouched. Separate home experiment worktree `/opt/mcp-vn-actor-policy-20261030` exists and is disposable only after safe confirmation.

## **UPDATE — 2026-10-30 21:26–21:27 Asia/Novosibirsk — deployment happened after original snapshot**

The table below describes the **21:07 pre-deployment baseline**, not current live status. **NOW DEPLOYED**: [P0 issue #39](https://github.com/Riannoni/web-vn/issues/39) / [PR #40](https://github.com/Riannoni/web-vn/pull/40), **squash-merged to main** at \`e42de14c7165033bd01142e5f72f5f7b7374e4a9\`, then manually deployed as an **exact two-file production vision patch** to the PC (\`mcp-vn-vision\` only; worker and ComfyUI untouched). Both original pre-patch production files matched their GitHub-main historical bytes exactly; a local rollback copy was taken before the atomic replacement. Live post-patch hashes:

- \`vision_daemon.py\` SHA256 \`627a2bdac2a7890a63b7936c5fcc622a535a3dc9e1d3a9e050f34f390f091f2b\`
- \`wardrobe_contract.py\` SHA256 \`17804a721b3d7e435b8d1033c203e3f1ff7d7024866aec8bdd1c1ad28f7aad96\`
- Legacy rollback copies in the PC protected research folder \`live-rollback-pr40\`; exact absolute path in private manifest.
- Restarted \`mcp-vn-vision\` and observed active \`/healthz\`; GPU queue idle. Startup briefly refused connections during the warm model load, then recovered.

**Crucial real deployed positive/negative verification, 21:26 local:** identical prior raw PNG SHA256 \`1a76766103c0e38f99f6c432f81d13b04f99a47f2ceebbe9f12c4192e4709d57\` against the actual production daemon:

| Contract on same pixels | Live \`worker.assess\` | QA duration |
|---|---|---:|
| Current blue jacket, old green cloak explicitly excluded | \`passed\`, zero reasons/warnings, CLIP face 0.9229 | 12.27s |
| Required green cloak while pixels show blue jacket | \`rejected\` with \`Wardrobe color incorrect: requested green, image shows blue\` | 12.29s |

The tested isolated helper exactly matched merged source, five unit tests passed, and no GPU generation was rerun for either QA replay. Private manifest updated SHA256 \`9399c91549782eb562768b6fc775316f9ecb2fa93a5311b5583c730ae3381e07\` (it contains the rollback path and live hashes). This is **source+deployed+isolated live QA verified FOR THE OUTFIT PARSER ONLY**. **No game/save E2E, browser publish, 3 CG continuation or global render-v1 quality proof.** Run read-only preflight again; source and live versions can drift after this timestamp.

## Exact repository and live state (must be rechecked before work)

| Dimension | 2026-10-30 observed state | Implication |
|---|---|---|
| GitHub \`main\` | \`84cfb9a672708bbf7bc368b3c17294cf6fef2bdb\` **before this handoff doc** | P0 experimental PRs **not merged** |
| Home isolated worktree | \`/opt/mcp-vn-render-wardrobe-20261030\`, HEAD \`88f812c697054b7c278686a30d7397604546bb25\`, branch \`fix/render-wardrobe-isolation-20261030\` | Many **untracked scripts** plus uncommitted \`worker/worker.py\`. **DO NOT \`git clean\`, reset, or force push.** Existing experiments depend on these. |
| Game/host | Home → SSH to PC → local private research dir; playable app is separate standalone VN Web at port 8190 | Do not conflate standalone browser client with MCP |
| PC live services | \`mcp-vn-comfy\`, \`mcp-vn-worker\`, \`mcp-vn-vision\` all active; production worker/vision ExecStart point at top-level local VN files, **not** isolated research copy | Production vision uses **older** wardrobe parser; success in shadow is NOT deployed |
| GPU queue | Comfy \`/queue\` running=[], pending=[] at 21:07 Asia/Novosibirsk | Snapshot only; recheck and identify other agents before GPU use |
| Source fixture | Read-only private source-job snapshot SHA256 \`0bb1a6c953f3000f0a60b228015e48374e31e378c5e6810f8d3922bbee1a8231\` | **Live game/save fingerprint and published-asset integrity were NOT independently rechecked in this handoff**; do not claim them proven |
| Current launch artifacts | New one-attempt sprite private canary (below); no accepted sequential three-CG run | No E2E pass, no deployment, no publish |

### Linked development streams (read before modifying)

- [Issue #31](https://github.com/Riannoni/web-vn/issues/31), [draft PR #33](https://github.com/Riannoni/web-vn/pull/33): isolate canonical facial identity from old body/outfit seed. SDXL masked Z-Image tests + sprite regressions.
- [Draft PR #35](https://github.com/Riannoni/web-vn/pull/35): SFace shadow identity metric; **synthetic identity cosine uncalibrated**.
- [Draft PR #36](https://github.com/Riannoni/web-vn/pull/36): typed two-hand map blocking, stale-limb preflight, native Klein staged Comfy graph + exact locked-pixel postcheck.
- [Issue #32](https://github.com/Riannoni/web-vn/issues/32): mandatory CG props/landmarks/physical relations; broad QA previously false accepted wrong CGs.
- [Issue #34](https://github.com/Riannoni/web-vn/issues/34), [draft PR #37](https://github.com/Riannoni/web-vn/pull/37): native Z-Image GPU reliability and overhead-arch bilateral CLIP **shadow**, not calibrated acceptance.
- [Draft PR #38](https://github.com/Riannoni/web-vn/pull/38): CPU Qwen3-VL-2B independent wall-action observation and fail-closed pure arbitration; production dispatcher **NOT** wired.
- [Issue #20](https://github.com/Riannoni/web-vn/issues/20), [#2](https://github.com/Riannoni/web-vn/issues/2), [#6](https://github.com/Riannoni/web-vn/issues/6), [#21](https://github.com/Riannoni/web-vn/issues/21), [#22](https://github.com/Riannoni/web-vn/issues/22), [#23](https://github.com/Riannoni/web-vn/issues/23): global first-attempt/E2E, golden-set, location, duplicates and outfit gates.

## Precisely reproduced root causes (DO NOT repeat blind rerolls)

1. **Old wardrobe leaks into sprites/CG**: prior full-body canonical body with historical clothing contaminates outfit change. Current masked sprite graph can preserve face and change navy outfit in ~12s GPU once; needs production integration and extended testing.
2. **Blind CG prompts lack object/action geometry**: first baseline CGs passed broad QA yet showed a basket instead of a map, and no required stone arch. The **object being present** does NOT prove both hands hold it.
3. **Extra limbs from source sprite**: on native Klein staged map CG, old down-hanging hands survived outside inpaint mask. Source DWPose coverage before fix was **48.08% / 39.62%** for old hands, resulting in a four-handed person. Enlarged mask covered **100% / 100%** and yielded coherent apparent two-hand map grip. The pure \`source_hand_mask_guard.py\` prevents this pre-GPU. \`map_grip_evidence.py\` returns at most \`plausible\`, not \`verified\`.
4. **Canonical identity through CG**: immutable face region plus explicit post-compositing preserved face in private single-shot map image; SFace cosine ~0.858, and **525,798** strictly locked original pixels were unchanged. Later arch environment-only edit kept **402,607** locked pixels unchanged, SFace ~0.855. Similarity scores are synthetic/uncalibrated and do not validate other camera angles. General guard is \`worker/staged_klein_scene.py\`.
5. **Architectural landmark false rejects**: first-shot private arch environment extension (~6.01s GPU) showed convincing overhead arch but global Florence caption failed to mention it; normal QA rejected. Three arch and five no-arch images (including two synthetic side-pillar hard negatives) were separated by **fixed left/right upper-ROI CLIP contrasts**. The \`arch_region_evidence.py\` output is advisory, not a full arch verification: no calibrated threshold, and stationary actor did NOT prove required **walking under arch**.
6. **Physical contact VLM false reports**: SmolVLM2-500M could call all three incorrect wall-adjacent poses “hands on wall”, and call the correct wall pose a ground-supported/kneeling pose. Cropping hands did NOT repair it. CPU **Qwen3-VL-2B-Instruct** locally classified **8/8** visual fixtures correctly (three wall positives, head/pavement/sides negatives, two map-holding frames) at ~5.56–6.21s per image, ~9 GB peak RAM. This is insufficient for release calibration. The pure narrow arbiter requires Qwen WALL + grounded Florence wall + correct DWPose geometry + verified location/person and only one known SmolVLM conflict.
7. **Whole-frame location QA occluded by wall**: original correct wall CG had market confidence ~0.17, below existing strict threshold. An independent Florence detector located stalls in the **left unoccluded 46.98% width** and the old CLIP threshold passed on that objective ROI, score **0.3936** (normal full shadow worker confidence 0.3851). This is not maximization over many crops.
8. **Full experimental wall QA**: read-only assessment on same original PNG with Florence location + opt-in Qwen arbiter produced \`qa_passed=true\`, location/count verified and 2D wall-contact \`plausible\`, **46.2s QA** including redundant models. The original Smol \`ground_pose=true\` contradiction remains, thus **not an acceptable production evidence payload**, and too slow for a real-time turn. Three negative full-QA frames rejected **for earlier location/semantic reasons**, so they do NOT independently prove a low false-accept rate of the wall arbiter.
9. **MAJOR NEW ROOT CAUSE: deployed vision daemon parses NEGATED historical outfit color as current.** Production top-level \`vision_daemon.py\` uses \`next(color for color in palette if regex.search(color, outfit))\`, so the current request \`navy-blue jacket ...; no old green cloak\` incorrectly selects **green** (palette order). The experimental \`worker/wardrobe_contract.py::requested_outerwear_color\` splits garment clauses and ignores exclusions; new shadow daemon uses it. This is **version skew**, not just model randomness.

## Latest first-attempt sprite experiment — what is and is not proved

Latest disposable run launched \`scripts/single_sprite_four_stage_private.py\`, derived from the validated masked sprite E2E script but forced **\`range(1)\`**, i.e. **exactly one GPU sprite attempt**. The initial systemd task with an unexported environment exited before GPU (\`VN_WORKER_TOKEN\` unavailable); corrected task exported the env, then **one** Comfy prompt actually ran. The resulting unmodified source PNG has SHA256 \`1a76766103c0e38f99f6c432f81d13b04f99a47f2ceebbe9f12c4192e4709d57\`.

- GPU generation **12.10s**; original deployed vision worker \`qa_reject\` after total **24.99s**, only reason \`Wardrobe color incorrect: requested green, image shows blue\`.
- Exactly the **same** immutable Comfy output, replayed into a **shadow updated vision daemon** (port isolated from production), returned **\`passed\`**, no reasons/warnings, **12.40s** QA, CLIP identity **0.9229**, 77.1% transparent pixels.
- Separate SFace synthetic-canonical cosine **0.80647**, **uncalibrated**. Visually manually inspected: one woman full-height in fitted navy jacket, dark trousers, boots; no old cloak, no clone. Original PNG alpha visible silhouette bbox at threshold 80 is well inside canvas. Historical canaries had four near-zero alpha pixels at corners; investigate spurious-alpha handling as a separate regression, not a reason to loosen foreground shape.
- **This is a sprite-only G1 + partial G2 artifact**, not a gameplay sprite published to the browser and NOT an accepted 1 sprite + 3 CG sequence. **STOP after first sprite** was appropriate while production QA reported a mandatory wardrobe contradiction. No linked CGs were generated in that particular fresh one-shot sequence.

Reference scripts in the isolated worktree: \`scripts/worker_masked_sprite_e2e_private.py\`, \`scripts/single_sprite_four_stage_private.py\`, \`scripts/replay_first_sprite_new_wardrobe_qa.py\`, \`worker/zimage_wardrobe.py\`, \`worker/wardrobe_contract.py\`, \`worker/vision_daemon.py\`. Actual private PNGs/manifest stay on PC.

## Prior individual CG experiments: useful BUT not a first-attempt sequence

- Native Klein first-shot map with front-view bimanual pose guide and expanded old-hand inpaint mask: visually two hands apparent on map, no obvious extra limbs, independent hand-edge relation \`plausible\`, private scene QA passed.
- Same character/map with **only architecture changed**: stone arch composited with zero locked-pixel changes, visual arch and stationary actor. Original full-frame landmark QA failed; walking under arch still **unobservable**.
- Original rear-wall contact CG looks physically plausible at original-pixel inspection and now has successful experimental full QA but not a calibrated 3D contact proof.
- These were **iteratively discovered, isolated** artifacts, with different starting assets/conditions and often different outfit requirements. **Never relabel them as the user-required first-shot 1 sprite + 3 CG test.**

## Handoff checklist: first steps for the next agent (do not ask user to repeat context)

1. Read normative files **fully**; then issue #20 and linked PRs. Query current GitHub \`main\` SHA and branches; no assumptions from numbers above.
2. Connect via SSH-MCP to \`home\` → PC. **Read-only preflight**: \`date\`, live \`mcp-vn-worker\` / \`mcp-vn-vision\` / \`mcp-vn-comfy\` status; live source file hashes and running ExecStart; Comfy \`/queue\`/\`/history\`; search competing GPU owners. Never restart/duplicate an unknown job.
3. Privately inspect \`render-fix-20261030/private-handoff-20261030.json\`, verify source/PNG SHA256s and exact job-to-Comfy history mapping, compare against original visible scene/canonical face references. Do not commit its contents.
4. **ONE NEXT MINIMAL HYPOTHESIS:** production wardrobe rejection is **entirely** the outdated first-color parser. Create an isolated regression that proves \`navy-blue jacket; no old green cloak\` → BLUE, preserves genuine \`green cloak\` → GREEN and rejects real blue-vs-green mismatch. Replay exactly the existing PNG and require the same QA outputs with unchanged thresholds; use tests in \`tests/wardrobe-contract.test.py\`. A correct parser alone does not fix CG identity/pose and must not suppress real mismatches.
5. Once proven, propose a **small separately reviewed production-compatible sync** of the vision parser + rollback; no broad branch merge. Recheck user game/save integrity and avoid concurrent deploy/GPU owners.
6. Plan **one fresh disposable game/save**, source fingerprint and typed outfit/actor/location contracts for a continuous **1 sprite + 3 CG** story. The first sprite must be accepted AND directly reviewed with SFace/alpha; all three CG must represent actual sequential action and clothing continuity. One attempt each, no rerolls, no stale-assets reuse. Need exact-view action guides, bimanual map+hand attribution, arch motion, wall contact. STOP at first mandatory failure, document all reasons.
7. Keep existing QA strict, and in the wall arbiter separate \`ground_pose\` from disputed observation so contradictory \`passed\`+misleading evidence never appears. Qwen replacement (not serial additive) should be benchmarked for end-to-end p50/p90; 46.2s QA is unacceptable as final performance.
8. Only after independently reviewed full first-attempt success: broaden to 30+ human-labeled multi-world tests including synthetic hard negatives and real-world negatives, restart/rollback, version fences, retention, latency and exact publish integrity. Until then **NO-GO**.

## Failures, STOP boundaries and security

- Never run multiple GPU jobs concurrently, blind retries, or a fourth prompt/mask variant for the same known defect.
- Never push raw private narratives, save data, face photos, generated PNG, internal IDs, secrets, model weights or unredacted logs to GitHub.
- If required actor pose is stationary, a pretty overhead arch DOES NOT meet a mandatory walking-under-arch contract.
- "Qwen answers WALL" is still not physical-contact proof in 3D. Full frame still needs exact action/location/count/identity/wardrobe/props.
- Research branch/PR accepted tests are **SOURCE READY / TESTED ISOLATED**, not MERGED, DEPLOYED or E2E VERIFIED.
- Preserve all current unknown/uncommitted research files; do not clean the worktree or move these experiments into production. Private manifest is the source of truth for exact paths.
- This doc is intentionally dated and will age. At next turn update with new actual main, worktree, PC and queue status rather than silently trusting it.
