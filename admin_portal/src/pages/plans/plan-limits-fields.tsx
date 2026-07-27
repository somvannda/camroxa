import type { Control, FieldValues, Path } from 'react-hook-form';

import { Input } from '@/components/ui/input';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';

type UnlimitedState = {
  song: boolean;
  setSong: (v: boolean) => void;
  image: boolean;
  setImage: (v: boolean) => void;
  draft: boolean;
  setDraft: (v: boolean) => void;
};

type PlanLimitsFieldsProps<T extends FieldValues> = {
  control: Control<T>;
  unlimited: UnlimitedState;
};

function SectionHeading({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="md:col-span-2 space-y-1 border-t border-slate-800 pt-4 first:border-t-0 first:pt-0">
      <h4 className="text-sm font-semibold text-slate-100">{title}</h4>
      <p className="text-xs text-slate-500">{hint}</p>
    </div>
  );
}

function UnlimitedToggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-1.5 text-sm text-slate-300 whitespace-nowrap">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-slate-600"
      />
      Unlimited
    </label>
  );
}

/** Period caps + daily limits for Admin plan create/edit dialogs. */
export function PlanLimitsFields<T extends FieldValues>({
  control,
  unlimited,
}: PlanLimitsFieldsProps<T>) {
  return (
    <>
      <SectionHeading
        title="Period caps (billing cycle)"
        hint="Total allowance for the full billing period (30 / 180 / 365 days). For 6-month and annual plans, multiply the monthly amounts."
      />

      <FormField
        control={control}
        name={'monthly_song_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Suno packages / period</FormLabel>
            <p className="text-xs text-slate-400">
              1 package = Primary + Secondary channel (2 tracks).
            </p>
            <div className="flex items-center gap-3">
              <FormControl>
                <Input
                  type="number"
                  disabled={unlimited.song}
                  value={unlimited.song ? '' : (field.value ?? 0)}
                  onChange={(e) => field.onChange(Number(e.target.value))}
                  placeholder={unlimited.song ? 'Unlimited' : ''}
                />
              </FormControl>
              <UnlimitedToggle
                checked={unlimited.song}
                onChange={(checked) => {
                  unlimited.setSong(checked);
                  field.onChange(checked ? null : 0);
                }}
              />
            </div>
            {!unlimited.song && field.value != null && (
              <p className="text-xs text-slate-500">≈ {Number(field.value) * 2} tracks / period</p>
            )}
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'monthly_image_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Images / period (account)</FormLabel>
            <p className="text-xs text-slate-400">Account BG + TH pool.</p>
            <div className="flex items-center gap-3">
              <FormControl>
                <Input
                  type="number"
                  disabled={unlimited.image}
                  value={unlimited.image ? '' : (field.value ?? 0)}
                  onChange={(e) => field.onChange(Number(e.target.value))}
                  placeholder={unlimited.image ? 'Unlimited' : ''}
                />
              </FormControl>
              <UnlimitedToggle
                checked={unlimited.image}
                onChange={(checked) => {
                  unlimited.setImage(checked);
                  field.onChange(checked ? null : 0);
                }}
              />
            </div>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'monthly_draft_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Drafts / period (account)</FormLabel>
            <p className="text-xs text-slate-400">Lyric, title, or album calls (shared pool).</p>
            <div className="flex items-center gap-3">
              <FormControl>
                <Input
                  type="number"
                  disabled={unlimited.draft}
                  value={unlimited.draft ? '' : (field.value ?? 0)}
                  onChange={(e) => field.onChange(Number(e.target.value))}
                  placeholder={unlimited.draft ? 'Unlimited' : ''}
                />
              </FormControl>
              <UnlimitedToggle
                checked={unlimited.draft}
                onChange={(checked) => {
                  unlimited.setDraft(checked);
                  field.onChange(checked ? null : 0);
                }}
              />
            </div>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'monthly_video_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Videos / period (account)</FormLabel>
            <p className="text-xs text-slate-400">Local track exports (3 credits overage).</p>
            <FormControl>
              <Input
                type="number"
                value={field.value ?? 0}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'monthly_merge_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Merges / period (account)</FormLabel>
            <p className="text-xs text-slate-400">Auto-merge concat (10 credits overage).</p>
            <FormControl>
              <Input
                type="number"
                value={field.value ?? 0}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <SectionHeading
        title="Daily limits"
        hint="Per-channel song/image/draft stay the same when buying +2 add-ons (more channels = more total). Account-wide video/merge scale with active add-on slots."
      />

      <FormField
        control={control}
        name={'daily_song_limit_per_channel' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Daily songs per channel</FormLabel>
            <FormControl>
              <Input
                type="number"
                {...field}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'daily_image_limit_per_channel' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Daily images per channel</FormLabel>
            <p className="text-xs text-slate-400">
              2 = 1 background + 1 thumbnail per channel. A 2-channel plan allows 4 images/day account-wide.
            </p>
            <FormControl>
              <Input
                type="number"
                {...field}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'daily_draft_limit_per_channel' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Daily drafts per channel</FormLabel>
            <FormControl>
              <Input
                type="number"
                {...field}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'daily_video_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Daily videos (account-wide)</FormLabel>
            <p className="text-xs text-slate-400">Scales with active +2 channel add-ons.</p>
            <FormControl>
              <Input
                type="number"
                {...field}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name={'daily_merge_limit' as Path<T>}
        render={({ field }) => (
          <FormItem>
            <FormLabel>Daily merges (account-wide)</FormLabel>
            <p className="text-xs text-slate-400">Scales with active +2 channel add-ons.</p>
            <FormControl>
              <Input
                type="number"
                {...field}
                onChange={(e) => field.onChange(Number(e.target.value))}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </>
  );
}
