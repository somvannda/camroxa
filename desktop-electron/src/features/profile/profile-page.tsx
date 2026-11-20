import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../../components/page-header";
import type { ChannelProfile } from "../dashboard/account-types";
import { useAccountOverview } from "../dashboard/use-account-overview";
import { AccountCard } from "./account-card";
import { ActivityCard } from "./activity-card";
import { ChannelProfilesCard } from "./channel-profiles-card";
import { MembershipCard } from "./membership-card";
import { profileAllowance } from "./profile-format";

export function ProfilePage() {
  const query = useAccountOverview();
  const navigate = useNavigate();
  const data = query.data;
  const loading = query.isLoading;
  const profileCount = data?.profiles.length ?? 0;
  const allowance = profileAllowance(data?.me, profileCount);

  const openProfile = useCallback(
    (profile: ChannelProfile) => {
      navigate(`/settings?profile=${encodeURIComponent(profile.id)}`);
    },
    [navigate],
  );

  return (
    <div className="pb-6">
      <PageHeader
        eyebrow="Workspace"
        title="Profile"
        description="Signed-in account, credits, usage and channel profiles."
      />

      <div className="space-y-4 p-5">
        <div className="grid items-start gap-4 xl:grid-cols-[1.2fr_0.8fr]">
          <AccountCard
            me={data?.me}
            loading={loading}
            hasError={query.isError}
            onTopUp={() => navigate("/plan")}
            onManage={() => navigate("/settings")}
          />
          <MembershipCard
            me={data?.me}
            stats={data?.stats}
            license={data?.license}
            profileCount={profileCount}
            loading={loading}
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.55fr_0.75fr]">
          <ChannelProfilesCard
            profiles={data?.profiles}
            allowanceText={loading ? "--" : allowance.text}
            loading={loading}
            onOpenProfile={openProfile}
          />
          <ActivityCard stats={data?.stats} />
        </div>
      </div>
    </div>
  );
}
