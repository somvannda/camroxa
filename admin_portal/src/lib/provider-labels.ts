/** Human-friendly labels for AI service provider ids shown on the Credits page. */
const PROVIDER_LABELS: Record<string, string> = {
  camxora_music_api: 'Camxora Music API',
  suno: 'Suno',
  deepseek: 'DeepSeek',
  openai: 'OpenAI',
  slai: 'SLAI',
  fal: 'FAL',
  kie: 'kie.ai',
};

/** Display name for a provider id, falling back to the raw id. */
export function providerLabel(id: string | null | undefined): string {
  const key = String(id ?? '').trim();
  if (!key) return '';
  return PROVIDER_LABELS[key] ?? key;
}
