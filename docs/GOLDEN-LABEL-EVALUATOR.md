# Offline golden-label evaluator (source-only, NOT a release gate)

This isolated helper summarizes candidate-bound independent human labels versus
shadow QA decisions for [#2](https://github.com/Riannoni/web-vn/issues/2)
and the render-v1 tracker [#20](https://github.com/Riannoni/web-vn/issues/20).
It **does not** inspect PNG pixels, authenticate a reviewer, verify that two
scenes are independent, perform E2E, or permit publishing. Even 30 passing rows
produce `NO_GO_SOURCE_ONLY`.

Input is a **private local** UTF-8 JSON file (do not commit images, save
snapshots, story, face references, or unredacted prompts):

```json
{
  "samples": [
    {
      "scene_id": "neutral-heldout-001",
      "first_attempt": true,
      "source_state_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "candidate_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "mandatory": ["props", "contact"],
      "human": {
        "independent": true,
        "candidate_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "verdicts": {"props": "verified", "contact": "violated"}
      },
      "qa": {
        "candidate_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "decision": "accept",
        "verdicts": {"props": "verified", "contact": "unobservable"}
      }
    }
  ]
}
```

Run: `python3 -B scripts/golden-label-eval.py /path/to/private-labels.json`.
Run regression tests: `python3 -B tests/golden-label-eval.test.py -v`.
Python standard library only. No browser, GPU, API, model or worker imports.

A mandatory verdict must be one of `verified`, `violated`, or
`unobservable`; `not_applicable` is invalid for mandatory checks. Missing,
invalid or cross-candidate evidence rejects the **whole dataset** with exit
code 2 rather than silently skipping rows. Human `unobservable` is reported
as unresolved, not counted as a grounded false accept. QA `accept` with
mandatory `unobservable` or `violated` is counted as unsafe acceptance.
False accepts require human `violated`; false rejects require all mandatory
human verdicts `verified`. First-attempt coverage is reported separately.

`independent=true` and unique scene IDs are caller assertions, not proof of
independent review or independent source scenes. The SHA-256 fields bind
reported verdicts to a candidate by value; the tool cannot verify hashes
against image bytes. Keep original PNGs, contracts, reviewer records and
provenance privately for independent pixel review. The output contains only
aggregate counts and cannot upgrade G2/G3 to PASS.

**Scope:** this helper is not wired into production QA or release automation.
Its metrics are suitable only for a manually reviewed, separately audited
candidate dataset. A future integration must verify image bytes and
independent reviewers and implement an actual gated E2E before release.
