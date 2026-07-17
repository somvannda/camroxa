import { Card } from '@/shared/ui/card'

type PlaceholderPageProps = {
  eyebrow: string
  title: string
  description: string
}

export function PlaceholderPage({
  eyebrow,
  title,
  description,
}: PlaceholderPageProps): React.JSX.Element {
  return (
    <Card className="p-6">
      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{eyebrow}</p>
      <h2 className="mt-2 text-2xl font-semibold text-white">{title}</h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">{description}</p>
    </Card>
  )
}
