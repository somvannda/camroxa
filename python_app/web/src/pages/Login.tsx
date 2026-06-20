import React, { useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Zap, Music, Film, GitBranch, Eye, EyeOff, Minus, Square, X } from 'lucide-react';
import type { PageKey } from '../types';

interface LoginProps {
  onNavigate: (page: PageKey) => void;
}

export function Login({ onNavigate }: LoginProps) {
  const { bridge } = usePythonBridge();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (isLogin) {
        await bridge?.login(email, password);
      } else {
        await bridge?.register(email, password, displayName);
      }
      onNavigate('home');
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen">
      {/* Left: Brand panel - 50% */}
      <div className="relative flex w-1/2 items-center justify-center bg-gradient-to-br from-[#4c1d95] via-[#6d28d9] to-[#a855f7] p-8 overflow-hidden">
        {/* Background decorative elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-white/5 blur-3xl" />
          <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-[#a855f7]/20 blur-3xl" />
        </div>

        <div className="relative max-w-md text-center">
          <div className="mb-8 flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-white/10 backdrop-blur-sm shadow-2xl">
              <Zap className="h-10 w-10 text-white" />
            </div>
          </div>
          <h1 className="mb-4 text-5xl font-bold text-white tracking-tight">
            CAMXORA
          </h1>
          <p className="mb-10 text-lg text-white/70 leading-relaxed">
            Create studio-grade music videos, automatically.
          </p>
          <div className="space-y-5 text-left max-w-xs mx-auto">
            <div className="flex items-center gap-4 text-white/90">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
                <Music className="h-5 w-5" />
              </div>
              <span className="text-[14px]">AI-powered song generation</span>
            </div>
            <div className="flex items-center gap-4 text-white/90">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
                <Film className="h-5 w-5" />
              </div>
              <span className="text-[14px]">Spectrum video rendering</span>
            </div>
            <div className="flex items-center gap-4 text-white/90">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
                <GitBranch className="h-5 w-5" />
              </div>
              <span className="text-[14px]">Batch pipelines & auto-upload</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right: Form panel - 50% */}
      <div className="relative flex w-1/2 items-center justify-center bg-[#080c24] p-8">
        {/* Window controls */}
        <div className="absolute right-4 top-4 flex gap-1">
          <button
            onClick={() => bridge?.minimize_window()}
            className="flex h-8 w-10 items-center justify-center rounded-lg hover:bg-white/5 transition-colors"
          >
            <Minus className="h-4 w-4 text-gray-500" />
          </button>
          <button
            onClick={() => bridge?.maximize_window()}
            className="flex h-8 w-10 items-center justify-center rounded-lg hover:bg-white/5 transition-colors"
          >
            <Square className="h-3 w-3 text-gray-500" />
          </button>
          <button
            onClick={() => bridge?.close_window()}
            className="flex h-8 w-10 items-center justify-center rounded-lg hover:bg-red-500/80 transition-colors"
          >
            <X className="h-4 w-4 text-gray-500" />
          </button>
        </div>

        <div className="w-full max-w-[360px]">
          <h2 className="mb-2 text-[28px] font-bold text-white">Welcome back</h2>
          <p className="mb-8 text-[14px] text-gray-400">
            {isLogin ? 'Sign in to your account' : 'Create a new account'}
          </p>

          {/* Tab bar */}
          <div className="mb-8 flex gap-1 rounded-xl bg-[#0f1538] p-1">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-1 rounded-lg px-4 py-2.5 text-[13px] font-medium transition-all ${
                isLogin
                  ? 'bg-gradient-to-r from-[#7c3aed] to-[#a855f7] text-white shadow-lg shadow-purple-500/25'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Login
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-1 rounded-lg px-4 py-2.5 text-[13px] font-medium transition-all ${
                !isLogin
                  ? 'bg-gradient-to-r from-[#7c3aed] to-[#a855f7] text-white shadow-lg shadow-purple-500/25'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Register
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {!isLogin && (
              <div>
                <label className="mb-2 block text-[13px] font-medium text-gray-300">
                  Display Name
                </label>
                <Input
                  type="text"
                  placeholder="Your name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  required={!isLogin}
                  className="h-12 rounded-xl border-white/10 bg-white/5 text-white placeholder-gray-500 focus:border-[#7c3aed]/50 focus:ring-[#7c3aed]/30"
                />
              </div>
            )}
            <div>
              <label className="mb-2 block text-[13px] font-medium text-gray-300">
                Email
              </label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="h-12 rounded-xl border-white/10 bg-white/5 text-white placeholder-gray-500 focus:border-[#7c3aed]/50 focus:ring-[#7c3aed]/30"
              />
            </div>
            <div>
              <label className="mb-2 block text-[13px] font-medium text-gray-300">
                Password
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="h-12 rounded-xl border-white/10 bg-white/5 pr-12 text-white placeholder-gray-500 focus:border-[#7c3aed]/50 focus:ring-[#7c3aed]/30"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-3 text-[13px] text-red-400">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="h-12 w-full rounded-xl bg-gradient-to-r from-[#7c3aed] to-[#a855f7] text-[14px] font-semibold shadow-lg shadow-purple-500/25 hover:opacity-90 transition-opacity"
              disabled={loading}
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Please wait...
                </div>
              ) : (
                isLogin ? 'Sign In' : 'Create Account'
              )}
            </Button>
          </form>

          <p className="mt-8 text-center text-[12px] text-gray-500">
            Don't have an account?{' '}
            <button
              onClick={() => setIsLogin(false)}
              className="text-[#a855f7] hover:text-[#c084fc] transition-colors"
            >
              Sign up
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
