import test from "node:test";
import assert from "node:assert/strict";

import {
  buildSignalProfile,
  formatSignalCount,
  getSignalPrimaryLabel,
  getSignalStatusLabel,
} from "./signalProfile.js";

const record = (id, type, manufacturer) => ({
  id,
  name: `Hardware ${id}`,
  type,
  manufacturer,
});

test("an empty or invalid catalog reports an empty profile", () => {
  [undefined, null, [], "nope", {}, 7].forEach((input) => {
    assert.deepEqual(buildSignalProfile(input), {
      isEmpty: true,
      total: 0,
      channels: [],
      manufacturers: [],
    });
  });
});

test("channels are the real counts of the real catalog", () => {
  const profile = buildSignalProfile([
    record(1, "CPU", "Intel"),
    record(2, "CPU", "AMD"),
    record(3, "CPU", "Intel"),
    record(4, "GPU", "NVIDIA"),
    record(5, "GPU", "AMD"),
  ]);

  assert.equal(profile.isEmpty, false);
  assert.equal(profile.total, 5);
  assert.deepEqual(
    profile.channels.map(({ label, value }) => ({ label, value })),
    [
      { label: "CPU", value: 3 },
      { label: "GPU", value: 2 },
    ]
  );
});

test("channel share is a proportion of the real total, never progress", () => {
  const profile = buildSignalProfile([
    record(1, "CPU", "Intel"),
    record(2, "CPU", "Intel"),
    record(3, "CPU", "AMD"),
    record(4, "GPU", "NVIDIA"),
  ]);

  const cpu = profile.channels.find((channel) => channel.label === "CPU");
  const gpu = profile.channels.find((channel) => channel.label === "GPU");

  assert.equal(cpu.share, 75);
  assert.equal(gpu.share, 25);

  const summed = profile.channels.reduce((sum, c) => sum + c.share, 0);
  assert.equal(Math.round(summed), 100);
  assert.ok(cpu.share < 100, "a share must not read as completion");
});

test("unknown types become their own channel rather than being dropped", () => {
  const profile = buildSignalProfile([
    record(1, "CPU", "Intel"),
    record(2, "GPU", "NVIDIA"),
    record(3, "TPU", "Google"),
  ]);

  assert.equal(profile.total, 3);
  assert.deepEqual(
    profile.channels.map((channel) => channel.label),
    ["CPU", "GPU", "TPU"]
  );
});

test("CPU always precedes GPU regardless of catalog order or volume", () => {
  const profile = buildSignalProfile([
    record(1, "GPU", "NVIDIA"),
    record(2, "GPU", "NVIDIA"),
    record(3, "GPU", "NVIDIA"),
    record(4, "CPU", "Intel"),
  ]);

  assert.deepEqual(
    profile.channels.map((channel) => channel.label),
    ["CPU", "GPU"]
  );
});

test("records missing a type or manufacturer are still counted in the total", () => {
  const profile = buildSignalProfile([
    record(1, "CPU", "Intel"),
    { id: 2, name: "No type" },
    { id: 3, name: "No type", type: "  " },
    null,
    "not a record",
  ]);

  assert.equal(profile.total, 1);
  assert.deepEqual(profile.channels, [
    { label: "CPU", value: 1, share: 100 },
  ]);
  assert.deepEqual(profile.manufacturers, [{ label: "Intel", value: 1 }]);
});

test("manufacturers are ranked by volume and capped", () => {
  const hardware = [
    record(1, "CPU", "Intel"),
    record(2, "CPU", "Intel"),
    record(3, "CPU", "AMD"),
    record(4, "GPU", "NVIDIA"),
    record(5, "GPU", "Intel"),
    record(6, "GPU", "Zhaoxin"),
    record(7, "GPU", "Moore Threads"),
  ];

  const profile = buildSignalProfile(hardware);

  assert.deepEqual(profile.manufacturers, [
    { label: "Intel", value: 3 },
    { label: "AMD", value: 1 },
    { label: "NVIDIA", value: 1 },
    { label: "Zhaoxin", value: 1 },
  ]);
});

test("a single-type catalog reports a full share without implying progress", () => {
  const profile = buildSignalProfile([record(1, "CPU", "Intel")]);

  assert.deepEqual(profile.channels, [
    { label: "CPU", value: 1, share: 100 },
  ]);
});

test("counts are formatted with real digit grouping", () => {
  assert.equal(formatSignalCount(5239), "5,239");
  assert.equal(formatSignalCount(0), "0");
  assert.equal(formatSignalCount(-4), "0");
  assert.equal(formatSignalCount(undefined), "0");
  assert.equal(formatSignalCount(Number.NaN), "0");
});

test("signal labels reflect real load state, never a guess", () => {
  const loaded = buildSignalProfile([record(1, "CPU", "Intel")]);

  assert.equal(getSignalPrimaryLabel(loaded), "Catalog composition");
  assert.equal(getSignalPrimaryLabel({ isEmpty: true }), "Catalog profile");
  assert.equal(getSignalStatusLabel(loaded), "Verified records");
  assert.equal(getSignalStatusLabel(loaded, { loading: true }), "Loading");
  assert.equal(getSignalStatusLabel(loaded, { error: "boom" }), "Unavailable");
  assert.equal(getSignalStatusLabel({ isEmpty: true }), "No records");
});

test("building the profile is deterministic for the same catalog", () => {
  const hardware = [
    record(1, "GPU", "NVIDIA"),
    record(2, "CPU", "Intel"),
    record(3, "CPU", "AMD"),
  ];

  assert.deepEqual(buildSignalProfile(hardware), buildSignalProfile(hardware));
});