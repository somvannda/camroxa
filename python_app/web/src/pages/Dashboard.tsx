import React, { useEffect, useState } from 'react';
import { usePythonBridge } from '../bridge/usePythonBridge';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  DollarSign,
  TrendingUp,
  Zap,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  MoreHorizontal,
  CreditCard,
  Activity,
} from 'lucide-react';
import type { DashboardData } from '../types';

export function Dashboard() {
  const { call } = usePythonBridge();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const result = await call('get_dashboard_data');
      if (result) setData(result);
    } finally {
      setLoading(false);
    }
  };

  const stats = [
    {
      title: 'Total Revenue',
      value: '$128,540',
      change: '+23.5%',
      changeType: 'up' as const,
      icon: DollarSign,
      iconBg: 'bg-emerald-500/20',
      iconColor: 'text-emerald-400',
      sparkline: [40, 35, 50, 45, 60, 55, 70, 65, 80, 75, 85, 90],
    },
    {
      title: 'Monthly Recurring Revenue',
      value: '$42,850',
      change: '+18.2%',
      changeType: 'up' as const,
      icon: CreditCard,
      iconBg: 'bg-blue-500/20',
      iconColor: 'text-blue-400',
      sparkline: [30, 35, 40, 38, 45, 50, 48, 55, 58, 60, 65, 70],
    },
    {
      title: 'Active Automations',
      value: '47',
      change: '+12.4%',
      changeType: 'up' as const,
      icon: Zap,
      iconBg: 'bg-purple-500/20',
      iconColor: 'text-purple-400',
      sparkline: [20, 25, 30, 28, 35, 40, 38, 45, 42, 48, 50, 47],
    },
    {
      title: 'Hours Saved',
      value: '326h',
      change: '+31.7%',
      changeType: 'up' as const,
      icon: Clock,
      iconBg: 'bg-cyan-500/20',
      iconColor: 'text-cyan-400',
      sparkline: [50, 55, 60, 58, 65, 70, 75, 80, 85, 90, 95, 100],
    },
  ];

  const recentAutomations = [
    { name: 'Lead Generation Flow', desc: 'Collects leads from landing pages', status: 'Active', value: '1,234', label: 'Leads', color: 'text-emerald-400' },
    { name: 'Client Onboarding Flow', desc: 'Automates client welcome process', status: 'Running', value: '89', label: 'Clients', color: 'text-blue-400' },
    { name: 'Invoice & Payment Flow', desc: 'Handles invoices and payments', status: 'Active', value: '$24,540', label: 'Revenue', color: 'text-emerald-400' },
    { name: 'Re-engagement Campaign', desc: 'Win back inactive leads', status: 'Paused', value: '456', label: 'Contacts', color: 'text-yellow-400' },
  ];

  const topClients = [
    { name: 'TechCorp Solutions', value: '$24,540', change: '+28.5%', gradient: 'from-blue-500 to-cyan-400', icon: '🏢' },
    { name: 'GrowthLab Agency', value: '$18,750', change: '+16.3%', gradient: 'from-pink-500 to-rose-400', icon: '🚀' },
    { name: 'InnovateX', value: '$15,630', change: '+24.7%', gradient: 'from-green-500 to-emerald-400', icon: '💡' },
    { name: 'ScaleUp Ventures', value: '$12,980', change: '+11.2%', gradient: 'from-purple-500 to-violet-400', icon: '📈' },
    { name: 'FutureStack', value: '$8,420', change: '+19.8%', gradient: 'from-cyan-500 to-blue-400', icon: '🔮' },
  ];

  const recentActivity = [
    { name: 'Lead Generation Flow', detail: 'New lead captured', time: '2m ago', icon: '🎯', iconBg: 'bg-emerald-500/20' },
    { name: 'Invoice & Payment Flow', detail: 'Payment received', time: '15m ago', icon: '💰', iconBg: 'bg-green-500/20' },
    { name: 'Client Onboarding Flow', detail: 'New client onboarded', time: '1h ago', icon: '👋', iconBg: 'bg-blue-500/20' },
    { name: 'Re-engagement Campaign', detail: 'Email sent', time: '2h ago', icon: '📧', iconBg: 'bg-purple-500/20' },
  ];

  const MiniSparkline = ({ data, color = '#a855f7' }: { data: number[]; color?: string }) => {
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;
    const width = 80;
    const height = 32;
    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg width={width} height={height} className="overflow-visible">
        <defs>
          <linearGradient id={`sparkline-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };

  const DonutChart = () => {
    const segments = [
      { label: 'Active', value: 47, color: '#10b981' },
      { label: 'Running', value: 8, color: '#3b82f6' },
      { label: 'Paused', value: 2, color: '#eab308' },
      { label: 'Failed', value: 1, color: '#ef4444' },
    ];
    const total = segments.reduce((a, b) => a + b.value, 0);
    const radius = 70;
    const strokeWidth = 12;
    const circumference = 2 * Math.PI * radius;
    let accumulated = 0;

    return (
      <div className="flex flex-col items-center">
        <div className="relative h-[180px] w-[180px]">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 180 180">
            <circle cx="90" cy="90" r={radius} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth={strokeWidth} />
            {segments.map((seg, i) => {
              const strokeDasharray = `${(seg.value / total) * circumference} ${circumference}`;
              const strokeDashoffset = -((accumulated / total) * circumference);
              accumulated += seg.value;
              return (
                <circle
                  key={i}
                  cx="90"
                  cy="90"
                  r={radius}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={strokeWidth}
                  strokeDasharray={strokeDasharray}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  className="transition-all duration-1000"
                />
              );
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-bold text-white">{total}</span>
            <span className="text-[11px] text-gray-400">Active</span>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2">
          {segments.map((seg) => (
            <div key={seg.label} className="flex items-center gap-2">
              <div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
              <span className="text-[12px] text-gray-400">{seg.label}</span>
              <span className="text-[12px] font-medium text-white ml-auto">{seg.value}</span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const LineChart = () => {
    const data = [
      { day: 'May 1', value: 45000 },
      { day: 'May 8', value: 52000 },
      { day: 'May 15', value: 48000 },
      { day: 'May 22', value: 78000 },
      { day: 'May 29', value: 128540 },
    ];
    const maxValue = 150000;
    const width = 600;
    const height = 200;
    const padding = { top: 20, right: 20, bottom: 30, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    const points = data.map((d, i) => ({
      x: padding.left + (i / (data.length - 1)) * chartWidth,
      y: padding.top + chartHeight - (d.value / maxValue) * chartHeight,
    }));

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
    const areaPath = `${linePath} L ${points[points.length - 1].x} ${padding.top + chartHeight} L ${points[0].x} ${padding.top + chartHeight} Z`;

    return (
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#a855f7" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#7c3aed" />
            <stop offset="100%" stopColor="#00d4ff" />
          </linearGradient>
        </defs>
        {/* Grid lines */}
        {[0, 50000, 100000, 150000].map((v) => (
          <g key={v}>
            <line
              x1={padding.left}
              y1={padding.top + chartHeight - (v / maxValue) * chartHeight}
              x2={padding.left + chartWidth}
              y2={padding.top + chartHeight - (v / maxValue) * chartHeight}
              stroke="rgba(255,255,255,0.05)"
              strokeDasharray="4 4"
            />
            <text
              x={padding.left - 8}
              y={padding.top + chartHeight - (v / maxValue) * chartHeight + 4}
              textAnchor="end"
              fill="#6b7280"
              fontSize="10"
            >
              ${v / 1000}K
            </text>
          </g>
        ))}
        {/* Area fill */}
        <path d={areaPath} fill="url(#chartGradient)" />
        {/* Line */}
        <path d={linePath} fill="none" stroke="url(#lineGradient)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {/* Data points */}
        {points.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="4" fill="#0a0e27" stroke="#a855f7" strokeWidth="2" />
            {i === points.length - 1 && (
              <g>
                <rect x={p.x - 28} y={p.y - 28} width="56" height="20" rx="4" fill="#7c3aed" />
                <text x={p.x} y={p.y - 14} textAnchor="middle" fill="white" fontSize="10" fontWeight="600">
                  $128,540
                </text>
              </g>
            )}
          </g>
        ))}
        {/* X-axis labels */}
        {data.map((d, i) => (
          <text
            key={i}
            x={points[i].x}
            y={height - 8}
            textAnchor="middle"
            fill="#6b7280"
            fontSize="10"
          >
            {d.day}
          </text>
        ))}
      </svg>
    );
  };

  return (
    <div className="min-h-full bg-[#080c24] p-6">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-[28px] font-bold text-white">Good morning, Alex.</h1>
          <p className="mt-1 text-[14px] text-gray-400">
            Here's what's happening with your AI automations today.
          </p>
        </div>

        {/* Stats cards */}
        <div className="grid grid-cols-4 gap-4">
          {stats.map((stat) => (
            <div
              key={stat.title}
              className="group relative overflow-hidden rounded-2xl border border-white/5 bg-gradient-to-br from-[#12162e] to-[#0d1025] p-5 transition-all hover:border-white/10 hover:shadow-lg hover:shadow-purple-500/5"
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-[12px] text-gray-400">{stat.title}</p>
                  <p className="mt-2 text-[28px] font-bold text-white">{stat.value}</p>
                  <div className="mt-2 flex items-center gap-1">
                    {stat.changeType === 'up' ? (
                      <ArrowUpRight className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <ArrowDownRight className="h-3.5 w-3.5 text-red-400" />
                    )}
                    <span className="text-[12px] font-medium text-emerald-400">
                      {stat.change}
                    </span>
                    <span className="text-[11px] text-gray-500">vs last month</span>
                  </div>
                </div>
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${stat.iconBg}`}>
                  <stat.icon className={`h-5 w-5 ${stat.iconColor}`} />
                </div>
              </div>
              {/* Sparkline */}
              <div className="mt-3 -mb-2 -mx-1">
                <MiniSparkline data={stat.sparkline} color="#a855f7" />
              </div>
            </div>
          ))}
        </div>

        {/* Middle section */}
        <div className="grid grid-cols-3 gap-4">
          {/* Revenue Overview */}
          <div className="col-span-2 rounded-2xl border border-white/5 bg-gradient-to-br from-[#12162e] to-[#0d1025] p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[15px] font-semibold text-white">Revenue Overview</h3>
              <Select defaultValue="this-month">
                <SelectTrigger className="w-[120px] h-8 rounded-lg border-white/10 bg-white/5 text-[12px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#1a1f3a] border-white/10">
                  <SelectItem value="this-month">This Month</SelectItem>
                  <SelectItem value="last-month">Last Month</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-baseline gap-3 mb-4">
              <span className="text-[32px] font-bold text-white">$128,540</span>
              <Badge variant="success" className="text-[11px] px-2 py-0.5">
                <TrendingUp className="mr-1 h-3 w-3" />
                23.5%
              </Badge>
            </div>
            <LineChart />
          </div>

          {/* Automation Status */}
          <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-[#12162e] to-[#0d1025] p-5">
            <h3 className="text-[15px] font-semibold text-white mb-4">Automation Status</h3>
            <DonutChart />
          </div>
        </div>

        {/* Bottom section */}
        <div className="grid grid-cols-3 gap-4">
          {/* Recent Automations */}
          <div className="col-span-2 rounded-2xl border border-white/5 bg-gradient-to-br from-[#12162e] to-[#0d1025] p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[15px] font-semibold text-white">Recent Automations</h3>
              <Button variant="ghost" size="sm" className="text-[12px] text-[#a855f7] hover:text-[#c084fc]">
                View All
              </Button>
            </div>
            <div className="space-y-2">
              {recentAutomations.map((item) => (
                <div
                  key={item.name}
                  className="flex items-center justify-between rounded-xl bg-white/[0.02] border border-white/5 p-4 hover:bg-white/[0.04] transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#7c3aed]/20 to-[#a855f7]/20">
                      <Zap className="h-5 w-5 text-[#a855f7]" />
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-white">{item.name}</div>
                      <div className="text-[11px] text-gray-500">{item.desc}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-6">
                    <Badge
                      variant={item.status === 'Active' ? 'success' : item.status === 'Running' ? 'default' : 'warning'}
                      className="text-[11px] px-2.5 py-0.5"
                    >
                      {item.status}
                    </Badge>
                    <div className="text-right w-24">
                      <div className="text-[13px] font-semibold text-white">{item.value}</div>
                      <div className="text-[11px] text-gray-500">{item.label}</div>
                    </div>
                    <button className="text-gray-500 hover:text-white transition-colors">
                      <MoreHorizontal className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Top Clients */}
          <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-[#12162e] to-[#0d1025] p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[15px] font-semibold text-white">Top Clients</h3>
              <Button variant="ghost" size="sm" className="text-[12px] text-[#a855f7] hover:text-[#c084fc]">
                View All
              </Button>
            </div>
            <div className="space-y-3">
              {topClients.map((client) => (
                <div key={client.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br ${client.gradient} text-[14px]`}>
                      {client.icon}
                    </div>
                    <div>
                      <div className="text-[13px] font-medium text-white">{client.name}</div>
                      <div className="text-[11px] text-gray-500">{client.value}</div>
                    </div>
                  </div>
                  <span className="text-[12px] font-medium text-emerald-400">{client.change}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="rounded-2xl border border-white/5 bg-gradient-to-br from-[#12162e] to-[#0d1025] p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[15px] font-semibold text-white">Recent Activity</h3>
            <Button variant="ghost" size="sm" className="text-[12px] text-[#a855f7] hover:text-[#c084fc]">
              View All
            </Button>
          </div>
          <div className="space-y-3">
            {recentActivity.map((item, i) => (
              <div key={i} className="flex items-center justify-between rounded-xl bg-white/[0.02] border border-white/5 p-3">
                <div className="flex items-center gap-3">
                  <div className={`flex h-9 w-9 items-center justify-center rounded-full ${item.iconBg} text-[14px]`}>
                    {item.icon}
                  </div>
                  <div>
                    <div className="text-[13px] font-medium text-white">{item.name}</div>
                    <div className="text-[11px] text-gray-500">{item.detail}</div>
                  </div>
                </div>
                <span className="text-[11px] text-gray-500">{item.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
