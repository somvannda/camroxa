import { useEffect, useState } from 'react'

export function GeneratingTitleLabel(): React.JSX.Element {
  const [dots, setDots] = useState(0)

  useEffect(() => {
    const timerId = window.setInterval(() => {
      setDots((current) => (current + 1) % 3)
    }, 450)
    return () => window.clearInterval(timerId)
  }, [])

  return <span className="text-slate-300">Generating{'.'.repeat(dots + 1)}</span>
}
