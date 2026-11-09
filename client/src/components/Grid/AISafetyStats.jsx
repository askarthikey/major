import React from 'react';

export default function AISafetyStats({ stats }) {
  return (
    <div className="bg-slate-900/50 backdrop-blur-md border border-slate-800 border-l-4 border-l-blue-500 rounded-xl p-6 transition-all hover:border-slate-700 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xl">🛡️</span>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">AI Safety Monitor</span>
        </div>
        <div className="px-2 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-[10px] font-semibold text-blue-400">
          LIVE ENGINE
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-800/40 p-4 rounded-lg border border-slate-700/50 text-center group hover:bg-slate-800/60 transition-colors">
          <div className="text-slate-500 text-[10px] uppercase font-medium mb-1 tracking-tight">Active Model</div>
          <div className="text-blue-400 font-bold text-lg leading-tight">GraphSAGE v1.0</div>
        </div>

        <div className="bg-slate-800/40 p-4 rounded-lg border border-slate-700/50 text-center group hover:bg-slate-800/60 transition-colors">
          <div className="text-slate-500 text-[10px] uppercase font-medium mb-1 tracking-tight">Inference Speed</div>
          <div className="text-slate-100 font-bold text-lg leading-tight">{stats?.avg_latency || '0.2'}ms</div>
        </div>

        <div className="bg-slate-800/40 p-4 rounded-lg border border-slate-700/50 text-center group hover:bg-slate-800/60 transition-colors">
          <div className="text-slate-500 text-[10px] uppercase font-medium mb-1 tracking-tight">Violations Blocked</div>
          <div className="text-red-400 font-bold text-lg leading-tight">{stats?.violations_prevented || 0}</div>
        </div>

        <div className="bg-slate-800/40 p-4 rounded-lg border border-slate-700/50 text-center group hover:bg-slate-800/60 transition-colors">
          <div className="text-slate-500 text-[10px] uppercase font-medium mb-1 tracking-tight">Safety Rate</div>
          <div className="text-emerald-400 font-bold text-lg leading-tight">{stats?.safety_rate || '98.5'}%</div>
        </div>
      </div>
    </div>
  );
}
