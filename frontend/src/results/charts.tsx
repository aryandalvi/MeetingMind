import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Keyword, Person } from "../types";

// Single-series charts: one violet hue, recessive axes, hover tooltip, no legend.
const BAR = "#7b6ad9";
const AXIS = { fontSize: 12, fill: "#6b6780" };

function TooltipBox({ active, payload, unit }: { active?: boolean; payload?: { payload: { name: string; value: number; extra?: string } }[]; unit: string }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-[var(--shadow-lift)]">
      <div className="font-medium text-ink">{p.name}</div>
      <div className="text-muted">
        {p.value}
        {unit}
        {p.extra ? ` · ${p.extra}` : ""}
      </div>
    </div>
  );
}

export function TalkShareChart({ people }: { people: Person[] }) {
  const data = [...people]
    .sort((a, b) => b.talk_share - a.talk_share)
    .map((p) => ({ name: p.name, value: p.talk_share, extra: `${p.words} words, ${p.utterances} turns` }));
  return (
    <div style={{ height: Math.max(140, data.length * 44) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }} barCategoryGap={10}>
          <CartesianGrid horizontal={false} stroke="#ebe8f3" />
          <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={120} tick={AXIS} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: "#f6f4fe" }} content={<TooltipBox unit="% of words" />} />
          <Bar dataKey="value" fill={BAR} radius={[0, 4, 4, 0]} maxBarSize={22} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function KeywordChart({ keywords }: { keywords: Keyword[] }) {
  const data = keywords.slice(0, 10).map((k) => ({ name: k.phrase, value: k.mentions, extra: `rank ${k.rank}` }));
  return (
    <div style={{ height: Math.max(160, data.length * 34) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke="#ebe8f3" />
          <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={150} tick={AXIS} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: "#f6f4fe" }} content={<TooltipBox unit=" mentions" />} />
          <Bar dataKey="value" fill={BAR} radius={[0, 4, 4, 0]} maxBarSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
