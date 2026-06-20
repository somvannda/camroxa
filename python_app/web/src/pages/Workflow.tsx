import React, { useEffect, useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Play,
  RefreshCw,
  CheckCircle2,
  Circle,
  XCircle,
  Loader2,
  Clock,
  Music,
  Image as ImageIcon,
  Film,
  Merge,
  Upload,
} from 'lucide-react';

interface WorkflowStep {
  name: string;
  icon: React.ReactNode;
  status: 'done' | 'running' | 'inactive' | 'failed';
  percent: number;
  duration: string;
  detail: string;
}

export function Workflow() {
  const { call } = usePythonBridge();
  const [steps] = useState<WorkflowStep[]>([
    { name: 'Music Generation', icon: <Music className="h-4 w-4" />, status: 'done', percent: 100, duration: '2m 30s', detail: 'Generated 3 songs' },
    { name: 'Background + Thumbnail', icon: <ImageIcon className="h-4 w-4" />, status: 'done', percent: 100, duration: '45s', detail: 'Created 3 backgrounds' },
    { name: 'Convert MP4', icon: <Film className="h-4 w-4" />, status: 'running', percent: 65, duration: '1m 12s', detail: 'Converting song 2/3' },
    { name: 'Merge', icon: <Merge className="h-4 w-4" />, status: 'inactive', percent: 0, duration: '-', detail: 'Waiting' },
    { name: 'YouTube Upload', icon: <Upload className="h-4 w-4" />, status: 'inactive', percent: 0, duration: '-', detail: 'Waiting' },
  ]);

  const getStatusIcon = (status: WorkflowStep['status']) => {
    switch (status) {
      case 'done': return <CheckCircle2 className="h-5 w-5 text-green-500" />;
      case 'running': return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'failed': return <XCircle className="h-5 w-5 text-red-500" />;
      default: return <Circle className="h-5 w-5 text-muted-foreground" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-foreground">Workflow</h2>
        <div className="flex items-center gap-3">
          <Select defaultValue="latest">
            <SelectTrigger className="w-[420px]">
              <SelectValue placeholder="Select a workflow run" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="latest">Latest Run - 2024-01-15 14:30</SelectItem>
            </SelectContent>
          </Select>
          <Input type="date" className="w-36" />
          <Input type="date" className="w-36" />
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Timeline */}
      <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-lg">Pipeline Timeline</CardTitle>
          <Button className="bg-green-600 hover:bg-green-700">
            <Play className="mr-2 h-4 w-4" />
            Generate
          </Button>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            {steps.map((step, index) => (
              <div
                key={step.name}
                className="flex items-center gap-4 rounded-lg p-3 hover:bg-muted/30"
              >
                <div className="flex items-center gap-3">
                  {getStatusIcon(step.status)}
                  <div className="flex items-center gap-2 text-foreground">
                    {step.icon}
                    <span className="text-sm font-medium">{step.name}</span>
                  </div>
                </div>
                <div className="flex-1">
                  <div className="h-2 w-full rounded-full bg-muted/50">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        step.status === 'done'
                          ? 'bg-green-500'
                          : step.status === 'running'
                          ? 'bg-blue-500'
                          : step.status === 'failed'
                          ? 'bg-red-500'
                          : 'bg-muted'
                      }`}
                      style={{ width: `${step.percent}%` }}
                    />
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span className="w-12 text-right">{step.percent}%</span>
                  <span className="w-16 text-right">{step.duration}</span>
                  <span className="w-40 text-right">{step.detail}</span>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Notes */}
      <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardContent className="p-4">
          <p className="text-sm text-muted-foreground">
            Workflow running... Converting MP4 for song 2/3. Estimated time remaining: 1m 30s
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
