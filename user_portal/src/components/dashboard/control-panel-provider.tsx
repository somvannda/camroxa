"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { clearSession } from "@/lib/auth";
import {
  getCurrentUser,
  getProfilesStatus,
  listProfiles,
  type CurrentUserResponse,
  type ExistingProfile,
} from "@/lib/channel-setup";
import {
  listMyBillingPayments,
  type BillingPayment,
} from "@/lib/billing";
import { getWalletBalance, type WalletBalanceResponse } from "@/lib/credits";
import { getQuotaStatus, type QuotaStatus } from "@/lib/quota";
import {
  getMusicHistory,
  type MusicHistoryResponse,
} from "@/lib/music-history";
import { getWebsiteBaseUrl } from "@/lib/site-urls";
import {
  listMyRedeemHistory,
  type RedeemHistoryItem,
} from "@/lib/redeem-codes";
import { getDashboardStats, type DashboardStats } from "@/lib/stats";
import {
  getNotificationCenter,
  getSecurityOverview,
  type NotificationCenter,
  type SecurityOverview,
} from "@/lib/control-panel";
import { getUserSettings, type UserSettings } from "@/lib/settings";
import { logoutSession } from "@/lib/platform-api";

export type ControlPanelState = {
  user: CurrentUserResponse | null;
  profiles: ExistingProfile[];
  wallet: WalletBalanceResponse | null;
  quota: QuotaStatus | null;
  redemptions: RedeemHistoryItem[];
  stats: DashboardStats | null;
  musicHistory: MusicHistoryResponse | null;
  payments: BillingPayment[];
  settings: UserSettings;
  notifications: NotificationCenter | null;
  security: SecurityOverview | null;
};

type ControlPanelContextValue = {
  state: ControlPanelState;
  loading: boolean;
  websiteBaseUrl: string;
  signOut: () => Promise<void>;
  reloadAll: () => Promise<void>;
  refreshCreditsAndActivity: () => Promise<void>;
  refreshNotifications: () => Promise<void>;
  refreshSecurity: () => Promise<void>;
  setState: React.Dispatch<React.SetStateAction<ControlPanelState>>;
};

const DEFAULT_STATE: ControlPanelState = {
  user: null,
  profiles: [],
  wallet: null,
  quota: null,
  redemptions: [],
  stats: null,
  musicHistory: null,
  payments: [],
  settings: {},
  notifications: null,
  security: null,
};

const ControlPanelContext = React.createContext<ControlPanelContextValue | null>(null);

export function UserControlPanelProvider(props: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = React.useState<ControlPanelState>(DEFAULT_STATE);
  const [loading, setLoading] = React.useState(true);

  const websiteBaseUrl = getWebsiteBaseUrl();

  const reloadAll = React.useCallback(async () => {
    const [
      user,
      status,
      profiles,
      wallet,
      quota,
      redemptions,
      stats,
      musicHistory,
      payments,
      settings,
      notifications,
      security,
    ] = await Promise.all([
      getCurrentUser(),
      getProfilesStatus(),
      listProfiles().catch(() => []),
      getWalletBalance().catch(() => null),
      getQuotaStatus().catch(() => null),
      listMyRedeemHistory(8).catch(() => []),
      getDashboardStats().catch(() => null),
      getMusicHistory(4).catch(() => null),
      listMyBillingPayments(8).catch(() => []),
      getUserSettings().catch(() => ({})),
      getNotificationCenter().catch(() => null),
      getSecurityOverview().catch(() => null),
    ]);

    if (status.profile_count < 2) {
      router.replace("/onboarding");
      return;
    }

    setState({
      user,
      profiles,
      wallet,
      quota,
      redemptions,
      stats,
      musicHistory,
      payments,
      settings,
      notifications,
      security,
    });
  }, [router]);

  const refreshCreditsAndActivity = React.useCallback(async () => {
    const [wallet, quota, redemptions, stats, musicHistory, payments] = await Promise.all([
      getWalletBalance().catch(() => null),
      getQuotaStatus().catch(() => null),
      listMyRedeemHistory(8).catch(() => []),
      getDashboardStats().catch(() => null),
      getMusicHistory(4).catch(() => null),
      listMyBillingPayments(8).catch(() => []),
    ]);

    setState((current) => ({
      ...current,
      wallet,
      quota,
      redemptions,
      stats,
      musicHistory,
      payments,
    }));
  }, []);

  const refreshNotifications = React.useCallback(async () => {
    const notifications = await getNotificationCenter().catch(() => null);
    setState((current) => ({
      ...current,
      notifications,
    }));
  }, []);

  const refreshSecurity = React.useCallback(async () => {
    const [security, settings] = await Promise.all([
      getSecurityOverview().catch(() => null),
      getUserSettings().catch(() => ({})),
    ]);
    setState((current) => ({
      ...current,
      security,
      settings,
    }));
  }, []);

  React.useEffect(() => {
    let cancelled = false;

    async function initialize() {
      try {
        await reloadAll();
      } catch {
        if (!cancelled) {
          router.replace("/login");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void initialize();

    return () => {
      cancelled = true;
    };
  }, [reloadAll, router]);

  const signOut = React.useCallback(async () => {
    try {
      await logoutSession();
    } catch {}
    clearSession();
    router.replace("/login");
  }, [router]);

  const value = React.useMemo<ControlPanelContextValue>(
    () => ({
      state,
      loading,
      websiteBaseUrl,
      signOut,
      reloadAll,
      refreshCreditsAndActivity,
      refreshNotifications,
      refreshSecurity,
      setState,
    }),
    [loading, refreshCreditsAndActivity, refreshNotifications, refreshSecurity, reloadAll, signOut, state, websiteBaseUrl],
  );

  return (
    <ControlPanelContext.Provider value={value}>
      {props.children}
    </ControlPanelContext.Provider>
  );
}

export function useControlPanel() {
  const context = React.useContext(ControlPanelContext);
  if (!context) {
    throw new Error("useControlPanel must be used within UserControlPanelProvider.");
  }
  return context;
}
