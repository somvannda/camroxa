import * as React from "react";
import { Dialog, DialogContent } from "@/components/ui/Dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { CarModelsTab } from "@/components/dashboard/manage/CarModelsTab";
import { ImageSamplesTab } from "@/components/dashboard/manage/ImageSamplesTab";
import { PromptTemplatesTab } from "@/components/dashboard/manage/PromptTemplatesTab";
import { SavedTextsTab } from "@/components/dashboard/manage/SavedTextsTab";
import { TextStylesTab } from "@/components/dashboard/manage/TextStylesTab";
import { PhrasePoolsTab } from "@/components/dashboard/manage/PhrasePoolsTab";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initialTab?: string;
  onLoadDescription?: (text: string) => void;
  onLoadStructure?: (text: string) => void;
};

export function ManagePanel({ initialTab, onLoadDescription, onLoadStructure }: Omit<Props, "open" | "onOpenChange">) {
  const [tab, setTab] = React.useState("imageSamples");

  React.useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);

  return (
    <div className="min-h-0 flex-1 p-4 flex flex-col">
      <Tabs value={tab} onValueChange={setTab}>
        <div className="flex items-center justify-center">
          <TabsList>
            <TabsTrigger value="imageSamples">Image Samples</TabsTrigger>
            <TabsTrigger value="carModels">Car Models</TabsTrigger>
            <TabsTrigger value="descriptions">Descriptions</TabsTrigger>
            <TabsTrigger value="structures">Structures</TabsTrigger>
            <TabsTrigger value="promptTemplates">Prompt Templates</TabsTrigger>
            <TabsTrigger value="textStyles">Text Styles</TabsTrigger>
            <TabsTrigger value="phrasePools">Pools</TabsTrigger>
          </TabsList>
        </div>

        <div className="mt-4 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
          <TabsContent value="imageSamples" className="mt-0 min-h-0 flex-1 overflow-hidden">
            <ImageSamplesTab />
          </TabsContent>
          <TabsContent value="carModels" className="mt-0 min-h-0 flex-1 overflow-auto">
            <CarModelsTab />
          </TabsContent>
          <TabsContent value="descriptions" className="mt-0 min-h-0 flex-1 overflow-auto">
            <SavedTextsTab kind="descriptions" title="Manage descriptions" onLoad={onLoadDescription} />
          </TabsContent>
          <TabsContent value="structures" className="mt-0 min-h-0 flex-1 overflow-auto">
            <SavedTextsTab kind="structures" title="Manage structures" onLoad={onLoadStructure} />
          </TabsContent>
          <TabsContent value="promptTemplates" className="mt-0 min-h-0 flex-1 overflow-auto">
            <PromptTemplatesTab />
          </TabsContent>
          <TabsContent value="textStyles" className="mt-0 min-h-0 flex-1 overflow-auto">
            <TextStylesTab />
          </TabsContent>
          <TabsContent value="phrasePools" className="mt-0 min-h-0 flex-1 overflow-hidden">
            <PhrasePoolsTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

export function LibraryPanel({ initialTab, onLoadDescription, onLoadStructure }: Omit<Props, "open" | "onOpenChange">) {
  const [tab, setTab] = React.useState("imageSamples");

  React.useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);

  return (
    <div className="min-h-0 flex-1 p-4 flex flex-col">
      <Tabs value={tab} onValueChange={setTab}>
        <div className="flex items-center justify-center">
          <TabsList>
            <TabsTrigger value="imageSamples">Reference Images</TabsTrigger>
            <TabsTrigger value="carModels">Car Catalog</TabsTrigger>
            <TabsTrigger value="descriptions">Descriptions</TabsTrigger>
            <TabsTrigger value="structures">Structures</TabsTrigger>
            <TabsTrigger value="promptTemplates">Prompt Templates</TabsTrigger>
            <TabsTrigger value="textStyles">Text Styles</TabsTrigger>
          </TabsList>
        </div>

        <div className="mt-4 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
          <TabsContent value="imageSamples" className="mt-0 min-h-0 flex-1 overflow-hidden">
            <ImageSamplesTab />
          </TabsContent>
          <TabsContent value="carModels" className="mt-0 min-h-0 flex-1 overflow-auto">
            <CarModelsTab />
          </TabsContent>
          <TabsContent value="descriptions" className="mt-0 min-h-0 flex-1 overflow-auto">
            <SavedTextsTab kind="descriptions" title="Manage descriptions" onLoad={onLoadDescription} />
          </TabsContent>
          <TabsContent value="structures" className="mt-0 min-h-0 flex-1 overflow-auto">
            <SavedTextsTab kind="structures" title="Manage structures" onLoad={onLoadStructure} />
          </TabsContent>
          <TabsContent value="promptTemplates" className="mt-0 min-h-0 flex-1 overflow-auto">
            <PromptTemplatesTab />
          </TabsContent>
          <TabsContent value="textStyles" className="mt-0 min-h-0 flex-1 overflow-auto">
            <TextStylesTab />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

export function AdminPanel() {
  return (
    <div className="min-h-0 flex-1 p-4 flex flex-col">
      <div className="flex items-center justify-center text-sm font-semibold text-slate-100">Admin</div>
      <div className="mt-4 flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200/10 bg-slate-950/20 p-3">
        <PhrasePoolsTab />
      </div>
    </div>
  );
}

export function ManageDialog({ open, onOpenChange, initialTab, onLoadDescription, onLoadStructure }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Manage" className="max-w-6xl h-[760px] flex flex-col">
        <ManagePanel initialTab={initialTab} onLoadDescription={onLoadDescription} onLoadStructure={onLoadStructure} />
      </DialogContent>
    </Dialog>
  );
}

