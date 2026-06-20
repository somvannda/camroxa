import React from 'react';
import { usePythonBridge } from '../../bridge/usePythonBridge';
import { Titlebar } from './Titlebar';
import { Sidebar } from './Sidebar';
import { Footer } from './Footer';
import type { PageKey } from '../../types';

interface ShellProps {
  currentPage: PageKey;
  onNavigate: (page: PageKey) => void;
  children: React.ReactNode;
}

export function Shell({ currentPage, onNavigate, children }: ShellProps) {
  const { bridge, isReady } = usePythonBridge();

  const handleNavigate = (page: PageKey) => {
    onNavigate(page);
    if (bridge) {
      bridge.navigate(page);
    }
  };

  // Hybrid mode: PyQt6 provides titlebar, React shows sidebar + content
  const isHybrid = !!(window.qt?.webChannel);

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-[#080c24]">
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - full height */}
        <Sidebar currentPage={currentPage} onNavigate={handleNavigate} />

        {/* Main area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Titlebar — only in dev mode (hybrid mode uses PyQt6 titlebar) */}
          {!isHybrid && <Titlebar />}

          {/* Content */}
          <main className="flex-1 overflow-auto">
            {isReady ? children : (
              <div className="flex h-full items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#a855f7] border-t-transparent" />
                  <div className="text-[13px] text-gray-400">Loading...</div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
      <Footer />
    </div>
  );
}
