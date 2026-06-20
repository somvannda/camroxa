import React from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Image as ImageIcon,
  RefreshCw,
  Trash2,
  Download,
  Eye,
} from 'lucide-react';

export function ImagePage() {
  const { call } = usePythonBridge();

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-foreground">Image Generation</h2>
        <div className="flex items-center gap-3">
          <Input type="date" className="w-36" />
          <Input type="date" className="w-36" />
          <Select defaultValue="all">
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Profiles</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm">
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Image jobs table */}
      <Card className="bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardContent className="p-0">
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 bg-muted/30">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Prompt</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Created</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border/30">
                  <td className="px-4 py-3 text-muted-foreground">IMG-001</td>
                  <td className="px-4 py-3 text-foreground">Thumbnail</td>
                  <td className="px-4 py-3"><Badge variant="success">Ready</Badge></td>
                  <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">Neon cityscape with purple gradient...</td>
                  <td className="px-4 py-3 text-muted-foreground">2 min ago</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
                <tr className="border-b border-border/30">
                  <td className="px-4 py-3 text-muted-foreground">IMG-002</td>
                  <td className="px-4 py-3 text-foreground">Background</td>
                  <td className="px-4 py-3"><Badge variant="warning">Processing</Badge></td>
                  <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">Abstract music visualization...</td>
                  <td className="px-4 py-3 text-muted-foreground">5 min ago</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Eye className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
