import React, { useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Checkbox } from '../components/ui/checkbox';
import { Switch } from '../components/ui/switch';
import { Slider } from '../components/ui/slider';
import { Textarea } from '../components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Key,
  Bot,
  Youtube,
  Gauge,
  User,
  FolderOpen,
  Image as ImageIcon,
  Database,
  Shield,
  Save,
  RefreshCw,
} from 'lucide-react';

export function Settings() {
  const { call } = usePythonBridge();

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Settings</h2>

      <Tabs defaultValue="api-keys" className="w-full">
        <TabsList className="grid w-full grid-cols-9">
          <TabsTrigger value="api-keys" className="text-xs">
            <Key className="mr-1 h-3 w-3" />
            API Keys
          </TabsTrigger>
          <TabsTrigger value="ai-providers" className="text-xs">
            <Bot className="mr-1 h-3 w-3" />
            AI Providers
          </TabsTrigger>
          <TabsTrigger value="youtube" className="text-xs">
            <Youtube className="mr-1 h-3 w-3" />
            YouTube
          </TabsTrigger>
          <TabsTrigger value="performance" className="text-xs">
            <Gauge className="mr-1 h-3 w-3" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="profiles" className="text-xs">
            <User className="mr-1 h-3 w-3" />
            Profiles
          </TabsTrigger>
          <TabsTrigger value="paths" className="text-xs">
            <FolderOpen className="mr-1 h-3 w-3" />
            Paths
          </TabsTrigger>
          <TabsTrigger value="image" className="text-xs">
            <ImageIcon className="mr-1 h-3 w-3" />
            Image
          </TabsTrigger>
          <TabsTrigger value="database" className="text-xs">
            <Database className="mr-1 h-3 w-3" />
            Database
          </TabsTrigger>
          <TabsTrigger value="suno" className="text-xs">
            <Shield className="mr-1 h-3 w-3" />
            Suno
          </TabsTrigger>
        </TabsList>

        <TabsContent value="api-keys">
          <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
            <CardHeader>
              <CardTitle className="text-lg">API Keys</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">SLAI Song Model</label>
                <Input className="mt-1" placeholder="Enter SLAI Song model key" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Suno API Base URL</label>
                <Input className="mt-1" placeholder="https://api.suno.ai" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">OpenAI API Key</label>
                <Input className="mt-1" type="password" placeholder="sk-..." />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">SLAI IMG Model</label>
                <Input className="mt-1" placeholder="Enter SLAI Image model key" />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">FAL IMG Model</label>
                <Select defaultValue="fal-1">
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fal-1">FAL Image v1</SelectItem>
                    <SelectItem value="fal-2">FAL Image v2</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button>
                <Save className="mr-2 h-4 w-4" />
                Save API Keys
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="performance">
          <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
            <CardHeader>
              <CardTitle className="text-lg">Performance</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-muted-foreground">Music Workers</label>
                  <Input type="number" className="mt-1" defaultValue={1} min={1} max={5} />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">Image Workers</label>
                  <Input type="number" className="mt-1" defaultValue={2} min={1} max={8} />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">Export Workers</label>
                  <Input type="number" className="mt-1" defaultValue={4} min={1} max={10} />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">Merge Workers</label>
                  <Input type="number" className="mt-1" defaultValue={1} min={1} max={2} />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">YouTube Workers</label>
                  <Input type="number" className="mt-1" defaultValue={2} min={1} max={5} />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">Upload Chunk Size (MB)</label>
                  <Input type="number" className="mt-1" defaultValue={10} min={1} max={100} />
                </div>
              </div>
              <Button>
                <Save className="mr-2 h-4 w-4" />
                Save Performance Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="profiles">
          <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
            <CardHeader>
              <CardTitle className="text-lg">Profiles</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="rounded-lg border border-border/50 p-3">
                  <h4 className="font-medium text-foreground">Pop Channel</h4>
                  <p className="text-sm text-muted-foreground">/output/pop</p>
                </div>
                <div className="rounded-lg border border-border/50 p-3">
                  <h4 className="font-medium text-foreground">EDM Channel</h4>
                  <p className="text-sm text-muted-foreground">/output/edm</p>
                </div>
                <div className="rounded-lg border border-border/50 p-3">
                  <h4 className="font-medium text-foreground">Lo-Fi Channel</h4>
                  <p className="text-sm text-muted-foreground">/output/lofi</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
