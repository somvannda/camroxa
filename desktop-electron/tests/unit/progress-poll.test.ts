import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DOWNLOADS_POLL_MS,
  PROGRESS_ACTIVE_POLL_MS,
  PROGRESS_POLL_MS,
} from "../../src/features/progress/progress-format";
import { PollController } from "../../src/features/progress/progress-poll";

async function flush(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

describe("PollController", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls immediately, then on the default 12 s cadence", async () => {
    const poll = vi.fn(async () => undefined);
    const controller = new PollController({ poll, intervalMs: () => 12_000 });
    controller.start();
    await flush();
    expect(poll).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(11_999);
    expect(poll).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(poll).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(12_000);
    expect(poll).toHaveBeenCalledTimes(3);
    controller.stop();
  });

  it("uses the 4 s active-only cadence", async () => {
    const poll = vi.fn(async () => undefined);
    const controller = new PollController({ poll, intervalMs: () => 4_000 });
    controller.start();
    await flush();
    await vi.advanceTimersByTimeAsync(4_000);
    expect(poll).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(4_000);
    expect(poll).toHaveBeenCalledTimes(3);
    controller.stop();
  });

  it("pins the page cadences: 12 s default, 4 s active, 5 s downloads", async () => {
    expect(PROGRESS_POLL_MS).toBe(12_000);
    expect(PROGRESS_ACTIVE_POLL_MS).toBe(4_000);
    expect(DOWNLOADS_POLL_MS).toBe(5_000);

    const poll = vi.fn(async () => undefined);
    const controller = new PollController({ poll, intervalMs: () => DOWNLOADS_POLL_MS });
    controller.start();
    await flush();
    await vi.advanceTimersByTimeAsync(5_000);
    expect(poll).toHaveBeenCalledTimes(2);
    controller.stop();
  });

  it("stops every timer while hidden and refreshes once on return", async () => {
    const poll = vi.fn(async () => undefined);
    const controller = new PollController({ poll, intervalMs: () => 12_000 });
    controller.start();
    await flush();
    expect(poll).toHaveBeenCalledTimes(1);

    controller.stop();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(poll).toHaveBeenCalledTimes(1);

    controller.start();
    await flush();
    expect(poll).toHaveBeenCalledTimes(2);
    controller.stop();
  });

  it("never stacks requests while one poll is in flight", async () => {
    const deferred: { resolve: (() => void) | null } = { resolve: null };
    let concurrent = 0;
    let maxConcurrent = 0;
    const poll = vi.fn(async () => {
      concurrent += 1;
      maxConcurrent = Math.max(maxConcurrent, concurrent);
      if (poll.mock.calls.length === 1) {
        await new Promise<void>((resolve) => {
          deferred.resolve = resolve;
        });
      }
      concurrent -= 1;
    });

    const controller = new PollController({ poll, intervalMs: () => 12_000 });
    controller.start();
    await flush();
    expect(poll).toHaveBeenCalledTimes(1);

    const queued = controller.trigger();
    await controller.trigger();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(poll).toHaveBeenCalledTimes(1);

    deferred.resolve?.();
    await queued;
    await flush();
    expect(poll).toHaveBeenCalledTimes(2);
    expect(maxConcurrent).toBe(1);
    controller.stop();
  });

  it("reports poll failures without breaking the loop", async () => {
    const failure = new Error("offline");
    const poll = vi
      .fn<() => Promise<void>>()
      .mockRejectedValueOnce(failure)
      .mockResolvedValue(undefined);
    const onError = vi.fn();
    const controller = new PollController({ poll, intervalMs: () => 12_000, onError });
    controller.start();
    await flush();
    expect(onError).toHaveBeenCalledWith(failure);
    await vi.advanceTimersByTimeAsync(12_000);
    expect(poll).toHaveBeenCalledTimes(2);
    controller.stop();
  });
});
