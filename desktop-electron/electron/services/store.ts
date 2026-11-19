import path from "node:path";
import { createDatabase, type Store } from "./database";
import { getAppPaths } from "./paths";

let store: Store | null = null;

export function initStore(): Store {
  if (store) return store;
  store = createDatabase(path.join(getAppPaths().userData, "camxora.db"));
  return store;
}

export function getStore(): Store {
  if (!store) throw new Error("Store not initialised");
  return store;
}

export function closeStore(): void {
  store?.close();
  store = null;
}
