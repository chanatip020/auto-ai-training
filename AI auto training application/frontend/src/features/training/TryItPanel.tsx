import { useRef, useState } from 'react';
import { Button } from '../../components/Button';
import { Card, CardBody, CardHeader } from '../../components/Card';
import { Field, Input, Select } from '../../components/Input';
import { Spinner } from '../../components/Spinner';
import { ApiError } from '../../lib/api';
import { num } from '../../lib/format';
import {
  useExportModel,
  usePredict,
  type ExportResult,
  type PredictionResult,
} from './api';


export function TryItPanel({ jobId }: { jobId: string }) {
  const predict = usePredict(jobId);
  const exporter = useExportModel(jobId);

  const [file, setFile] = useState<File | null>(null);
  const [conf, setConf] = useState(0.25);
  const [iou, setIou] = useState(0.7);
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [format, setFormat] = useState<'onnx' | 'torchscript' | 'coreml' | 'tflite'>('onnx');
  const [exportInfo, setExportInfo] = useState<ExportResult | null>(null);

  async function onRun() {
    if (!file) return;
    setResult(null);
    try {
      const r = await predict.mutateAsync({ file, conf, iou });
      setResult(r);
    } catch {/* shown via predict.error */}
  }

  async function onExport() {
    setExportInfo(null);
    try {
      const r = await exporter.mutateAsync(format);
      setExportInfo(r);
    } catch {/* shown via exporter.error */}
  }

  function onFile(f: File | null) {
    setFile(f);
    setResult(null);
    if (imgUrl) URL.revokeObjectURL(imgUrl);
    setImgUrl(f ? URL.createObjectURL(f) : null);
  }

  const predErr = predict.error instanceof ApiError ? predict.error.message : null;
  const expErr = exporter.error instanceof ApiError ? exporter.error.message : null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-2">
        <CardHeader title="Try it" subtitle="Drag an image to see the trained model's predictions." />
        <CardBody className="space-y-3">
          <label className="block cursor-pointer rounded-md border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center hover:border-blue-400">
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => onFile(e.target.files?.[0] ?? null)}
            />
            {file ? (
              <p className="text-sm font-medium text-slate-800">
                {file.name}
                <span className="ml-2 text-xs text-slate-500">
                  ({(file.size / 1024).toFixed(1)} KB)
                </span>
              </p>
            ) : (
              <p className="text-sm text-slate-500">Click to choose an image</p>
            )}
          </label>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Confidence threshold (conf)">
              <Input
                type="number" step={0.05} min={0} max={1}
                value={conf} onChange={(e) => setConf(parseFloat(e.target.value || '0.25'))}
              />
            </Field>
            <Field label="IoU threshold (iou)">
              <Input
                type="number" step={0.05} min={0} max={1}
                value={iou} onChange={(e) => setIou(parseFloat(e.target.value || '0.7'))}
              />
            </Field>
          </div>

          <div className="flex justify-end">
            <Button onClick={onRun} disabled={!file} loading={predict.isPending}>
              Run prediction
            </Button>
          </div>

          {predErr && (
            <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700 whitespace-pre-line">
              {predErr}
            </p>
          )}

          {imgUrl && (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-2">
              <ImageWithOverlay src={imgUrl} result={result} />
            </div>
          )}
        </CardBody>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader title="Predictions" />
          <CardBody>
            {predict.isPending && <Spinner />}
            {result && result.predictions.length === 0 && (
              <p className="text-xs text-slate-500">No detections above confidence threshold.</p>
            )}
            {result && result.predictions.length > 0 && (
              <ul className="space-y-1 text-xs">
                {result.predictions.slice(0, 20).map((p, i) => (
                  <li key={i} className="flex items-center justify-between rounded bg-slate-50 px-2 py-1">
                    <span className="font-mono">{p.class_name}</span>
                    <span className="text-slate-600">{num(p.confidence, 3)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Export" subtitle="Convert best.pt to a portable format." />
          <CardBody className="space-y-3">
            <Field label="Format">
              <Select value={format} onChange={(e) => setFormat(e.target.value as typeof format)}>
                <option value="onnx">ONNX (cross-platform)</option>
                <option value="torchscript">TorchScript</option>
                <option value="coreml">CoreML (iOS / macOS)</option>
                <option value="tflite">TFLite (mobile / edge)</option>
              </Select>
            </Field>
            <div className="flex justify-end">
              <Button onClick={onExport} loading={exporter.isPending}>
                Export
              </Button>
            </div>
            {expErr && (
              <p className="rounded bg-red-50 px-3 py-2 text-xs text-red-700 whitespace-pre-line">
                {expErr}
              </p>
            )}
            {exportInfo && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                Exported <span className="font-mono">{exportInfo.name}</span>. Find it in the
                <strong> Artifacts</strong> list above.
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}


/** Draws the image and overlays bboxes/polygons. */
function ImageWithOverlay({ src, result }: { src: string; result: PredictionResult | null }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);

  if (!result) {
    return (
      <img
        src={src}
        alt="upload"
        className="max-h-96 w-full rounded object-contain"
        onLoad={(e) => {
          const i = e.currentTarget;
          setImgSize({ w: i.naturalWidth, h: i.naturalHeight });
        }}
      />
    );
  }

  const w = imgSize?.w ?? result.width;
  const h = imgSize?.h ?? result.height;

  return (
    <div ref={wrap} className="relative inline-block">
      <img
        src={src}
        alt="prediction"
        className="max-h-96 rounded object-contain"
        onLoad={(e) => setImgSize({
          w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight,
        })}
      />
      <svg
        viewBox={`0 0 ${w} ${h}`}
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full pointer-events-none"
      >
        {result.predictions.map((p, i) => p.bbox && (
          <g key={i}>
            <rect
              x={p.bbox[0]} y={p.bbox[1]}
              width={p.bbox[2] - p.bbox[0]} height={p.bbox[3] - p.bbox[1]}
              fill="none" stroke="#3b82f6" strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
            <text
              x={p.bbox[0]} y={Math.max(p.bbox[1] - 4, 12)}
              fill="#1e3a8a" fontSize={14} fontWeight={700}
              style={{ paintOrder: 'stroke', stroke: 'white', strokeWidth: 3 }}
            >
              {p.class_name} {num(p.confidence, 2)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
