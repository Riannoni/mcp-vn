# REAL GPU first-shot five-frame checkpoint — 2026-10-31

**Experiment, not production.** Public redacted outcome for the first new disposable, source-frozen pack. Raw PNGs, exact prompt content, original user references and private per-case pixel reviews remain on game PC at `~/.local/share/web-vn-native-team/first-shot-lab-20261031/`. No game save, accepted image, deployed worker, or user story was modified. Executed directly with `scripts/first_shot/run_one.py --submit` in an isolated source checkout, one Comfy job at a time; no automatic retries.

| Case | Submit→PNG wall s | G1 | Independent direct original-pixel G2 | First mandatory failure |
|---|---:|---|---|---|
| BG-01 | 11.040 | PASS | PASS | none: market, stalls, stone arch, no principal foreground |
| SPR-01 | 7.029 | PASS | FAIL | RGB opaque white background, no sprite alpha; closed jacket issue; canonical identity not linked |
| CG-01 | 6.024 | PASS | FAIL | OPEN instead of folded map; exact actor/environment reference continuity unobservable |
| CG-02 | 5.050 | PASS | FAIL | duplicate second/open box on stall; scene continuity/identity unverified |
| CG-03 | 6.028 | PASS | FAIL | virtually upright stance vs required clear forward wall lean; face identity unobservable |

- **5/5 first GPU jobs succeeded in <20 s**; P50 submit-to-image 6.028 s, max 11.040 s. These measurements include polling/client overhead but exclude postprocess, independent pixel review, narrator latency and complete game end-to-end QA. **Do not claim full turn <20 s.**
- **1/5 G2 passes** in the frozen *public synthetic* pack, 0/5 production canonical character games accepted. The real user's private scenes still need separate source-bound benchmark; no inference from synthetic actor appearance to canonical visual identity.
- **0 new human labels**; all five original images were visually inspected directly by the assistant, **not independent human raters**, and specific failures recorded with SHA-bound private reports. This does not count as the release 30-scene human set.
- **G3 NO_GO**: 5/5 complete first-shot sprite+three CG end-to-end not met, identity/wardrobe/landmarks/contact not reliable across cases.
- No GPU parallelism benchmark yet. Single GPU submission serially: lower latency and no VRAM conflict; next CPU QA can be pipelined while next GPU renders.

## Immediate causal priorities

1. **QA/sprite:** run first-attempt output through a CPU alpha-cutout stage; validate silhouette, hair and limbs; measure stage duration. Do not call RGB PNG a sprite. Need actual private canonical face anchor to claim identity.
2. **Renderer/quality:** use real source-bound native Z-Image Union pose/inpaint or validated identity adapter; locked environment plate and actor/outfit ROI. Fix **one factor** per controlled hypothesis. Two CGs differ in background and character face: T2I alone is demonstrably insufficient for continuity, despite speed.
3. **CG contact:** exact-view pose before GPU, verify BOTH hands and forward lean with actual original-pixel evidence, don't equate proximity with contact.
4. **Reliability/speed:** instrument actual Comfy GPU stage vs queue, postprocess and QA. Investigate why live browser showed ~100 s complete and ~60–80 s QA even though isolated native T2I is only 5–11 s; no invented latency reductions.
5. **Golden:** independently read original PNG and exact private contract/ref; keep `violated/unobservable` failures, handoff without private imagery/public faces. Get 30 truly independent human labels later for release.

## Stop condition and next checkpoint

Do not optimize GPU speed further while 5/5 are already below 20 s. Direct effort to visual correctness and real game integration. Next useful user-visible result is **at least BG + alpha-valid sprite + 1 story CG with verified original pixels and measurable postprocess/QA latency**. Never call a CPU-processed second picture a new first GPU attempt; it is a derived output from the same first shot and requires its own full G2 check. Existing source-only tasks R-10/Q-09/G-08/S-11 require independent Chief SHA/evidence review; their tests alone do not close the G2 gap.

## Traceability

The exact private `BG-01-result.json` etc and `*-pixel-review.json` are bound to Comfy prompt IDs and PNG SHA256 in a 0700 lab directory. `scripts/first_shot/scoreboard.py` independently re-hashes the output bytes and refuses a PASS without a directly reviewed SHA/prompt-matched original. The score is re-computable on PC and should be included in every Chief report.
