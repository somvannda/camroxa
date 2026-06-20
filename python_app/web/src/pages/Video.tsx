import React, { useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Slider } from '../components/ui/slider';
import { Switch } from '../components/ui/switch';
import { Checkbox } from '../components/ui/checkbox';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Play,
  Square,
  SkipBack,
  SkipForward,
  Upload,
  FolderOpen,
  Download,
  Merge,
  Layers,
  Sparkles,
  Type,
  Image as ImageIcon,
  Settings2,
} from 'lucide-react';

export function Video() {
  const { call } = usePythonBridge();
  const [playing, setPlaying] = useState(false);

  return (
    <div className="flex h-full gap-4">
      {/* Left panel: Settings */}
      <div className="w-80 shrink-0 overflow-auto">
        <Tabs defaultValue="spectrum" className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="spectrum" className="text-xs">
              <Sparkles className="h-4 w-4" />
            </TabsTrigger>
            <TabsTrigger value="background" className="text-xs">
              <ImageIcon className="h-4 w-4" />
            </TabsTrigger>
            <TabsTrigger value="logo" className="text-xs">
              <Layers className="h-4 w-4" />
            </TabsTrigger>
            <TabsTrigger value="particles" className="text-xs">
              <Settings2 className="h-4 w-4" />
            </TabsTrigger>
            <TabsTrigger value="text" className="text-xs">
              <Type className="h-4 w-4" />
            </TabsTrigger>
          </TabsList>

          <TabsContent value="spectrum" className="space-y-4 p-1">
            <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Spectrum</span>
                  <Switch />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Style Preset</label>
                  <Select defaultValue="classic">
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="classic">Classic Vertical</SelectItem>
                      <SelectItem value="thin">Thin Lines</SelectItem>
                      <SelectItem value="dot">Dot Matrix</SelectItem>
                      <SelectItem value="wave">Wave</SelectItem>
                      <SelectItem value="circle">Circle</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Sensitivity</label>
                  <Slider className="mt-1" defaultValue={[50]} max={100} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Smoothing</label>
                  <Slider className="mt-1" defaultValue={[30]} max={100} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Anchor</label>
                  <Select defaultValue="bottom">
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bottom">Bottom</SelectItem>
                      <SelectItem value="top">Top</SelectItem>
                      <SelectItem value="center">Center</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="background" className="space-y-4 p-1">
            <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Background</span>
                  <Switch />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Fit Mode</label>
                  <Select defaultValue="cover">
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cover">Cover</SelectItem>
                      <SelectItem value="contain">Contain</SelectItem>
                      <SelectItem value="stretch">Stretch</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Brightness</label>
                  <Slider className="mt-1" defaultValue={[50]} max={100} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Reactivity</label>
                  <Slider className="mt-1" defaultValue={[30]} max={100} />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="logo" className="p-1">
            <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Logo</span>
                  <Switch />
                </div>
                <Button variant="outline" size="sm" className="w-full">
                  <FolderOpen className="mr-2 h-4 w-4" />
                  Select Logo
                </Button>
                <div>
                  <label className="text-xs text-muted-foreground">Size</label>
                  <Slider className="mt-1" defaultValue={[50]} max={100} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Opacity</label>
                  <Slider className="mt-1" defaultValue={[80]} max={100} />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="particles" className="p-1">
            <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Particles</span>
                  <Switch />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Max Count</label>
                  <Slider className="mt-1" defaultValue={[100]} max={500} />
                </div>
                <div>
                  <label className="text-xs text-muted-foreground">Size</label>
                  <Slider className="mt-1" defaultValue={[50]} max={100} />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="text" className="p-1">
            <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
              <CardContent className="space-y-4 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground">Text Overlay</span>
                  <Switch />
                </div>
                <Textarea placeholder="Enter text..." className="h-20 resize-none" />
                <div>
                  <label className="text-xs text-muted-foreground">Font Size</label>
                  <Slider className="mt-1" defaultValue={[24]} max={72} />
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* Center panel: Preview + Controls */}
      <div className="flex flex-1 flex-col gap-4">
        {/* Preview area */}
        <Card className="flex-1 bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardContent className="flex h-full items-center justify-center p-4">
            <div id="opengl-preview" className="relative h-full w-full rounded-lg bg-muted/30 flex items-center justify-center">
              <span className="text-muted-foreground">Video Preview (OpenGL)</span>
            </div>
          </CardContent>
        </Card>

        {/* Playback controls */}
        <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardContent className="flex items-center gap-4 p-3">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <SkipBack className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-10 w-10"
              onClick={() => setPlaying(!playing)}
            >
              {playing ? <Square className="h-5 w-5" /> : <Play className="h-5 w-5" />}
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <SkipForward className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground">0:00 / 3:45</span>
            <Slider className="flex-1" defaultValue={[0]} max={1000} />
          </CardContent>
        </Card>

        {/* Export controls */}
        <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardContent className="flex items-center gap-4 p-4">
            <Button variant="outline" size="sm">
              <FolderOpen className="mr-2 h-4 w-4" />
              Select MP3 Folder
            </Button>
            <Button variant="outline" size="sm">
              <ImageIcon className="mr-2 h-4 w-4" />
              Generate Thumbnail
            </Button>
            <div className="flex-1" />
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted-foreground">Workers:</label>
              <Input type="number" className="w-16 h-8" defaultValue={1} min={1} max={10} />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox id="auto-merge" />
              <label htmlFor="auto-merge" className="text-sm text-muted-foreground">Auto merge</label>
            </div>
            <Button className="bg-gradient-to-r from-[#7c3aed] to-[#a855f7]">
              <Upload className="mr-2 h-4 w-4" />
              Export
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Right panel: Layer Inspector */}
      <div className="w-80 shrink-0 overflow-auto">
        <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Layer Inspector</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-2">
              <Select defaultValue="0">
                <SelectTrigger className="flex-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Layer 1 - Spectrum</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline" size="icon" className="h-8 w-8">
                <Layers className="h-4 w-4" />
              </Button>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Layer Name</label>
              <Input className="mt-1 h-8 text-sm" defaultValue="Spectrum" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Gravity</label>
              <Select defaultValue="bottom">
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bottom">Bottom</SelectItem>
                  <SelectItem value="top">Top</SelectItem>
                  <SelectItem value="left">Left</SelectItem>
                  <SelectItem value="right">Right</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">Bar Width</label>
                <span className="text-xs text-foreground">20</span>
              </div>
              <Slider defaultValue={[20]} max={50} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">Opacity</label>
                <span className="text-xs text-foreground">100%</span>
              </div>
              <Slider defaultValue={[100]} max={100} />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs text-muted-foreground">Glow</label>
                <span className="text-xs text-foreground">50%</span>
              </div>
              <Slider defaultValue={[50]} max={100} />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Blend Mode</label>
              <Select defaultValue="normal">
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="normal">Normal</SelectItem>
                  <SelectItem value="additive">Additive</SelectItem>
                  <SelectItem value="screen">Screen</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Color Mode</label>
              <Select defaultValue="solid">
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="solid">Solid</SelectItem>
                  <SelectItem value="gradient">Gradient</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
