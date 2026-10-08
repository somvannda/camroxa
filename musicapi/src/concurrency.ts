/**
 * Concurrency gate for Suno-backed work.
 *
 * A small Suno account pool (or a single-account pool) cannot absorb an
 * unbounded burst of jobs: every job calls `pool.pick()` and submits to Suno
 * in parallel, so a spike produces 429s / captcha challenges / charged-then-
 * refunded churn. This gate admits at most `max()` jobs at once across the
 * process, and at most `cap` at once for any single owner (a user, so all of a
 * user's API keys share one budget; `"system"` for jobs with no user).
 *
 * Admission is FIFO and slot-based: a job is only counted once it is admitted,
 * so a waiting job never holds a slot and cannot deadlock the pool. Because
 * `max` is evaluated on every admission, adding a Suno account raises capacity
 * without a restart.
 */
/** Thrown by `acquire()` when the waiting queue is at its configured bound. */
export class QueueFullError extends Error {
  constructor() {
    super("Job queue is full.");
    this.name = "QueueFullError";
  }
}

export class ConcurrencyGate {
  private active = 0;
  private readonly ownerActive = new Map<string, number>();
  private readonly waiting: Array<{ owner: string; cap: number; resolve: () => void }> = [];

  /**
   * @param max     Global admission ceiling (re-evaluated per admission).
   * @param maxQueue Maximum jobs allowed to wait; `<= 0` means unbounded. When
   *                 the queue is full, `acquire()` rejects with `QueueFullError`
   *                 so a flood cannot accumulate unbounded pending jobs.
   */
  constructor(
    private readonly max: () => number,
    private readonly maxQueue: number | (() => number) = 0,
  ) {}

  /** Current waiting-queue bound; supports a live getter (admin-editable). */
  private maxQueueLimit(): number {
    return typeof this.maxQueue === "function" ? this.maxQueue() : this.maxQueue;
  }

  /**
   * Resolve once both a global slot and an owner slot are free, or reject with
   * `QueueFullError` if the waiting queue is already at `maxQueue`. On success
   * the caller MUST invoke the returned release function exactly once (typically
   * in a `finally`).
   */
  acquire(owner: string, cap: number): Promise<() => void> {
    if (this.canStart(owner, cap)) {
      this.start(owner);
      return Promise.resolve(() => this.release(owner));
    }
    const maxQueue = this.maxQueueLimit();
    if (maxQueue > 0 && this.waiting.length >= maxQueue) {
      return Promise.reject(new QueueFullError());
    }
    return new Promise<() => void>((resolve) => {
      this.waiting.push({ owner, cap, resolve: () => resolve(() => this.release(owner)) });
    });
  }

  private release(owner: string): void {
    if (this.active > 0) this.active -= 1;
    const remaining = (this.ownerActive.get(owner) ?? 0) - 1;
    if (remaining > 0) this.ownerActive.set(owner, remaining);
    else this.ownerActive.delete(owner);
    this.pump();
  }

  private canStart(owner: string, cap: number): boolean {
    if (this.active >= Math.max(1, this.max())) return false;
    return (this.ownerActive.get(owner) ?? 0) < Math.max(1, cap);
  }

  private start(owner: string): void {
    this.active += 1;
    this.ownerActive.set(owner, (this.ownerActive.get(owner) ?? 0) + 1);
  }

  /** Admit as many waiting jobs as slots allow, in arrival order. */
  private pump(): void {
    for (let i = 0; i < this.waiting.length; ) {
      const entry = this.waiting[i];
      if (this.canStart(entry.owner, entry.cap)) {
        this.waiting.splice(i, 1);
        this.start(entry.owner);
        entry.resolve();
      } else {
        i += 1;
      }
    }
  }

  /** Snapshot for the admin `/metrics` view. */
  stats(): { active: number; waiting: number; maxQueue: number } {
    return { active: this.active, waiting: this.waiting.length, maxQueue: this.maxQueueLimit() };
  }
}
