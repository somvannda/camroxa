import React, { useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Slider } from '../components/ui/slider';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Play,
  Pause,
  Shuffle,
  Copy,
  Wand2,
  History,
  Music2,
  Disc3,
} from 'lucide-react';

export function Music() {
  const { call } = usePythonBridge();
  const [description, setDescription] = useState('');
  const [structure, setStructure] = useState('');
  const [generating, setGenerating] = useState(false);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await call('generate_music', JSON.stringify({ description, structure }));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Session bar */}
      <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardContent className="flex items-center gap-4 p-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">From:</label>
            <Input type="date" className="w-36" />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">To:</label>
            <Input type="date" className="w-36" />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">Language:</label>
            <Select defaultValue="en">
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="km">Khmer</SelectItem>
                <SelectItem value="de">German</SelectItem>
                <SelectItem value="es">Spanish</SelectItem>
                <SelectItem value="fr">French</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">Creativity:</label>
            <Slider className="w-24" defaultValue={[50]} max={100} step={1} />
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="unique" />
            <label htmlFor="unique" className="text-sm text-muted-foreground">Unique opening</label>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">Strict:</label>
            <Select defaultValue="3">
              <SelectTrigger className="w-16">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[1, 2, 3, 4, 5].map((n) => (
                  <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">Count:</label>
            <Input type="number" className="w-16" defaultValue={1} min={1} max={50} />
          </div>
        </CardContent>
      </Card>

      {/* Top row: Description + Structure */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm">Song Description</CardTitle>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" className="h-7 text-xs">
                <Shuffle className="mr-1 h-3 w-3" />
                Shuffle
              </Button>
              <Button variant="ghost" size="sm" className="h-7 text-xs">
                Match
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Describe your song..."
              className="h-32 resize-none"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </CardContent>
        </Card>

        <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm">Song Structure</CardTitle>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" className="h-7 text-xs">
                <Shuffle className="mr-1 h-3 w-3" />
                Shuffle
              </Button>
              <Button variant="ghost" size="sm" className="h-7 text-xs">
                Cycle
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Textarea
              placeholder="Define song structure..."
              className="h-32 resize-none"
              value={structure}
              onChange={(e) => setStructure(e.target.value)}
            />
          </CardContent>
        </Card>
      </div>

      {/* Automation bar */}
      <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardContent className="flex items-center gap-6 p-4">
          <div className="flex items-center gap-2">
            <Checkbox id="auto-image" />
            <label htmlFor="auto-image" className="text-sm text-muted-foreground">Auto-Gen Image</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="auto-suno" />
            <label htmlFor="auto-suno" className="text-sm text-muted-foreground">Auto-GSuno</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="auto-video" />
            <label htmlFor="auto-video" className="text-sm text-muted-foreground">Auto-Video</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="auto-merge" />
            <label htmlFor="auto-merge" className="text-sm text-muted-foreground">Auto Merge</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="auto-reel" />
            <label htmlFor="auto-reel" className="text-sm text-muted-foreground">Auto Reel</label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="auto-upload" />
            <label htmlFor="auto-upload" className="text-sm text-muted-foreground">Auto Upload</label>
          </div>
          <div className="flex-1" />
          <Badge variant="outline" className="text-muted-foreground">
            Credits: 1,250
          </Badge>
          <Button
            onClick={handleGenerate}
            disabled={generating}
            className="bg-gradient-to-r from-[#7c3aed] to-[#a855f7] hover:opacity-90"
          >
            {generating ? (
              <>
                <Disc3 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Wand2 className="mr-2 h-4 w-4" />
                Generate
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Bottom row: Song detail + History */}
      <div className="grid grid-cols-3 gap-4">
        {/* Current song */}
        <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Current Song</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground">Title</label>
              <Input className="h-8 text-sm" placeholder="Song title" />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Album</label>
              <Input className="h-8 text-sm" placeholder="Album name" />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="h-7 text-xs">
                <Copy className="mr-1 h-3 w-3" />
                Copy title
              </Button>
              <Button variant="outline" size="sm" className="h-7 text-xs">
                <Copy className="mr-1 h-3 w-3" />
                Copy lyrics
              </Button>
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Lyrics</label>
              <Textarea className="h-24 resize-none font-mono text-xs" placeholder="Song lyrics..." />
            </div>
          </CardContent>
        </Card>

        {/* History */}
        <Card className="col-span-2 bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm">Generation History</CardTitle>
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              <History className="mr-1 h-3 w-3" />
              Show all
            </Button>
          </CardHeader>
          <CardContent>
            <div className="overflow-auto rounded-lg border border-border/50">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50 bg-muted/30">
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">No</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Title</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Channel</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Suno</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Generated</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-border/30">
                    <td className="px-3 py-2 text-muted-foreground">1</td>
                    <td className="px-3 py-2 text-foreground">Midnight Dreams</td>
                    <td className="px-3 py-2 text-muted-foreground">Pop Channel</td>
                    <td className="px-3 py-2"><Badge variant="success">Complete</Badge></td>
                    <td className="px-3 py-2 text-muted-foreground">2 min ago</td>
                  </tr>
                  <tr className="border-b border-border/30">
                    <td className="px-3 py-2 text-muted-foreground">2</td>
                    <td className="px-3 py-2 text-foreground">Electric Pulse</td>
                    <td className="px-3 py-2 text-muted-foreground">EDM Channel</td>
                    <td className="px-3 py-2"><Badge variant="warning">Pending</Badge></td>
                    <td className="px-3 py-2 text-muted-foreground">15 min ago</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
