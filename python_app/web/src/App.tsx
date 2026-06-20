import React, { useState, useEffect } from 'react';
import { PythonBridgeProvider, usePythonBridge } from './bridge/usePythonBridge';
import { Shell } from './components/layout/Shell';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Music } from './pages/Music';
import { Video } from './pages/Video';
import { Workflow } from './pages/Workflow';
import { ImagePage } from './pages/Image';
import { Progress } from './pages/Progress';
import { Settings } from './pages/Settings';
import { Log } from './pages/Log';

export type Page = 'login' | 'home' | 'music' | 'video' | 'workflow' | 'image' | 'progress' | 'settings' | 'log' | 'merger';

function PageRouter() {
  const { bridge, isReady } = usePythonBridge();
  const [currentPage, setCurrentPage] = useState<Page>('home');

  // In hybrid mode: listen for page_changed signal from Python sidebar
  useEffect(() => {
    if (!isReady || !bridge?.page_changed) return;

    // page_changed is a Qt signal — listen for it
    const handler = (page: string) => {
      console.log('[React] Page changed from Python:', page);
      setCurrentPage(page as Page);
    };

    bridge.page_changed.connect(handler);
    return () => {
      bridge.page_changed.disconnect(handler);
    };
  }, [bridge, isReady]);

  // Hybrid mode: QWebEngineView provides the container, React shows full shell
  // Dev mode: show Shell for standalone development
  // Both render the same way — Shell with sidebar + content
  return (
    <Shell currentPage={currentPage} onNavigate={setCurrentPage}>
      {currentPage === 'home' && <Dashboard />}
      {currentPage === 'music' && <Music />}
      {currentPage === 'video' && <Video />}
      {currentPage === 'workflow' && <Workflow />}
      {currentPage === 'image' && <ImagePage />}
      {currentPage === 'progress' && <Progress />}
      {currentPage === 'settings' && <Settings />}
      {currentPage === 'log' && <Log />}
      {currentPage === 'merger' && (
        <div className="flex h-full items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-white mb-2">Merger</h2>
            <p className="text-gray-400">Merger page is reserved for future development.</p>
          </div>
        </div>
      )}
    </Shell>
  );
}

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('login');

  return (
    <PythonBridgeProvider>
      <div className="h-screen w-screen overflow-hidden bg-[#080c24]">
        {currentPage === 'login' ? (
          <Login onNavigate={setCurrentPage} />
        ) : (
          <PageRouter />
        )}
      </div>
    </PythonBridgeProvider>
  );
}

export default App;
