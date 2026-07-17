import { useQuery } from '@tanstack/react-query'

import { getDesktopApi } from '@/shared/api/desktop'
import {
  apiGetMe,
  apiGetSettings,
  apiListProfiles,
  apiListPromptDescriptionNames,
  apiListPromptStructureNames,
  apiListYouTubeConnections,
} from '@/shared/api/platformEndpoints'

const API_BASE_URL_STORAGE_KEY = 'camxora.apiBaseUrl'

export function useSettingsWorkspaceQuery() {
  return useQuery({
    queryKey: ['settings-workspace'],
    queryFn: async () => {
      const desktopApi = getDesktopApi()
      const [me, profiles, settings, descriptionOptions, structureOptions, youtubeConnections, appMeta, storedApiBaseUrl, videoWorkspace] = await Promise.all([
        apiGetMe(),
        apiListProfiles(),
        apiGetSettings(),
        apiListPromptDescriptionNames(),
        apiListPromptStructureNames(),
        apiListYouTubeConnections(),
        desktopApi.getAppMeta(),
        desktopApi.secureStorage.get(API_BASE_URL_STORAGE_KEY),
        desktopApi.video.getWorkspaceState(),
      ])

      const apiBaseUrl = storedApiBaseUrl?.trim()
        ? storedApiBaseUrl.trim().replace(/\/+$/, '')
        : 'http://localhost:8000/api/v1'

      return {
        me,
        profiles,
        settings,
        descriptionOptions,
        structureOptions,
        youtubeConnections,
        appMeta,
        apiBaseUrl,
        isApiBaseUrlOverridden: Boolean(storedApiBaseUrl?.trim()),
        videoWorkspace,
      }
    },
    staleTime: 30_000,
  })
}
