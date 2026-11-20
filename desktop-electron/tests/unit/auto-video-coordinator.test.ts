import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { createDatabase } from "../../electron/services/database";
import { listQueue } from "../../electron/services/pipeline-queue";
import { saveVideoTemplate } from "../../electron/services/video-templates";
import { AutoVideoCoordinator } from "../../electron/services/auto-video-coordinator";
import type { ApiResponse } from "../../electron/shared/types";

const roots: string[] = [];

function tempRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "camxora-auto-video-"));
  roots.push(root);
  return root;
}

function snapshot(width: number, height: number): string {
  return JSON.stringify({
    format: "studio-project",
    version: 1,
    savedAt: new Date().toISOString(),
    project: {
      id: "p1",
      name: "Auto video",
      width,
      height,
      fps: 30,
      bpm: 120,
      markers: {},
      duration: 10,
      background: "#000000",
      creatorNote: "",
      volume: 100,
      muted: false,
      spectrumLayerColorMode: "lighten",
      spectrumLayerColorShift: 0.5,
      audioImpactMax: 0,
      globals: [],
      audioSettings: {},
    },
    nodes: [],
    layers: [],
    automations: [],
    automationGroups: [],
    analyzers: [],
    effects: [],
    assets: [],
  });
}

afterEach(() => {
  for (const root of roots.splice(0)) {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

function response(data: unknown): ApiResponse {
  return { status: 200, data, headers: {} };
}

describe("AutoVideoCoordinator", () => {
  it("enqueues a ready run with the generated background and starts the runner", async () => {
    const root = tempRoot();
    const templatesRoot = path.join(root, "templates");
    const runDir = path.join(root, "run");
    fs.mkdirSync(runDir, { recursive: true });
    fs.writeFileSync(path.join(runDir, "1. First Light.mp3"), Buffer.from("audio"));
    fs.writeFileSync(path.join(runDir, "background-16x9.png"), Buffer.from("png"));
    fs.writeFileSync(path.join(runDir, "background-9x16.png"), Buffer.from("png"));

    saveVideoTemplate({
      root: templatesRoot,
      name: "Long",
      snapshotJson: snapshot(1920, 1080),
      kind: "long",
      id: "long-1",
    });
    saveVideoTemplate({
      root: templatesRoot,
      name: "Reel",
      snapshotJson: snapshot(1080, 1920),
      kind: "reel",
      id: "reel-1",
    });

    const store = createDatabase(":memory:");
    let runnerRunning = false;
    let started = 0;
    const coordinator = new AutoVideoCoordinator({
      store,
      templatesRoot,
      isRunnerRunning: () => runnerRunning,
      startRunner: () => {
        runnerRunning = true;
        started += 1;
      },
      log: () => {},
      hasSession: () => true,
      request: async (request) => {
        switch (request.path) {
          case "/settings":
            return response({
              autoVideoAfterSuno: true,
              autoReelAfterVideo: false,
              autoMergeAfterVideo: true,
            });
          case "/profiles":
            return response([
              {
                id: "p1",
                name: "Night Shift",
                video_template_id: "long-1",
                reel_template_id: "reel-1",
              },
            ]);
          case "/progress":
            return response({
              rows: [
                {
                  batch: "b1",
                  run_date: "2026-11-20",
                  meta: {
                    batch_id: "b1",
                    profile_id: "p1",
                    role: "OK",
                    run_dir: runDir,
                    background_16x9_path: path.join(runDir, "background-16x9.png"),
                    background_9x16_path: path.join(runDir, "background-9x16.png"),
                    expected: 1,
                    saved: 1,
                    download_pending: 0,
                    download_ready: 1,
                    updated_at: "2026-11-20T10:00:00Z",
                  },
                },
              ],
            });
          case "/music/history":
            return response({
              batches: [
                {
                  batch_id: "b1",
                  ok_album: "Night Album",
                  alt_album: "Alt Album",
                  songs: [
                    {
                      title: "First Light",
                      album: "Night Album",
                      output_dir_ok: runDir,
                      downloaded_ok: true,
                    },
                  ],
                },
              ],
            });
          default:
            throw new Error(`Unexpected request ${request.path}`);
        }
      },
    });

    coordinator.start({ immediate: false });
    await coordinator.tick();
    coordinator.stop();

    const jobs = listQueue(store);
    expect(jobs).toHaveLength(1);
    expect(jobs[0]).toMatchObject({
      batchId: "b1:long",
      branch: "long",
      templateId: "long-1",
      title: "First Light",
      album: "Night Album",
      backgroundPath: path.join(runDir, "background-16x9.png"),
      merge: true,
      status: "queued",
    });
    expect(started).toBe(1);

    // A second poll never duplicates the queued row.
    coordinator.start({ immediate: false });
    await coordinator.tick();
    coordinator.stop();
    expect(listQueue(store)).toHaveLength(1);
    store.close();
  });

  it("stays idle when no video checkbox is enabled", async () => {
    const root = tempRoot();
    const store = createDatabase(":memory:");
    let requests = 0;
    const coordinator = new AutoVideoCoordinator({
      store,
      templatesRoot: path.join(root, "templates"),
      isRunnerRunning: () => false,
      startRunner: () => {
        throw new Error("The runner must not start");
      },
      log: () => {},
      hasSession: () => true,
      request: async () => {
        requests += 1;
        return response({
          autoVideoAfterSuno: false,
          autoReelAfterVideo: false,
          autoMergeAfterVideo: true,
        });
      },
    });
    coordinator.start({ immediate: false });
    await coordinator.tick();
    coordinator.stop();
    expect(requests).toBe(1);
    expect(listQueue(store)).toHaveLength(0);
    store.close();
  });

  it("renders a reel on its own when only 9:16 is checked", async () => {
    const root = tempRoot();
    const templatesRoot = path.join(root, "templates");
    const runDir = path.join(root, "run");
    fs.mkdirSync(runDir, { recursive: true });
    fs.writeFileSync(path.join(runDir, "1. First Light.mp3"), Buffer.from("audio"));
    fs.writeFileSync(path.join(runDir, "background-9x16.png"), Buffer.from("png"));
    saveVideoTemplate({
      root: templatesRoot,
      name: "Reel",
      snapshotJson: snapshot(1080, 1920),
      kind: "reel",
      id: "reel-1",
    });

    const store = createDatabase(":memory:");
    const coordinator = new AutoVideoCoordinator({
      store,
      templatesRoot,
      isRunnerRunning: () => false,
      startRunner: () => {},
      log: () => {},
      hasSession: () => true,
      request: async (request) => {
        switch (request.path) {
          case "/settings":
            return response({
              autoVideoAfterSuno: false,
              autoReelAfterVideo: true,
              autoMergeAfterVideo: false,
            });
          case "/profiles":
            return response([{ id: "p1", name: "Night Shift", reel_template_id: "reel-1" }]);
          case "/progress":
            return response({
              rows: [
                {
                  batch: "b1",
                  run_date: "2026-11-20",
                  meta: {
                    batch_id: "b1",
                    profile_id: "p1",
                    role: "OK",
                    run_dir: runDir,
                    background_9x16_path: path.join(runDir, "background-9x16.png"),
                    expected: 1,
                    saved: 1,
                    download_pending: 0,
                    download_ready: 1,
                  },
                },
              ],
            });
          case "/music/history":
            return response({
              batches: [
                {
                  batch_id: "b1",
                  songs: [
                    {
                      title: "First Light",
                      output_dir_ok: runDir,
                      downloaded_ok: true,
                    },
                  ],
                },
              ],
            });
          default:
            throw new Error(`Unexpected request ${request.path}`);
        }
      },
    });

    coordinator.start({ immediate: false });
    await coordinator.tick();
    coordinator.stop();
    const jobs = listQueue(store);
    expect(jobs).toHaveLength(1);
    expect(jobs[0]).toMatchObject({
      batchId: "b1:reel",
      branch: "reel",
      templateId: "reel-1",
      backgroundPath: path.join(runDir, "background-9x16.png"),
    });
    store.close();
  });
});
