/**
 * Undo/redo over exactly four mutation shapes.
 *
 * Every edit in the editor is expressed as one of UndoOp: a value change, an
 * object insertion, an object removal, or a reorder. Recording the *inverse*
 * next to the forward action keeps the stack trivially correct and means new
 * features only need to describe themselves in those terms.
 */

export interface HistoryEntry {
  label: string;
  undo: () => void;
  redo: () => void;
}

export class History {
  private stack: HistoryEntry[] = [];
  private cursor = -1;
  private listeners = new Set<() => void>();

  /** Drop every entry, e.g. after loading a different project. */
  clear(): void {
    this.stack.length = 0;
    this.cursor = -1;
    this.emit();
  }

  push(entry: HistoryEntry): void {
    // Drop the redo tail.
    this.stack.length = this.cursor + 1;
    this.stack.push(entry);
    this.cursor = this.stack.length - 1;
    this.emit();
  }

  undo(): HistoryEntry | null {
    if (this.cursor < 0) return null;
    const entry = this.stack[this.cursor];
    entry.undo();
    this.cursor -= 1;
    this.emit();
    return entry;
  }

  redo(): HistoryEntry | null {
    if (this.cursor >= this.stack.length - 1) return null;
    this.cursor += 1;
    const entry = this.stack[this.cursor];
    entry.redo();
    this.emit();
    return entry;
  }

  canUndo(): boolean {
    return this.cursor >= 0;
  }

  canRedo(): boolean {
    return this.cursor < this.stack.length - 1;
  }

  labels(): string[] {
    return this.stack.map((e) => e.label);
  }

  onChange(fn: () => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(): void {
    for (const fn of this.listeners) fn();
  }
}

/** Coalesce rapid slider drags into one history entry. */
export class Coalescer {
  private lastKey: string | null = null;
  private lastAt = 0;

  shouldCoalesce(key: string, windowMs = 400): boolean {
    const now = performance.now();
    const same = this.lastKey === key && now - this.lastAt < windowMs;
    this.lastKey = key;
    this.lastAt = now;
    return same;
  }

  reset(): void {
    this.lastKey = null;
  }
}
