import { useMemo } from "react";

/* SPECTRA PHASE F — HARDWARE VISUAL SYSTEM (F1)
   Original, token-driven SVG primitives for CPU and GPU packages. These are
   identity illustrations, not data: every visual is aria-hidden, never labeled
   as a specific model, and never carries a measurement. Colours derive from
   the theme tokens (--spectra-vis-*) so dark and light themes both hold.
   No brand logos, no fabricated physical representations, no 3D libraries. */

const TRACE_FIELDS = [
  { id: "t1", d: "M44 128 H 88 V 168" },
  { id: "t2", d: "M128 168 H 168 V 128 H 208" },
  { id: "t3", d: "M64 168 V 208 H 128" },
  { id: "t4", d: "M168 208 H 208" },
  { id: "t5", d: "M108 168 V 208" },
];

/* A stylized processor package: substrate, die window, capacitors, pin
   matrix. Deliberately abstract — package geometry, not a real product. */
export function ProcessorVisual({ className = "" }) {
  const pins = useMemo(() => {
    const rows = [];
    for (let row = 0; row < 7; row += 1) {
      for (let col = 0; col < 7; col += 1) {
        rows.push({ key: `p${row}-${col}`, x: 62 + col * 26, y: 62 + row * 26 });
      }
    }
    return rows;
  }, []);

  const capacitors = useMemo(() => {
    const caps = [];
    for (let col = 0; col < 5; col += 1) {
      caps.push({ key: `c${col}`, x: 74 + col * 26, y: 26 });
    }
    return caps;
  }, []);

  return (
    <svg
      className={`hwv-svg ${className}`.trim()}
      viewBox="0 0 252 252"
      fill="none"
      focusable="false"
    >
      <defs>
        <linearGradient id="hwvCpuDie" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--spectra-vis-die-a)" />
          <stop offset="1" stopColor="var(--spectra-vis-die-b)" />
        </linearGradient>
        <linearGradient id="hwvCpuSubstrate" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--spectra-vis-body)" />
          <stop offset="1" stopColor="var(--spectra-vis-body-deep)" />
        </linearGradient>
      </defs>

      {/* pin matrix */}
      {pins.map((pin) => (
        <circle
          key={pin.key}
          cx={pin.x}
          cy={pin.y}
          r="3.2"
          fill="var(--spectra-vis-pin)"
        />
      ))}

      {/* substrate */}
      <rect
        x="30"
        y="30"
        width="192"
        height="192"
        rx="14"
        fill="url(#hwvCpuSubstrate)"
        stroke="var(--spectra-vis-edge)"
        strokeWidth="1.5"
      />

      {/* substrate traces under the die window */}
      <g stroke="var(--spectra-vis-signal)" strokeOpacity="0.3" strokeWidth="1.4">
        {TRACE_FIELDS.map((trace) => (
          <path key={trace.id} d={trace.d} />
        ))}
      </g>

      {/* die window */}
      <rect
        x="78"
        y="78"
        width="96"
        height="96"
        rx="8"
        fill="var(--spectra-vis-well)"
        stroke="var(--spectra-vis-edge)"
      />
      <rect
        x="94"
        y="94"
        width="64"
        height="64"
        rx="4"
        className="hwv-die"
        fill="url(#hwvCpuDie)"
      />

      {/* die grid: abstract interconnect, not a real mask */}
      <g
        stroke="var(--spectra-vis-edge)"
        strokeOpacity="0.55"
        strokeWidth="1"
      >
        <path d="M110 94 V 158 M 126 94 V 158 M 142 94 V 158" />
        <path d="M94 110 H 158 M94 126 H 158 M94 142 H 158" />
      </g>

      {/* capacitors */}
      {capacitors.map((cap) => (
        <rect
          key={cap.key}
          x={cap.x}
          y={cap.y}
          width="10"
          height="6"
          rx="1.5"
          fill="var(--spectra-vis-pin)"
        />
      ))}

      {/* corner keying notch */}
      <circle cx="42" cy="42" r="4" fill="none" stroke="var(--spectra-vis-pin)" strokeWidth="1.6" />
    </svg>
  );
}

/* Shared wrapper: an explicitly decorative hardware illustration with an
   honest caption. `label` is identity copy ("CPU"), never a data claim. */
export function HardwareVisual({
  kind,
  className = "",
  caption,
  size = "md",
}) {
  const sizeClass = `hwv-${size}`;
  const captionClass = caption ? "hwv-caption" : "hwv-caption hwv-caption-empty";
  const visual =
    kind === "gpu" ? <GraphicsVisual /> : <ProcessorVisual />;

  return (
    <div className={`hwv ${sizeClass} ${className}`.trim()} aria-hidden="true">
      <div className="hwv-frame">{visual}</div>
      {caption ? <span className={captionClass}>{caption}</span> : null}
    </div>
  );
}

/* Slot-sized visual used inside build slots and comparison slots. The same
   primitives render in a smaller frame with a soft signal well behind them.
   M2: adds stylized slot visuals for the four new Build Planner categories
   (RAM stick, drive, board, PSU box). Same identity-illustration rules:
   abstract geometry, aria-hidden, theme tokens only. */
export function HardwareSlotVisual({ kind, className = "" }) {
  let visual;
  if (kind === "gpu") {
    visual = <GraphicsVisual />;
  } else if (kind === "ram") {
    visual = <RamStickVisual />;
  } else if (kind === "storage") {
    visual = <DriveVisual />;
  } else if (kind === "motherboard") {
    visual = <BoardVisual />;
  } else if (kind === "psu") {
    visual = <PsuBoxVisual />;
  } else {
    visual = <ProcessorVisual />;
  }

  return (
    <span className={`hwv-slot ${className}`.trim()} aria-hidden="true">
      {visual}
    </span>
  );
}

/* A stylized DIMM stick seen edge-on: PCB, chips, connector edge. */
export function RamStickVisual({ className = "" }) {
  return (
    <svg
      viewBox="0 0 320 160"
      fill="none"
      focusable="false"
      className={`hwv-svg hwv-slot-svg ${className}`.trim()}
      role="presentation"
    >
      <rect x="30" y="40" width="260" height="64" rx="6" fill="var(--spectra-vis-body)" />
      <rect x="30" y="96" width="260" height="14" rx="3" fill="var(--spectra-vis-body-deep)" />
      {[0, 1, 2, 3, 4, 5, 6, 7].map((chip) => (
        <rect
          key={chip}
          x={44 + chip * 30}
          y={56}
          width={22}
          height={30}
          rx={3}
          fill="var(--spectra-vis-die-a)"
          opacity="0.85"
        />
      ))}
    </svg>
  );
}

/* A stylized drive seen face-on: enclosure, label well, connector notch. */
export function DriveVisual({ className = "" }) {
  return (
    <svg
      viewBox="0 0 320 160"
      fill="none"
      focusable="false"
      className={`hwv-svg hwv-slot-svg ${className}`.trim()}
      role="presentation"
    >
      <rect x="34" y="36" width="252" height="88" rx="8" fill="var(--spectra-vis-body)" />
      <rect x="52" y="54" width="140" height="52" rx="4" fill="var(--spectra-vis-die-b)" opacity="0.7" />
      <rect x="216" y="54" width="52" height="52" rx="4" fill="var(--spectra-vis-body-deep)" />
    </svg>
  );
}

/* A stylized motherboard seen face-on: board, socket well, slot rows. */
export function BoardVisual({ className = "" }) {
  return (
    <svg
      viewBox="0 0 320 160"
      fill="none"
      focusable="false"
      className={`hwv-svg hwv-slot-svg ${className}`.trim()}
      role="presentation"
    >
      <rect x="34" y="24" width="252" height="112" rx="8" fill="var(--spectra-vis-body)" />
      <rect x="56" y="44" width="56" height="56" rx="4" fill="var(--spectra-vis-die-a)" opacity="0.85" />
      {[0, 1, 2, 3].map((slot) => (
        <rect
          key={slot}
          x={132}
          y={40 + slot * 24}
          width={132}
          height={12}
          rx={3}
          fill="var(--spectra-vis-body-deep)"
        />
      ))}
    </svg>
  );
}

/* A stylized power supply seen face-on: enclosure, fan well, cable face. */
export function PsuBoxVisual({ className = "" }) {
  return (
    <svg
      viewBox="0 0 320 160"
      fill="none"
      focusable="false"
      className={`hwv-svg hwv-slot-svg ${className}`.trim()}
      role="presentation"
    >
      <rect x="34" y="36" width="252" height="88" rx="8" fill="var(--spectra-vis-body)" />
      <circle cx="120" cy="80" r="34" fill="var(--spectra-vis-die-b)" opacity="0.7" />
      <rect x="196" y="56" width="72" height="48" rx="4" fill="var(--spectra-vis-body-deep)" />
    </svg>
  );
}

/* A stylized graphics card seen face-on in its shroud: die cluster, memory
   packages, power connector. Abstract geometry, not a real board layout. */
export function GraphicsVisual({ className = "" }) {
  const fins = useMemo(() => {
    const list = [];
    for (let i = 0; i < 12; i += 1) {
      list.push({ key: `f${i}`, x: 96 + i * 12 });
    }
    return list;
  }, []);

  return (
    <svg
      className={`hwv-svg ${className}`.trim()}
      viewBox="0 0 252 188"
      fill="none"
      focusable="false"
    >
      <defs>
        <linearGradient id="hwvGpuDie" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--spectra-vis-die-a)" />
          <stop offset="1" stopColor="var(--spectra-vis-die-b)" />
        </linearGradient>
        <linearGradient id="hwvGpuShroud" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="var(--spectra-vis-body)" />
          <stop offset="1" stopColor="var(--spectra-vis-body-deep)" />
        </linearGradient>
      </defs>

      {/* shroud */}
      <rect
        x="16"
        y="30"
        width="220"
        height="128"
        rx="14"
        fill="url(#hwvGpuShroud)"
        stroke="var(--spectra-vis-edge)"
        strokeWidth="1.5"
      />

      {/* die + memory cluster */}
      <rect
        x="42"
        y="52"
        width="66"
        height="56"
        rx="6"
        className="hwv-die"
        fill="url(#hwvGpuDie)"
      />
      <g stroke="var(--spectra-vis-edge)" strokeOpacity="0.5" strokeWidth="1">
        <path d="M58 52 V 108 M 75 52 V 108 M 92 52 V 108" />
      </g>

      {[
        { key: "m1", x: 122, y: 52 },
        { key: "m2", x: 176, y: 52 },
        { key: "m3", x: 122, y: 122 },
        { key: "m4", x: 176, y: 122 },
      ].map((mod) => (
        <rect
          key={mod.key}
          x={mod.x}
          y={mod.y}
          width="40"
          height="28"
          rx="4"
          fill="var(--spectra-vis-well)"
          stroke="var(--spectra-vis-edge)"
        />
      ))}

      {/* power connector */}
      <rect
        x="196"
        y="36"
        width="28"
        height="12"
        rx="3"
        fill="var(--spectra-vis-pin)"
      />
      <path d="M202 36 V 48 M 210 36 V 48 M 218 36 V 48" stroke="var(--spectra-vis-well)" strokeWidth="1.4" />

      {/* heatsink fins below the shroud */}
      <g stroke="var(--spectra-vis-pin)" strokeOpacity="0.5" strokeWidth="2">
        {fins.map((fin) => (
          <path key={fin.key} d={`M${fin.x} 166 V 178`} />
        ))}
      </g>

      {/* bracket */}
      <path
        d="M16 44 V 144"
        stroke="var(--spectra-vis-edge)"
        strokeWidth="4"
        strokeLinecap="round"
      />
      {[
        { key: "dp1", y: 66 },
        { key: "dp2", y: 92 },
        { key: "dp3", y: 118 },
      ].map((port) => (
        <rect
          key={port.key}
          x="12"
          y={port.y}
          width="8"
          height="12"
          rx="2"
          fill="var(--spectra-vis-pin)"
        />
      ))}
    </svg>
  );
}
