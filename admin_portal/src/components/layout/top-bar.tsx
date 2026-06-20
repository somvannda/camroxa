import { LogOut } from 'lucide-react';
import { useAuth } from '@/hooks/use-auth';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

export function TopBar() {
  const { adminEmail, logout } = useAuth();

  return (
    <header className="flex items-center justify-between h-14 px-6 bg-slate-900 border-b border-slate-800">
      <div className="text-sm font-medium text-slate-300">
        Admin Dashboard
      </div>

      <div className="flex items-center gap-3">
        {adminEmail && (
          <span className="text-sm text-slate-400">{adminEmail}</span>
        )}
        <Separator orientation="vertical" className="h-6 bg-slate-700" />
        <Button
          variant="ghost"
          size="sm"
          onClick={logout}
          className="text-slate-400 hover:text-slate-200 hover:bg-slate-800 gap-2"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </Button>
      </div>
    </header>
  );
}
