import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Layers3, Plus, Save, Trash2 } from 'lucide-react'

import {
  apiCreateMyDescription,
  apiCreateMyStructure,
  apiDeleteMyDescription,
  apiDeleteMyStructure,
  apiListMyDescriptions,
  apiListMyStructures,
  apiUpdateMyDescription,
  apiUpdateMyStructure,
  type UserOwnedPrompt,
} from '@/shared/api/platformEndpoints'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { Textarea } from '@/shared/ui/textarea'

type PromptKind = 'descriptions' | 'structures'

type UserOwnedPromptPanelProps = {
  kind: PromptKind
}

function listQueryKey(kind: PromptKind): string[] {
  return kind === 'descriptions' ? ['my-descriptions'] : ['my-structures']
}

export function UserOwnedPromptPanel({ kind }: UserOwnedPromptPanelProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const isDescriptions = kind === 'descriptions'
  const queryKey = listQueryKey(kind)
  const listQuery = useQuery({
    queryKey,
    queryFn: isDescriptions ? apiListMyDescriptions : apiListMyStructures,
  })
  const items = listQuery.data ?? []
  const [selectedId, setSelectedId] = useState<string>('')
  const [draftName, setDraftName] = useState('')
  const [draftContent, setDraftContent] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  )

  useEffect(() => {
    if (isCreating) {
      setDraftName('')
      setDraftContent('')
      return
    }
    if (selectedItem) {
      setDraftName(selectedItem.name)
      setDraftContent(selectedItem.content)
    }
  }, [isCreating, selectedItem])

  useEffect(() => {
    if (!items.length) {
      setSelectedId('')
      return
    }
    if (!selectedId || !items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0]?.id ?? '')
      setIsCreating(false)
    }
  }, [items, selectedId])

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey }),
      queryClient.invalidateQueries({ queryKey: ['settings-workspace'] }),
      queryClient.invalidateQueries({ queryKey: ['music-workspace'] }),
    ])
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = { name: draftName.trim(), content: draftContent.trim() }
      if (isCreating) {
        return isDescriptions
          ? apiCreateMyDescription(payload)
          : apiCreateMyStructure(payload)
      }
      if (!selectedId) {
        throw new Error('Select a prompt to update.')
      }
      return isDescriptions
        ? apiUpdateMyDescription(selectedId, payload)
        : apiUpdateMyStructure(selectedId, payload)
    },
    onSuccess: async (saved: UserOwnedPrompt) => {
      setIsCreating(false)
      setSelectedId(saved.id)
      await invalidate()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!selectedId) {
        throw new Error('Select a prompt to delete.')
      }
      if (isDescriptions) {
        await apiDeleteMyDescription(selectedId)
      } else {
        await apiDeleteMyStructure(selectedId)
      }
    },
    onSuccess: async () => {
      setIsCreating(false)
      await invalidate()
    },
  })

  const canSave = draftName.trim().length > 0 && draftContent.trim().length > 0

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">
            {isDescriptions ? 'My Descriptions' : 'My Structures'}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Create and edit your own prompts. Camxora-owned prompt content stays hidden.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setIsCreating(true)
            setSelectedId('')
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          New
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
        <div className="space-y-2">
          {listQuery.isLoading ? (
            <p className="text-xs text-slate-500">Loading your prompts...</p>
          ) : items.length ? (
            items.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                  !isCreating && selectedId === item.id
                    ? 'border-sky-400/40 bg-sky-500/10 text-white'
                    : 'border-white/10 bg-slate-950/60 text-slate-300 hover:border-white/20'
                }`}
                onClick={() => {
                  setIsCreating(false)
                  setSelectedId(item.id)
                }}
              >
                {item.name}
              </button>
            ))
          ) : (
            <p className="text-xs text-slate-500">No custom prompts yet.</p>
          )}
        </div>

        <div className="space-y-3">
          {isCreating || selectedItem ? (
            <>
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-[0.16em] text-slate-500">Name</label>
                <Input value={draftName} onChange={(event) => setDraftName(event.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-xs uppercase tracking-[0.16em] text-slate-500">Content</label>
                <Textarea
                  className="min-h-[180px] font-mono text-sm"
                  value={draftContent}
                  onChange={(event) => setDraftContent(event.target.value)}
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={!canSave || saveMutation.isPending}
                  onClick={() => saveMutation.mutate()}
                >
                  <Save className="mr-2 h-4 w-4" />
                  {isCreating ? 'Create' : 'Save'}
                </Button>
                {!isCreating && selectedItem ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate()}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                ) : null}
              </div>
              {saveMutation.error ? (
                <p className="text-sm text-rose-300">
                  {saveMutation.error instanceof Error ? saveMutation.error.message : 'Unable to save prompt.'}
                </p>
              ) : null}
            </>
          ) : (
            <div className="rounded-xl border border-dashed border-white/10 px-4 py-8 text-sm text-slate-500">
              Select one of your prompts or click New to create one.
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
        {isDescriptions ? <FileText className="h-3.5 w-3.5" /> : <Layers3 className="h-3.5 w-3.5" />}
        Your prompts sync to the server and appear in Music dropdowns for your account only.
      </div>
    </div>
  )
}
