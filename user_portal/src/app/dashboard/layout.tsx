import type { ReactNode } from "react";

import { UserControlPanelProvider } from "@/components/dashboard/control-panel-provider";
import { UserControlPanelShell } from "@/components/dashboard/control-panel-shell";

export default function DashboardLayout(props: { children: ReactNode }) {
  return (
    <UserControlPanelProvider>
      <UserControlPanelShell>{props.children}</UserControlPanelShell>
    </UserControlPanelProvider>
  );
}
