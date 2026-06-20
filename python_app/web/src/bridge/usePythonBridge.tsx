import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';

declare global {
  interface Window {
    qt: {
      webChannel: {
        connect: (callback: (objects: Record<string, any>) => void) => void;
      };
    };
  }
}

interface PythonBridgeContextType {
  bridge: any;
  isReady: boolean;
  call: (method: string, ...args: any[]) => Promise<any>;
  emit: (signal: string, callback: (data: any) => void) => void;
}

const PythonBridgeContext = createContext<PythonBridgeContextType>({
  bridge: null,
  isReady: false,
  call: async () => null,
  emit: () => {},
});

export function PythonBridgeProvider({ children }: { children: React.ReactNode }) {
  const [bridge, setBridge] = useState<any>(null);
  const [isReady, setIsReady] = useState(false);
  const callbacksRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>;
    let attempts = 0;
    const MAX_ATTEMPTS = 50; // 5 seconds max wait
    const POLL_INTERVAL = 100; // ms

    function connectToBridge() {
      if (window.qt?.webChannel) {
        // Running inside QWebEngineView
        console.log('[Web] QWebChannel detected, connecting...');
        window.qt.webChannel.connect((objects) => {
          const pythonBridge = objects.python;
          if (pythonBridge) {
            setBridge(pythonBridge);
            setIsReady(true);

            // Connect to Python signals
            pythonBridge.progress_updated.connect((data: string) => {
              callbacksRef.current.get('progress_updated')?.forEach(cb => cb(JSON.parse(data)));
            });
            pythonBridge.music_event.connect((data: string) => {
              callbacksRef.current.get('music_event')?.forEach(cb => cb(JSON.parse(data)));
            });
            pythonBridge.export_event.connect((data: string) => {
              callbacksRef.current.get('export_event')?.forEach(cb => cb(JSON.parse(data)));
            });
            pythonBridge.notification.connect((title: string, message: string) => {
              callbacksRef.current.get('notification')?.forEach(cb => cb({ title, message }));
            });
            pythonBridge.page_changed.connect((page: string) => {
              callbacksRef.current.get('page_changed')?.forEach(cb => cb(page));
            });
          }
        });
        return;
      }

      attempts++;
      if (attempts < MAX_ATTEMPTS) {
        timeout = setTimeout(connectToBridge, POLL_INTERVAL);
      } else {
        // Fallback to mock bridge after timeout
        console.log('[Web] QWebChannel not found after waiting, using mock bridge');
        setBridge({
          get_dashboard_data: () => JSON.stringify({
            activeBatches: 12, failedItems: 3, songs: 45, images: 128,
            mp4: 8, merged: 5, youtube: 3, credits: 1250
          }),
          get_music_data: () => JSON.stringify({ songs: [], profiles: [] }),
          get_video_templates: () => JSON.stringify([]),
          navigate: (page: string) => console.log('Navigate to:', page),
          minimize_window: () => console.log('Minimize'),
          maximize_window: () => console.log('Maximize'),
          close_window: () => console.log('Close'),
          login: (email: string, password: string) => {
            console.log('Login:', email, password);
            return JSON.stringify({ status: 'ok', token: 'mock-token' });
          },
          register: (email: string, password: string, displayName: string) => {
            console.log('Register:', email, password, displayName);
            return JSON.stringify({ status: 'ok' });
          },
          generate_music: (params: string) => console.log('Generate music:', params),
          cancel_generation: () => console.log('Cancel'),
          get_progress_data: () => JSON.stringify([]),
          get_log: () => '',
          clear_log: () => {},
          get_settings: () => JSON.stringify({}),
          save_settings: (settings: string) => console.log('Save settings:', settings),
        });
        setIsReady(true);
      }
    }

    connectToBridge();

    return () => {
      if (timeout) clearTimeout(timeout);
    };
  }, []);

  const call = useCallback(async (method: string, ...args: any[]) => {
    if (!bridge) return null;
    try {
      const result = await bridge[method](...args);
      try {
        return typeof result === 'string' ? JSON.parse(result) : result;
      } catch {
        return result;
      }
    } catch (err) {
      console.error(`[Bridge] Error calling ${method}:`, err);
      return null;
    }
  }, [bridge]);

  const emit = useCallback((signal: string, callback: (data: any) => void) => {
    if (!callbacksRef.current.has(signal)) {
      callbacksRef.current.set(signal, new Set());
    }
    callbacksRef.current.get(signal)!.add(callback);

    // Return unsubscribe function
    return () => {
      callbacksRef.current.get(signal)?.delete(callback);
    };
  }, []);

  return (
    <PythonBridgeContext.Provider value={{ bridge, isReady, call, emit }}>
      {children}
    </PythonBridgeContext.Provider>
  );
}

export function usePythonBridge() {
  return useContext(PythonBridgeContext);
}
