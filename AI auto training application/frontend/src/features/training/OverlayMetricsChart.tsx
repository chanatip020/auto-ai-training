import { useMemo, useState } from 'react';
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import type { TrainingMetric } from '../../lib/types';
import { useTrainingMetrics } from './api';


type MetricKey = 'loss' | 'val_loss' | 'precision' | 'recall' | 'map50' | 'map5095';

const METRIC_OPTIONS: { value: MetricKey; label: string }[] = [
  { value: 'map5095', label: 'mAP50-95' },
  { value: 'map50',   label: 'mAP50' },
  { value: 'loss',    label: 'Loss (train)' },
  { value: 'val_loss',label: 'Loss (val)' },
  { value: 'precision', label: 'Precision' },
  { value: 'recall',  label: 'Recall' },
];

const SERIES_COLORS = ['#2563eb', '#ea580c', '#16a34a', '#9333ea', '#0891b2'];


interface RunRef {
  id: string;
  label: string;  // short display label, e.g. "A" or "v1 · yolov8n"
}


/** Overlay loss / mAP curves from N selected training runs on one chart. */
export function OverlayMetricsChart({ runs }: { runs: RunRef[] }) {
  const [metric, setMetric] = useState<MetricKey>('map5095');

  // We can only call hooks unconditionally — fetch for up to 5 runs.
  // (UX limits selection to 2 today, but keep it future-proof.)
  const m0 = useTrainingMetrics(runs[0]?.id);
  const m1 = useTrainingMetrics(runs[1]?.id);
  const m2 = useTrainingMetrics(runs[2]?.id);
  const m3 = useTrainingMetrics(runs[3]?.id);
  const m4 = useTrainingMetrics(runs[4]?.id);
  const queries = [m0, m1, m2, m3, m4];

  // Merge: build a row per epoch with one column per run.
  const data = useMemo(() => {
    const byEpoch = new Map<number, Record<string, number | null>>();
    runs.forEach((run, idx) => {
      const items = queries[idx].data?.items ?? [];
      for (const m of items) {
        const row = byEpoch.get(m.epoch) ?? { epoch: m.epoch };
        const v = (m as TrainingMetric)[metric];
        row[`run_${idx}`] = v != null ? Number(v) : null;
        byEpoch.set(m.epoch, row);
      }
    });
    return [...byEpoch.values()].sort((a, b) => Number(a.epoch) - Number(b.epoch));
  }, [runs, queries, metric]);

  const loading = queries.slice(0, runs.length).some((q) => q.isLoading);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-700">Metric:</span>
        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs">
          {METRIC_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setMetric(opt.value)}
              className={
                'rounded-md px-2.5 py-1 transition ' +
                (metric === opt.value
                  ? 'bg-white shadow-sm font-medium text-slate-900'
                  : 'text-slate-500 hover:text-slate-700')
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
        {loading && <span className="text-[11px] text-slate-500">loading…</span>}
      </div>

      <div className="h-72 w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="epoch" stroke="#64748b" fontSize={12} />
            <YAxis stroke="#64748b" fontSize={12} />
            <Tooltip />
            <Legend />
            {runs.map((run, idx) => (
              <Line
                key={run.id}
                type="monotone"
                dataKey={`run_${idx}`}
                name={run.label}
                stroke={SERIES_COLORS[idx % SERIES_COLORS.length]}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
