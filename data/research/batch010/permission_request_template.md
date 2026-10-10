# Draft — Data Reuse Permission Request Template

Prepared in Batch 010 (2026-10-10). This is a **draft**; it has not been sent.
It is generic enough to address a publisher's contact with the exact reuse
SPECTRA wants, so it can be adapted per publisher (TechPowerUp, PassMark,
Primate Labs/Geekbench, Intel, AMD).

---

## Re-use permission request — SPECTRA hardware catalogue

**To:** [Publisher / Data operator]
**Attn:** [Contact name / channel, if known]
**Cc:** [your name / project maintainer]
**Subject:** Request for permission to reuse [dataset / values] for a non-commercial research catalogue

Dear [name / team],

I am building **SPECTRA**, a non-commercial research catalogue of hardware
specifications and benchmark figures. SPECTRA currently stores [shortly:
technical data about CPUs, GPUs and benchmark scores] and shows them in
per-hardware detail and comparison views.

I would like to reuse [describe the data:
- for TechPowerUp: _the GPU core-clock figures for the 44 GPUs currently in our
  database, plus optionally a small set of standardized multi-GPU FPS charts
  (game, resolution, quality preset, FPS metric, GPU list)_;
- for PassMark: _the CPU catalogue fields (socket, clock speeds, cores,
  threads, TDP) shown per CPU_;
- for Geekbench / Primate Labs: _Geekbench 7 single-core and multi-core scores
  shown per CPU_;
- for Intel / AMD: _the on-site published specification values for CPUs we
  catalogue_].

**Intended use.** The values are, or will be, stored in our database and shown
(a) on per-hardware detail pages, and (b) in side-by-side comparison views.
There is no paywall, no advertising, and no monetary gain; any future
redistribution (such as exporting the dataset or publishing a copy) would
happen only if you permit it.

**Attribution.** We will clearly attribute each value to [your brand] and link
to [the source page(s) you specify].

**Questions we would like yes/no answers to:**
1. May we store and display the values described above?
2. May we cache them in our database (a local copy for serving the pages)?
3. If permission is granted for the display use, does it extend to
   redistribution of a derived dataset (export/API/published copy), and on
   what terms (attribution, share-alike, non-commercial-only)?
4. If redistribution is not permitted, should we display a "source:
   [you]" attribution and link when showing the values?

**Scope.** This request is limited to the specific data described above. We
are not asking for a general licence to your whole site, nor permission to
scrape your site; we are asking whether the specific values already (or
legitimately) sourced may be used in the described way.

If any part of the intended use is not acceptable, please tell us what is
allowed instead, or deny the specific items. We will respect your answer
exactly and remove any value you do not want used.

Thank you for your time.

[Name]
[Project / affiliation, if any]
[Contact email]

---

## Checklist before sending

- [ ] Replace every bracketed placeholder with the exact dataset and use.
- [ ] Attach a short table of the exact values intended (or offer to provide
      one on request).
- [ ] Confirm no commercial use is involved; if it ever becomes commercial,
      state that you will re-request permission.
- [ ] For TechPowerUp, use the published contact: `w1zzard@techpowerup.com`.
- [ ] Record the sent date, recipient, and the reply, and update
      `data/research/batch010/source_permission_research.md` with the response.