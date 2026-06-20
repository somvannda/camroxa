import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

/**
 * Centered error display with an error icon, message, and optional retry button.
 * Used as a page-level error state when API requests fail.
 */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex min-h-[400px] items-center justify-center p-6">
      <Card className="w-full max-w-md border-slate-800 bg-slate-900/50">
        <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
          <div className="rounded-full bg-destructive/10 p-3">
            <AlertCircle className="h-8 w-8 text-destructive" />
          </div>
          <div className="space-y-2">
            <h3 className="text-lg font-semibold text-slate-100">
              Something went wrong
            </h3>
            <p className="text-sm text-slate-400">{message}</p>
          </div>
          {onRetry && (
            <Button onClick={onRetry} variant="outline" className="mt-2">
              Retry
            </Button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
