import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TrainingMetric } from '../lib/types';

interface Props {
  metrics: TrainingMetric[];
  show: 'loss' | 'map';
}

export function MetricsChart({ metrics, show }: Props) {
  const data = metrics.map((m) => ({
    epoch: m.epoch,
    loss: m.loss != null ? Number(m.loss) : null,
    val_loss: m.val_loss != null ? Number(m.val_loss) : null,
    map50: m.map50 != null ? Number(m.map50) : null,
    map5095: m.map5095 != null ? Number(m.map5095) : null,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="epoch" stroke="#64748b" fontSize={12} />
          <YAxis stroke="#64748b" fontSize={12} />
          <Tooltip />
          <Legend />
          {show === 'loss' ? (
            <>
              <Line type="monotone" dataKey="loss" stroke="#3b82f6" dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="val_loss" stroke="#ef4444" dot={false} isAnimationActive={false} />
            </>
          ) : (
            <>
              <Line type="monotone" dataKey="map50" stroke="#0ea5e9" dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="map5095" stroke="#16a34a" dot={false} isAnimationActive={false} />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
