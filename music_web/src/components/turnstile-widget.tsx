'use client';

import Script from 'next/script';
import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: Record<string, unknown>,
      ) => string;
      reset: (widgetId?: string | HTMLElement) => void;
      remove: (widgetId?: string | HTMLElement) => void;
    };
    onTurnstileLoad?: () => void;
  }
}

type TurnstileWidgetProps = {
  action: 'login' | 'register';
  onToken: (token: string) => void;
  onExpire?: () => void;
  onError?: () => void;
};

export default function TurnstileWidget({
  action,
  onToken,
  onExpire,
  onError,
}: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const onTokenRef = useRef(onToken);
  const onExpireRef = useRef(onExpire);
  const onErrorRef = useRef(onError);
  const [scriptReady, setScriptReady] = useState(false);

  useEffect(() => {
    onTokenRef.current = onToken;
    onExpireRef.current = onExpire;
    onErrorRef.current = onError;
  }, [onError, onExpire, onToken]);

  useEffect(() => {
    window.onTurnstileLoad = () => setScriptReady(true);
    if (window.turnstile) {
      setScriptReady(true);
    }
    return () => {
      if (window.onTurnstileLoad) {
        delete window.onTurnstileLoad;
      }
    };
  }, []);

  useEffect(() => {
    if (!scriptReady || !window.turnstile || !containerRef.current) {
      return;
    }

    if (widgetIdRef.current) {
      try {
        window.turnstile.remove(widgetIdRef.current);
      } catch {
        /* ignore stale widget cleanup */
      }
      widgetIdRef.current = null;
    }

    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey:
        process.env.NEXT_PUBLIC_CLOUDFLARE_TURNSTILE_SITE_KEY ||
        '0x4AAAAAAERrvCRyn8xcIet3',
      action,
      theme: 'dark',
      callback: (token: string) => onTokenRef.current(token),
      'expired-callback': () => {
        onTokenRef.current('');
        onExpireRef.current?.();
      },
      'error-callback': () => {
        onTokenRef.current('');
        onErrorRef.current?.();
      },
    });

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          /* ignore */
        }
        widgetIdRef.current = null;
      }
    };
  }, [action, scriptReady]);

  return (
    <>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=onTurnstileLoad"
        async
        defer
      />
      <div ref={containerRef} className="min-h-[65px]" />
    </>
  );
}
