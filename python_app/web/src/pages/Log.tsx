import React, { useEffect, useRef, useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ScrollArea } from '../components/ui/scroll-area';
import { Trash2, ArrowDown } from 'lucide-react';

export function Log() {
  const { call, emit } = usePythonBridge();
  const [logLines, setLogLines] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadLog();
    const unsub = emit('log_update', (data: { lines: string[] }) => {
      setLogLines((prev) => [...prev, ...data.lines]);
    });
    return unsub;
  }, []);

  const loadLog = async () => {
    const result = await call('get_log');
    if (result && typeof result === 'string') {
      setLogLines(result.split('\n').filter(Boolean));
    }
  };

  const clearLog = async () => {
    await call('clear_log');
    setLogLines([]);
  };

  const scrollToBottom = () => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  };

  return (
    <div className="flex h-full flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-foreground">Application Log</h2>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={clearLog}>
            <Trash2 className="mr-2 h-4 w-4" />
            Clear
          </Button>
          <Button variant="outline" size="sm" onClick={scrollToBottom}>
            <ArrowDown className="mr-2 h-4 w-4" />
            Scroll to Bottom
          </Button>
        </div>
      </div>

      {/* Log area */}
      <Card className="flex-1 bg-gradient-to-br from-[#1e2548] to-[#0f1538] border-border/50">
        <CardContent className="p-0 h-full">
          <ScrollArea className="h-full" ref={scrollRef}>
            <div className="p-4 font-mono text-xs text-muted-foreground">
              {logLines.length === 0 ? (
                <span className="text-muted-foreground/50">No log entries yet...</span>
              ) : (
                logLines.map((line, i) => (
                  <div key={i} className="py-0.5 hover:bg-muted/20">
                    {line}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Status */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Logging active</span>
        <span>{logLines.length} lines</span>
      </div>
    </div>
  );
}
