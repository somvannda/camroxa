import React from 'react';
import { usePythonBridge } from '../../bridge/usePythonBridge';
import { Minus, Square, X, Bell } from 'lucide-react';

export function Titlebar() {
  const { bridge } = usePythonBridge();

  return (
    <div className="drag-region flex h-11 shrink-0 items-center border-b border-white/5 bg-[#080c24] px-4">
      <div className="flex-1" />

      {/* Right: Notification + Window controls */}
      <div className="no-drag flex items-center gap-2">
        {/* Notification bell */}
        <button className="relative flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 transition-colors">
          <Bell className="h-4 w-4 text-gray-400" />
          <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-red-500 border-2 border-[#080c24]" />
        </button>

        <div className="mx-1 h-6 w-px bg-white/10" />

        {/* Window controls */}
        <button
          onClick={() => bridge?.minimize_window()}
          className="flex h-8 w-10 items-center justify-center rounded-lg hover:bg-white/10 transition-colors"
        >
          <Minus className="h-4 w-4 text-gray-400" />
        </button>
        <button
          onClick={() => bridge?.maximize_window()}
          className="flex h-8 w-10 items-center justify-center rounded-lg hover:bg-white/10 transition-colors"
        >
          <Square className="h-3 w-3 text-gray-400" />
        </button>
        <button
          onClick={() => bridge?.close_window()}
          className="flex h-8 w-10 items-center justify-center rounded-lg hover:bg-red-500/80 transition-colors"
        >
          <X className="h-4 w-4 text-gray-400 hover:text-white" />
        </button>
      </div>
    </div>
  );
}
