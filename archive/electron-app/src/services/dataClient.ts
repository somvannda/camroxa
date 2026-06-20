import type { AppData, HistoryItem } from "../../shared/app-types";

export const dataClient = {
  async getData(): Promise<AppData> {
    if (!window.mgApi) throw new Error("Database is required. Launch the Electron app to use MusicGenerator.");
    return await window.mgApi.getData();
  },
  async setData(data: AppData) {
    if (!window.mgApi) throw new Error("Database is required. Launch the Electron app to use MusicGenerator.");
    return await window.mgApi.setData(data);
  },
  async appendHistory(item: HistoryItem) {
    if (!window.mgApi) throw new Error("Database is required. Launch the Electron app to use MusicGenerator.");
    return await window.mgApi.appendHistory(item);
  },
  async reset(): Promise<AppData> {
    if (!window.mgApi) throw new Error("Database is required. Launch the Electron app to use MusicGenerator.");
    return await window.mgApi.reset();
  },
  async closeWindow() {
    if (!window.mgApi) throw new Error("Database is required. Launch the Electron app to use MusicGenerator.");
    return await window.mgApi.closeWindow();
  },
};

