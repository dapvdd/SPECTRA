/**
 * M4 Task 7: workload profile metadata for the intelligence UI.
 *
 * Mirrors the backend registry (backend/app/services/workload_profiles.py,
 * M4-PROFILES-v1.0). Kept free of React so it runs under `node --test`.
 * Labels/assumptions here are display metadata; the backend remains the
 * single source of truth for scoring — profiles never invent evidence.
 */

export const WORKLOAD_PROFILE_VERSION = "M4-PROFILES-v1.0";

export const WORKLOAD_PROFILE_KEYS = [
  "esports_gaming",
  "aaa_gaming",
  "general_productivity",
  "software_development",
  "video_editing",
  "rendering_3d",
  "virtualization_homelab",
  "ai_ml_experimentation",
];

export const PROFILES = {
  esports_gaming: {
    key: "esports_gaming",
    label: "Esports gaming",
    description: "High-frame-rate competitive titles at 1080p/1440p.",
    supportedPreferences: ["resolution", "budget_max", "priority", "existing_components"],
    assumptions: [
      "Uses CPU Geekbench 7 multi-core as the gaming proxy; no game-specific FPS measurements exist in this dataset.",
      "Does not claim measured FPS at any resolution; resolution preference is advisory context only.",
      "No GPU gaming benchmarks exist in this dataset, so GPU gaming suitability is spec-based and capped.",
    ],
  },
  aaa_gaming: {
    key: "aaa_gaming",
    label: "AAA gaming",
    description: "GPU-heavy modern titles at 1440p/4k.",
    supportedPreferences: ["resolution", "budget_max", "priority", "existing_components"],
    assumptions: [
      "CPU side uses Geekbench 7 multi-core; GPU side is spec-based (VRAM/bandwidth) and capped at 3 stars because no GPU gaming benchmark data exists.",
      "Never reports expected FPS at a resolution.",
      "Assumes higher VRAM/bandwidth helps at higher resolution — a qualitative spec argument, not a measured one.",
    ],
  },
  general_productivity: {
    key: "general_productivity",
    label: "General productivity",
    description: "Office, browsing, media, everyday multitasking.",
    supportedPreferences: ["budget_max", "priority", "power_limit_w", "existing_components"],
    assumptions: [
      "Daily-use scenario weights single-core responsiveness (Geekbench 7 single-core) and efficiency (score-per-watt).",
      "Does not measure application launch times or battery life.",
    ],
  },
  software_development: {
    key: "software_development",
    label: "Software development",
    description: "Coding, compiling, containers, local VMs.",
    supportedPreferences: ["budget_max", "priority", "power_limit_w", "existing_components"],
    assumptions: [
      "Compilation/build throughput is proxied by Geekbench 7 multi-core; IDE responsiveness by single-core.",
      "Does not measure project-specific compile times.",
    ],
  },
  video_editing: {
    key: "video_editing",
    label: "Video editing",
    description: "Timeline editing, exports, effects.",
    supportedPreferences: ["budget_max", "priority", "power_limit_w", "existing_components"],
    assumptions: [
      "Proxy: Geekbench 7 multi-core for export/encode; no application-specific video benchmark data exists.",
      "Does not claim codec-specific performance (no such data).",
    ],
  },
  rendering_3d: {
    key: "rendering_3d",
    label: "3D rendering",
    description: "CPU/GPU render workloads.",
    supportedPreferences: ["budget_max", "priority", "power_limit_w", "existing_components"],
    assumptions: [
      "CPU render proxy: Geekbench 7 multi-core.",
      "GPU render/compute claims are NOT made: no GPU compute benchmarks exist in this dataset; GPU suitability is spec-based only.",
    ],
  },
  virtualization_homelab: {
    key: "virtualization_homelab",
    label: "Virtualization & homelab",
    description: "Multi-VM hosts, containers, NAS/services.",
    supportedPreferences: ["budget_max", "priority", "power_limit_w", "existing_components"],
    assumptions: [
      "Proxy: multi-core throughput plus core count; RAM capacity requirements are NOT modeled (no VM memory sizing data).",
      "Does not estimate VM density.",
    ],
  },
  ai_ml_experimentation: {
    key: "ai_ml_experimentation",
    label: "AI/ML experimentation",
    description: "Local model inference/experimentation, dataset work.",
    supportedPreferences: ["budget_max", "priority", "power_limit_w", "existing_components"],
    assumptions: [
      "No GPU/VRAM compute benchmarks exist in this dataset: AI/ML GPU suitability is NOT scored.",
      "CPU-side proxy: Geekbench 7 multi-core for data preprocessing; no training-throughput claims.",
    ],
  },
};

export const formatProfileLabel = (key) =>
  PROFILES[key]?.label || key;

/**
 * Normalize one profile payload (from a v2 response or the local registry)
 * into display-ready fields.
 */
export const formatWorkloadProfile = (profile) => ({
  key: profile?.key || null,
  label: profile?.label || formatProfileLabel(profile?.key),
  description: profile?.description || "",
  assumptions: Array.isArray(profile?.assumptions) ? profile.assumptions : [],
  supportedPreferences: Array.isArray(profile?.supportedPreferences)
    ? profile.supportedPreferences
    : [],
});
