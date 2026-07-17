import { useVideoWorkspaceCoordinator } from '@/features/video/workspace/useVideoWorkspaceCoordinator'
import { VideoWorkspaceShell } from '@/features/video/workspace/VideoWorkspaceShell'
import { Card } from '@/shared/ui/card'

export function VideoWorkspacePage(): React.JSX.Element {
  const { isError, workspaceViewModel } = useVideoWorkspaceCoordinator()

  return (
    <div className="grid h-full min-h-0 gap-4 overflow-hidden">
      {isError ? (
        <Card className="border-rose-500/25 bg-rose-500/10 p-6">
          <p className="text-sm text-rose-200">
            Unable to load the desktop video workspace snapshot right now. Refresh after the Electron bridge becomes
            available again.
          </p>
        </Card>
      ) : null}

      {!isError ? (
        <VideoWorkspaceShell {...workspaceViewModel} />
      ) : null}
    </div>
  )
}
