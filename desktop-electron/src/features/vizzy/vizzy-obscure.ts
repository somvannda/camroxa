import { create } from "zustand";

/**
 * Frozen frame of the native Vizzy view while a transient shell overlay (the
 * notifications dropdown) hides it. A `WebContentsView` always paints above the
 * shell DOM, so the overlay needs the view hidden; the snapshot keeps the
 * editor visible behind it instead of the "Starting the Vizzy editor" placeholder.
 */
interface VizzyObscureState {
  snapshot: string | null;
  setSnapshot: (snapshot: string | null) => void;
}

export const useVizzyObscure = create<VizzyObscureState>((set) => ({
  snapshot: null,
  setSnapshot: (snapshot) => set({ snapshot }),
}));
