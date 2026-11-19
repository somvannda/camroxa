import { Component, type ErrorInfo, type ReactNode } from "react";
import { RotateCcw } from "lucide-react";
import { Button } from "./button";
import { Card } from "./card";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Renderer error boundary", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="flex h-full items-center justify-center bg-bg p-8" role="alert">
        <Card className="w-full max-w-xl p-6">
          <h1 className="text-title font-semibold text-text-primary">Camxora needs to reload</h1>
          <p className="mt-2 text-body text-text-secondary">
            The interface stopped unexpectedly. Your project files on disk are safe. Reload the
            window to continue.
          </p>
          <pre className="mt-4 max-h-40 overflow-auto rounded-control border border-border bg-surface-2 p-3 font-mono text-caption text-text-muted">
            {this.state.error.message}
          </pre>
          <div className="mt-5 flex items-center gap-2">
            <Button variant="primary" onClick={() => window.location.reload()}>
              <RotateCcw size={14} />
              Reload window
            </Button>
          </div>
        </Card>
      </div>
    );
  }
}
