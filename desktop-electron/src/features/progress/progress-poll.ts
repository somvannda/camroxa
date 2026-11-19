/**
 * Single-flight interval runner for the Progress page (PG-44…PG-48).
 *
 * - one request at a time; a trigger during a request coalesces into one
 *   follow-up run instead of stacking;
 * - `stop()` cancels the timer and prevents re-arming after an in-flight poll;
 * - `start()` polls immediately, which is also what a visible page does when
 *   it returns (PG-47).
 */
export interface PollControllerOptions {
  poll: () => Promise<unknown>;
  intervalMs: () => number;
  onError?: (error: unknown) => void;
}

export class PollController {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private inFlight = false;
  private queued = false;
  private stopped = true;

  constructor(private readonly options: PollControllerOptions) {}

  get isRunning(): boolean {
    return !this.stopped;
  }

  get isPolling(): boolean {
    return this.inFlight;
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    void this.run();
  }

  stop(): void {
    this.stopped = true;
    this.queued = false;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  /** Immediate refresh. Safe to call while another poll is running. */
  trigger(): Promise<void> {
    return this.run();
  }

  private arm(): void {
    if (this.stopped) return;
    if (this.timer) clearTimeout(this.timer);
    const delay = Math.max(0, this.options.intervalMs());
    this.timer = setTimeout(() => {
      this.timer = null;
      void this.run();
    }, delay);
  }

  private async run(): Promise<void> {
    if (this.inFlight) {
      this.queued = true;
      return;
    }
    this.inFlight = true;
    try {
      await this.options.poll();
    } catch (error) {
      try {
        this.options.onError?.(error);
      } catch {
        // An error reporter must never wedge the scheduler.
      }
    }
    this.inFlight = false;
    if (this.stopped) return;
    if (this.queued) {
      this.queued = false;
      void this.run();
      return;
    }
    this.arm();
  }
}
