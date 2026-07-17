export function isSongTitleGenerating(song: {
  title?: string | null
  status?: string | null
}): boolean {
  if (song.title?.trim()) {
    return false
  }
  const status = (song.status || 'pending').toLowerCase()
  return status === 'pending' || status === 'processing' || status === 'drafting'
}
