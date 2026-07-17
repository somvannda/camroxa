"use client";

import Image from "next/image";
import { Lock, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function StepLogo(props: {
  channelName: string;
  logoBase64: string | null;
  setChannelName: (name: string) => void;
  setLogoBase64: (base64: string | null) => void;
  isBusy: boolean;
  onGenerateLogo: () => void;
}) {
  const hasName = props.channelName.trim().length > 0;

  return (
    <div className="grid gap-4">
      <div className="grid gap-2">
        <Label>Channel name</Label>
        <Input value={props.channelName} onChange={(e) => props.setChannelName(e.target.value)} />
      </div>

      <div className="flex flex-wrap gap-3">
        <Button onClick={props.onGenerateLogo} disabled={!hasName || props.isBusy}>
          <Wand2 className="h-4 w-4" />
          Generate logo
        </Button>
        <Button variant="outline" onClick={() => props.setLogoBase64(null)} disabled={props.isBusy}>
          Clear
        </Button>
      </div>

      {props.logoBase64 ? (
        <div className="flex items-center gap-4 rounded-lg border border-border/60 bg-background/30 p-4">
          <div className="relative h-20 w-20 overflow-hidden rounded-full border border-border/60 bg-background">
            <Image
              alt="Logo preview"
              src={`data:image/png;base64,${props.logoBase64}`}
              fill
              sizes="80px"
              className="object-cover"
            />
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium">Logo ready</div>
            <div className="text-sm text-muted-foreground">
              This is stored per role in the same way as the old desktop draft.
            </div>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-lg border border-dashed border-border/60 bg-background/20 p-6 text-sm text-muted-foreground">
          <Lock className="h-4 w-4" />
          No logo yet. Generate one.
        </div>
      )}
    </div>
  );
}
