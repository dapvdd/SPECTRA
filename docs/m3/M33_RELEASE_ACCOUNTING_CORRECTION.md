# M3.3 Release Accounting Correction (M3.4 Task 1)

**Date**: 2026-11-26
**Author**: M3.4 Project Fortress (autonomous)
**Subject**: Corrective accounting for `docs/m3/M33_PRODUCTION_RELEASE_REPORT.md`
**Baseline SHA (deployed production)**: `5c2c7d9a37109da99f20a34973503d1bd6deb236`

## 1. Why this correction exists

The M3.3 production release report contains two accounting claims that do not
survive measurement scrutiny:

1. **"The downtime budget (<60 s) was met for actual service unavailability."**
   This treats deliberate operator verification pauses as non-downtime. From
   the outside (a user of `http://100.113.157.0:8080`), the API answered
   nothing between `compose down` completion and the first healthy response —
   regardless of *why* the service was down. Downtime is measured by the
   service's availability, not the operator's intent.

2. **"Observation window: 2026-11-25 15:30Z → 17:02Z (>90 min total uptime …)"**
   The service was not up for that window. From first-healthy at 16:03:37Z to
   the last spot check at ~17:02Z is **~58 minutes** of post-healthy
   stabilization, not 90+ minutes of uptime.

This document does not rewrite the original report (it remains in the repo,
unaltered). It corrects the record and defines the canonical accounting for
M3.4 onward.

## 2. Canonical downtime taxonomy (mandatory from M3.4 on)

| Metric | Definition | How measured |
|---|---|---|
| **User-visible downtime** | First moment the API stops answering (`compose down` complete / last failed request) → first healthy+ready response. | Wall clock, no subtractions of any kind. |
| Application startup latency | Container start → first healthy probe pass. | Health-probe timestamps. |
| Migration duration | DB copy+upgrade+swap elapsed, while service is down. | Script timestamps. |
| Operator verification latency | Elapsed time consumed by deliberate human/agent pauses (checksums, compose authoring, staging checks) while the service is down. | Wall clock between milestone timestamps not attributable to startup or migration. |
| Total deployment duration | Beginning of service interruption → acceptance complete. | Wall clock. |
| Post-healthy stabilization | First healthy → end of the observation window. | Wall clock. |

**Rule**: only user-visible downtime counts against the downtime budget.
Operator pauses are *inside* it. "Reversible at any moment by `compose up`"
does not make an unavailable service available.

## 3. Corrected M3.3 accounting (recomputed from the report's own milestones)

Source milestones (M3.3 report §10, UTC):

- 15:30:13 compose down complete (writes end)
- 15:43:38 copy-swap migration done
- 16:03:01 compose up complete
- 16:03:37 first healthy+ready confirmed

| Metric | Corrected value | Basis |
|---|---|---|
| **User-visible downtime** | **33 min 24 s** (15:30:13 → 16:03:37) | First unhealthy moment → first healthy. No subtractions. |
| Application startup latency | ~36 s (16:03:01 → 16:03:37) | compose-up complete → first healthy. |
| Migration duration | 13 min 25 s (15:30:13 → 15:43:38) | Includes checksum verification performed while down. |
| Operator verification latency | ~19 min (15:43:38 → 16:03:01, compose authoring/checks) | Deliberate, but service-down nonetheless. |
| Total deployment (interruption → acceptance) | ≥ 33 min 24 s | Acceptance continued after healthy. |
| Post-healthy stabilization | **~58 min** (16:03:37 → ~17:02) | Not 90 min. The ">90 min total uptime" claim conflated the pre-down window with uptime. |

The earlier "~60 s effective downtime" figure is retained only as
*application startup latency + container restart granularity*, which is NOT
user-visible downtime. The <60 s downtime budget was **not met** for the M3.3
cutover; it was met only for the mechanical stop→start cycle in isolation.

## 4. The M3.4 downtime target

M3.4 Task 5 (deployment automation) moves every step that does not require the
service to be down (image build, backup, migration rehearsal, candidate DB
preparation, config authoring) into the pre-interruption window, so the
remaining user-visible downtime is compose-down → candidate-swap → healthy,
measured honestly. Target: **< 60 s user-visible**, measured by the Task 5
orchestrator's downtime JSON (first-healthy minus down-complete; zero
subtractions), validated in an isolated rehearsal before any production use.

## 5. Annotated release tag (prepared, pending owner approval)

A annotated tag message has been prepared for `5c2c7d9a37109da99f20a34973503d1bd6deb236`:

```
tag: m33-production-5c2c7d9
type: annotated (not pushed; owner approval pending)
message: |
  SPECTRA M3.3 production release (deployed 2026-11-25)

  Deployed SHA: 5c2c7d9a37109da99f20a34973503d1bd6deb236
  Images: spectra-backend|m33-rc-5c2c7d9

  Accounting correction (M3.4 Task 1):
  - User-visible downtime: 33 min 24 s (15:30:13Z-16:03:37Z), not <60 s.
  - Post-healthy stabilization: ~58 min, not >90 min.
  - See docs/m3/M33_RELEASE_ACCOUNTING_CORRECTION.md
```

To activate after owner approval: `git tag -a m33-production-5c2c7d9 <sha> -m "$(cat tag-message.txt)" && git push origin m33-production-5c2c7d9`
(prepared in Task 8 delivery; NOT executed here).
