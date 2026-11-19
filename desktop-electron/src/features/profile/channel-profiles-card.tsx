import { Card } from "../../components/card";
import { Table, TBody, TD, TH, THead, TR } from "../../components/table";
import type { ChannelProfile } from "../dashboard/account-types";
import {
  imageModeLabel,
  sortProfiles,
  visibilityLabel,
} from "./profile-format";

const COLUMNS = ["Name", "Run Prefix", "Output Resolution", "Image Mode", "Visibility"];

interface ChannelProfilesCardProps {
  profiles: ChannelProfile[] | null | undefined;
  allowanceText: string;
  loading: boolean;
  onOpenProfile: (profile: ChannelProfile) => void;
}

export function ChannelProfilesCard({
  profiles,
  allowanceText,
  loading,
  onOpenProfile,
}: ChannelProfilesCardProps) {
  const rows = sortProfiles(profiles);

  return (
    <Card className="p-5" data-testid="profile-channels">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-title font-semibold text-text-primary">Channel Profiles</h2>
          <p className="mt-1 text-body text-text-secondary">
            Profiles available for generation and publication workflows.
          </p>
        </div>
        <span className="shrink-0 text-meta text-text-secondary text-tabular">{allowanceText}</span>
      </div>

      <div className="mt-4">
        <Table>
          <THead>
            <TR className="hover:bg-surface-2">
              {COLUMNS.map((column) => (
                <TH key={column}>{column}</TH>
              ))}
              <TH className="w-[1%]">
                <span className="sr-only">Actions</span>
              </TH>
            </TR>
          </THead>
          <TBody>
            {loading ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMNS.length + 1} className="text-text-secondary">
                  Loading profiles...
                </TD>
              </TR>
            ) : rows.length === 0 ? (
              <TR className="hover:bg-transparent">
                <TD colSpan={COLUMNS.length + 1} className="text-text-secondary">
                  No channel profiles found yet.
                </TD>
              </TR>
            ) : (
              rows.map((profile) => (
                <TR key={profile.id}>
                  <TD className="max-w-[220px] truncate font-medium">{profile.name}</TD>
                  <TD className="text-text-secondary">{profile.run_prefix || "--"}</TD>
                  <TD className="text-text-secondary">{profile.output_resolution || "--"}</TD>
                  <TD className="text-text-secondary">{imageModeLabel(profile)}</TD>
                  <TD className="text-text-secondary">{visibilityLabel(profile)}</TD>
                  <TD className="text-right">
                    <button
                      type="button"
                      className="rounded-control px-2 py-1 text-caption text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                      onClick={() => onOpenProfile(profile)}
                    >
                      Open in Settings
                    </button>
                  </TD>
                </TR>
              ))
            )}
          </TBody>
        </Table>
      </div>
    </Card>
  );
}
