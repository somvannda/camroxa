/// <reference types="vite/client" />

import type { DesktopApi } from '@/shared/types/desktop'

declare global {
  interface Window {
    camxoraDesktop?: DesktopApi
  }
}
