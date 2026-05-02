"use client";

import { create } from "zustand";

type UiState = {
  currentPage: string;
  selectedTicker: string;
  strategySubMenu: string;
  runtimeStage: string;
  error: string;
  hydrated: boolean;
  hydrateFromApi: (payload: Record<string, unknown>) => void;
  setStrategySubMenu: (value: string) => void;
};

export const useUiStore = create<UiState>((set) => ({
  currentPage: "仪表盘",
  selectedTicker: "QQQ",
  strategySubMenu: "LRS TQQQ策略",
  runtimeStage: "",
  error: "",
  hydrated: false,
  hydrateFromApi: (payload) =>
    set({
      currentPage: String(payload.current_page ?? "仪表盘"),
      selectedTicker: String(payload.selected_ticker ?? "QQQ"),
      strategySubMenu: String(payload.strategy_sub_menu ?? "LRS TQQQ策略"),
      runtimeStage: String(payload.runtime_stage ?? ""),
      error: String(payload.error ?? ""),
      hydrated: true,
    }),
  setStrategySubMenu: (value) => set({ strategySubMenu: value }),
}));

