/** A simple SVG gauge for the dataset health score (0–100). */
export function HealthGauge({ score }: { score: number | null | undefined }) {
  const v = score == null ? 0 : Math.max(0, Math.min(100, Number(score)));
  const r = 56;
  const c = 2 * Math.PI * r;
  const dash = (v / 100) * c;
  const color =
    v >= 80 ? '#16a34a' : v >= 60 ? '#65a30d' : v >= 40 ? '#f59e0b' : '#dc2626';

  return (
    <div className="flex items-center gap-4">
      <svg width="140" height="140" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={r} stroke="#e2e8f0" strokeWidth="12" fill="none" />
        <circle
          cx="70"
          cy="70"
          r={r}
          stroke={color}
          strokeWidth="12"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          transform="rotate(-90 70 70)"
          style={{ transition: 'stroke-dasharray 350ms ease, stroke 350ms ease' }}
        />
        <text
          x="70"
          y="74"
          textAnchor="middle"
          fontSize="28"
          fontWeight="600"
          fill="#0f172a"
        >
          {score == null ? '—' : v.toFixed(0)}
        </text>
        <text x="70" y="96" textAnchor="middle" fontSize="11" fill="#64748b">
          / 100
        </text>
      </svg>
      <div>
        <div className="text-sm font-semibold text-slate-900">Dataset health</div>
        <p className="mt-1 max-w-xs text-xs text-slate-500">
          Weighted blend of label coverage, class balance, image quality, and
          dataset volume.
        </p>
      </div>
    </div>
  );
}
