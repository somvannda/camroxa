import { Link } from 'react-router-dom';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function MusicWebCreditsNote() {
  return (
    <Card className="border-violet-500/20 bg-slate-900/50">
      <CardHeader>
        <CardTitle className="text-lg text-slate-100">Free daily credits</CardTitle>
        <CardDescription>
          The old <span className="font-mono">web_music_free_daily_credits</span> setting is retired.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-slate-400">
        <p>
          Free daily credits now live on the <strong className="text-slate-200">Free</strong> plan
          row (<span className="font-mono">daily_credits</span>). Edit that grant on{' '}
          <Link to="/plans" className="text-violet-300 hover:underline">
            Plans
          </Link>
          .
        </p>
        <p>
          Web Create charges the same plan amounts as desktop when the generate flag is On. CutLuy
          checkout still writes the web subscription ledger until the later one-wallet project.
        </p>
      </CardContent>
    </Card>
  );
}
