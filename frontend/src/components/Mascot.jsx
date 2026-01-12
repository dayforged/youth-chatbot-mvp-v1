// frontend/src/components/Mascot.jsx — Header mascot + title/status (no logic)
import React from "react";

export default function Mascot({ title, subtitle, status }) {
  return (
    <div className="mb-4 flex flex-col items-center">
      <div className="w-20 h-20 rounded-full bg-white/5 border border-white/10 flex items-center justify-center shadow-lg">
        <div className="w-12 h-12 rounded-2xl bg-white/10 border border-white/10 flex flex-col items-center justify-center">
          <div className="flex gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-white" />
            <span className="w-2.5 h-2.5 rounded-full bg-white" />
          </div>
          <span className="mt-2 w-6 h-1.5 rounded-full bg-white/60" />
        </div>
      </div>

      <div className="mt-3 text-center">
        <div className="text-sm text-white/70">{subtitle}</div>
      </div>

      <div className="mt-4 w-full bg-[#0f172a] border border-white/10 rounded-2xl px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
          <div>
            <div className="font-semibold">{title}</div>
            <div className="text-xs text-white/60">{subtitle}</div>
          </div>
        </div>
        <div className="text-xs text-white/50">{status}</div>
      </div>
    </div>
  );
}
