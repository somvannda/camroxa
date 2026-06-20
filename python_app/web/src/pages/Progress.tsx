import React from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  RefreshCw,
  XCircle,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Loader2,
} from 'lucide-react';

export function Progress() {
  const { call } = usePythonBridge();

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-foreground">Progress</h2>
        <div className="flex items-center gap-3">
          <Input type="date" className="w-36" />
          <Input type="date" className="w-36" />
          <div className="flex items-center gap-2">
            <Checkbox id="active-only" />
            <label htmlFor="active-only" className="text-sm text-muted-foreground">Active only</label>
          </div>
          <Select defaultValue="25">
            <SelectTrigger className="w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button variant="destructive" size="sm">
            <XCircle className="mr-2 h-4 w-4" />
            Cancel All
          </Button>
        </div>
      </div>

      {/* Summary */}
      <p className="text-sm text-muted-foreground">12 active jobs, 3 completed today</p>

      {/* Progress table */}
      <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 bg-muted/30">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Batch</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Run Date</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Channel</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Music</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Image</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Converter</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Merge</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">YouTube</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Stage</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Notes</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Updated</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { batch: 'BATCH-001', date: '2024-01-15', channel: 'Pop', status: 'running', music: '3/3', image: '2/3', converter: '1/3', merge: '0/3', youtube: '0/3', stage: 'Convert', notes: 'Converting song 2', updated: '2m ago' },
                  { batch: 'BATCH-002', date: '2024-01-15', channel: 'EDM', status: 'completed', music: '5/5', image: '5/5', converter: '5/5', merge: '5/5', youtube: '5/5', stage: 'Done', notes: 'All uploaded', updated: '15m ago' },
                  { batch: 'BATCH-003', date: '2024-01-14', channel: 'Lo-Fi', status: 'failed', music: '2/3', image: '1/3', converter: '0/3', merge: '0/3', youtube: '0/3', stage: 'Image', notes: 'API error', updated: '1h ago' },
                ].map((row) => (
                  <tr key={row.batch} className="border-b border-border/30 hover:bg-muted/20">
                    <td className="px-4 py-3 font-medium text-foreground">{row.batch}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.date}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.channel}</td>
                    <td className="px-4 py-3">
                      <Badge variant={row.status === 'completed' ? 'success' : row.status === 'failed' ? 'destructive' : 'default'}>
                        {row.status === 'running' && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                        {row.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{row.music}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.image}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.converter}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.merge}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.youtube}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.stage}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.notes}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.updated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
