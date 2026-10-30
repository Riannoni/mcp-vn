# Detector-grounded architectural landmark: bilateral shadow experiment

Status: **isolated, UNCALIBRATED, NOT RELEASED**. Required read-first rules:
`AGENTS.md` -> `docs/DEVELOPMENT-AND-TESTING.md`.

## Reproduced false reject

A first-shot 6.01 s Klein CG preserving all actor, map and hand pixels had
visibly coherent masonry arch over the medieval marketplace. The existing
shadow `worker.assess` returned `qa_passed=false`, because the global
Florence-2 caption ignored the foreground arch. Florence detection gave
three boxes, but required independent caption agreement was absent.
The original CG is retained on the PC and the production QA was untouched.

## Pre-registered A/B

Fixed textual CLIP contrasts on **two fixed upper-side crops** (leftmost 36%
and rightmost 36% of full width, both upper 65% of height), not selected by
max similarity. We compare the logits of 'stone arched gateway framing the
street' and 'open medieval street without nearby arch' on each ROI.
Full-image CLIP contrast is negative even when the actual arch is clearly
visible. In a diagnostic 3 positive / 5 negative image-level sample:

| Visual reference | Left logit gap | Right logit gap |
| --- | ---: | ---: |
| Generated staged stone arch | +0.6155 | +0.2993 |
| Existing arch candidate A | +1.7700 | +2.2684 |
| Existing arch candidate B | +1.6489 | +3.0316 |
| Actual market without arch | -0.9542 | -1.2875 |
| Separate actual no-arch market | -0.9542 | -1.2909 |
| Actual masonry wall, not arch | -1.6695 | -1.6840 |
| Synthetic side columns, no vault | -1.5473 | -2.7369 |
| Synthetic edge masonry, no vault | -0.2149 | -1.9046 |

The last two hard negatives were constructed **only** from private existing
images with stone side pieces but no overhead vault. They test a shortcut and
do not constitute independent real-world validation.

`worker/arch_region_evidence.py` implements only this bounded supplementary
measurement, returning `bilateral_arch_supported` or `unobservable`, never
`verified` and never overriding semantic QA. Synthetic-fixture tests include
missing ROIs, nonfinite logits, one-sided positives and known hard negatives.
The score sign is a diagnostic text comparison, NOT a calibrated confidence
threshold. The bilateral outputs share one CLIP model, hence are not
independent modality observations.

## Still unproven

The new checker cannot prove a curved continuous overhead vault as opposed to
side pillars in unseen domains; it cannot prove an actor *walks* under the
arch. If the mandatory Scene Contract requires walking while the exact actor
pixels stay identical to the previous frame, visual motion is not established.
Do not report a full G2 pass. Full rollout needs human-labeled multisource
positives/negatives including deliberately deceptive hard examples, measured
false accepts/rejects, and independent landmark caption/geometry evidence.
Current game remains **NO-GO**, no live save or published asset changes.
