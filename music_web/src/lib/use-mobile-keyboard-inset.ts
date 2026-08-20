'use client';

import { useEffect } from 'react';

/**
 * iOS Safari usually keeps the layout viewport full-height when the keyboard
 * opens, so `position: fixed` bars sit behind it. Chrome with
 * `interactive-widget: resizes-content` already shrinks the layout, so the
 * computed inset stays ~0 there.
 */
export function useMobileKeyboardInset() {
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;

    const sync = () => {
      if (window.matchMedia('(min-width: 768px)').matches) {
        document.documentElement.style.setProperty('--music-keyboard-inset', '0px');
        return;
      }
      const inset = Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop);
      document.documentElement.style.setProperty('--music-keyboard-inset', `${Math.round(inset)}px`);
    };

    sync();
    viewport.addEventListener('resize', sync);
    viewport.addEventListener('scroll', sync);
    window.addEventListener('focusout', sync);
    return () => {
      viewport.removeEventListener('resize', sync);
      viewport.removeEventListener('scroll', sync);
      window.removeEventListener('focusout', sync);
      document.documentElement.style.removeProperty('--music-keyboard-inset');
    };
  }, []);
}
