import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { buildComparisonEvidence } from "../../../frontend/src/comparisonEvidence.js";
import { buildComparisonDecisionSummary } from "../../../frontend/src/comparisonDecision.js";

const DB_PATH = "C:/SPECTRA/data/spectra.db";
const EXPECTED_SHA = "20e1b7386df88da72ac6628b9b1efab9539c7895475d7b57f2289271c17b1127";

const results = { checks: [], warnings: [], verdict: null };

function check(name, passed, detail = "") {
  results.checks.push({ name, passed, detail });
  if (!passed) results.warnings.push(`FAILED: ${name} — ${detail}`);
}

// 1. Database integrity
const dbData = readFileSync(DB_PATH);
const sha = createHash("sha256").update(dbData).digest("hex");
check("database_sha256_unchanged", sha === EXPECTED_SHA, `expected ${EXPECTED_SHA}, got ${sha}`);

const db = new DatabaseSync(DB_PATH);
const quick = db.prepare("PRAGMA quick_check").get();
check("database_quick_check_ok", quick.quick_check === "ok", JSON.stringify(quick));

const fk = db.prepare("PRAGMA foreign_key_check").all();
check("database_foreign_key_check_empty", fk.length === 0, `fk violations=${fk.length}`);

// 2. Benchmark scores unchanged
const scores = db.prepare(
  "SELECT score, test_type FROM benchmark_results WHERE hardware_id = 1508 ORDER BY id"
).all();
check(
  "benchmark_scores_unchanged",
  scores.length >= 2 && scores[0].score === 695.0 && scores[1].score === 2005.0,
  `hardware 1508: ${JSON.stringify(scores.slice(0, 2))}`
);

const benchCount = db.prepare("SELECT COUNT(*) AS c FROM benchmark_results").get();
check("benchmark_count_unchanged", benchCount.c === 1040, `count=${benchCount.c}`);

// 3. Evidence separation logic
const cpuA = { id: 1, name: "CPU A", type: "CPU", manufacturer: "AMD",
  specifications: { cores: 24, threads: 48, base_clock_ghz: 3.2, boost_clock_ghz: 5.1, tdp_w: 125 } };
const cpuB = { id: 2, name: "CPU B", type: "CPU", manufacturer: "Intel",
  specifications: { cores: 16, threads: 32, base_clock_ghz: 3.2, boost_clock_ghz: 5.1, tdp_w: 125 } };

const benchA = { status: "success", results: [
  { benchmark_name: "Geekbench 7", score: 24000, unit: "points", test_type: "multi-core" },
  { benchmark_name: "Geekbench 7", score: 12000, unit: "points", test_type: "single-core" },
]};
const benchB = { status: "success", results: [
  { benchmark_name: "Geekbench 7", score: 18000, unit: "points", test_type: "multi-core" },
  { benchmark_name: "Geekbench 7", score: 9000, unit: "points", test_type: "single-core" },
]};

const evidence = buildComparisonEvidence([cpuA, cpuB], { 1: benchA, 2: benchB });
check(
  "evidence_separates_benchmark_from_spec",
  evidence !== null && evidence.benchmark.wins.cpuA === 2 && evidence.specification.wins.cpuA === 2,
  `benchmark wins=${JSON.stringify(evidence?.benchmark?.wins)}, spec wins=${JSON.stringify(evidence?.specification?.wins)}`
);

check(
  "evidence_benchmark_coverage_complete",
  evidence?.benchmark?.coverage?.isComplete === true,
  `coverage=${JSON.stringify(evidence?.benchmark?.coverage)}`
);

const evidenceSpecOnly = buildComparisonEvidence([cpuA, cpuB]);
check(
  "evidence_spec_only_benchmark_empty",
  evidenceSpecOnly?.benchmark?.measurableCount === 0 && evidenceSpecOnly?.specification?.wins?.cpuA === 2,
  `benchmark measurable=${evidenceSpecOnly?.benchmark?.measurableCount}, spec wins=${JSON.stringify(evidenceSpecOnly?.specification?.wins)}`
);

const evidencePartial = buildComparisonEvidence([cpuA, cpuB], { 1: benchA });
check(
  "evidence_partial_benchmark_coverage",
  evidencePartial?.benchmark?.coverage?.isPartial === true,
  `coverage=${JSON.stringify(evidencePartial?.benchmark?.coverage)}`
);

// 4. Decision summary includes evidence
const summary = buildComparisonDecisionSummary([cpuA, cpuB], { 1: benchA, 2: benchB });
check(
  "decision_summary_includes_evidence",
  summary?.evidence !== null && summary?.evidence?.benchmark?.wins?.cpuA === 2,
  `evidence present: ${"evidence" in (summary || {})}`
);

// 5. No fabricated GPU benchmark data
const gpuBench = db.prepare(
  "SELECT COUNT(*) AS c FROM benchmark_results b JOIN hardware h ON b.hardware_id = h.id WHERE h.type = 'GPU'"
).get();
check("no_gpu_benchmark_data", gpuBench.c === 0, `gpu benchmark rows=${gpuBench.c}`);

// 6. .opencode/ not tracked
import { execSync } from "node:child_process";
const opencodeTracked = execSync("git ls-files .opencode", { cwd: "C:/SPECTRA" }).toString().trim();
check("opencode_not_tracked", opencodeTracked === "", `tracked: ${opencodeTracked}`);

// 7. Git diff check
try {
  execSync("git diff --check", { cwd: "C:/SPECTRA" });
  check("git_diff_check_clean", true);
} catch (e) {
  check("git_diff_check_clean", false, e.stdout?.toString() || e.message);
}

// 8. Verify no backend files were changed
const { execSync: exec } = await import("node:child_process");
const changedFiles = exec("git diff --name-only HEAD", { cwd: "C:/SPECTRA" }).toString().trim();
const backendChanged = changedFiles.split("\n").some(f => f.startsWith("backend/"));
check("no_backend_changes", !backendChanged, `changed: ${changedFiles}`);

const allPassed = results.checks.every(c => c.passed);
results.verdict = allPassed ? "PASS" : "FAIL";

console.log(JSON.stringify(results, null, 2));

const { writeFileSync } = await import("node:fs");
writeFileSync("C:/SPECTRA/data/research/batch012/independent_audit.json", JSON.stringify(results, null, 2));

process.exit(allPassed ? 0 : 1);
