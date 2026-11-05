# Source delivery review — 2026-10-28

Fresh isolated tests: 703 backend tests passed, 2 skipped; 572 frontend tests
passed. Full backend collection initially failed in two legacy database-reading
scripts with missing `hardware` tables against an empty in-memory database.
Those two scripts were excluded from the isolated suite; no production database
or migration was used.

Security findings: the optional limiter trusts arbitrary X-Forwarded-For values
and retains per-client buckets without eviction. It is disabled by default and
must not be represented as effective adversarial cost protection. Existing API
authentication/user isolation remains unfinished. Migration utilities default to
the local catalog path and must only be run deliberately on an approved copy.

Product limits: cores/TDP is not measured energy efficiency. The compatibility
helper's socket and TDP heuristics do not certify a complete build or PSU sizing.
The segment field requires a schema upgrade before use with older databases.

Database backups and exploratory data-research scripts remain outside this
source delivery. Historical coverage reports are not fresh database validation.
