import { useState, useEffect } from "react";
import {
  analyzeDataset,
  generateRecommendations,
  getBestExperiment,
} from "./lib/api";
import {
  startTraining,
  getTrainingProgress,
  getExperiments,
  stopTraining,
} from "./lib/api";

type AnyObject = Record<string, any>;

export default function App() {
  const [datasetPath, setDatasetPath] = useState("");
  const [datasetReport, setDatasetReport] = useState<AnyObject | null>(null);
  const [recommendation, setRecommendation] = useState<AnyObject | null>(null);
  const [experiments, setExperiments] = useState<any[]>([]);
  const [best, setBest] = useState<AnyObject | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [model, setModel] = useState("yolo11s.pt");
  const [epochs, setEpochs] = useState(100);
  const [imgsz, setImgsz] = useState(640);
  const [batch, setBatch] = useState("8");
  const [device, setDevice] = useState("0");
  const [trainingJobId, setTrainingJobId] = useState("");
  const [trainingProgress, setTrainingProgress] = useState(0);
  const [currentEpoch, setCurrentEpoch] = useState(0);
  const [totalEpochs, setTotalEpochs] = useState(0);
  const [trainingStatus, setTrainingStatus] = useState("");
  const [trainingResult, setTrainingResult] = useState<any>(null);

  async function handleStopTraining() {

    try {

      if (!trainingJobId) return;

      await stopTraining(trainingJobId);

      setTrainingStatus("stopping");

    } catch (err: any) {

      setError(err.message);
    }
  }

  async function handleTrain() {
    try {
      setError("");
      setLoading("train");
      setTrainingProgress(0);
      setCurrentEpoch(0);
      setTrainingStatus("starting");
      setTrainingResult(null);

      const result = await startTraining({
        dataset_path: datasetPath,
        model,
        epochs,
        imgsz,
        batch,
        device,
      });

      setTrainingJobId(result.job_id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }
  useEffect(() => {
    if (!trainingJobId) return;

    const interval = setInterval(async () => {
      try {
        const progress = await getTrainingProgress(trainingJobId);

        setTrainingProgress(progress.progress ?? 0);
        setCurrentEpoch(progress.current_epoch ?? 0);
        setTotalEpochs(progress.total_epochs ?? epochs);
        setTrainingStatus(progress.status ?? "");

        if (progress.status === "completed") {
          setTrainingResult(progress.result);

          const history = await getExperiments();
          setExperiments(history.data);

          clearInterval(interval);
        }

        if (progress.status === "failed") {
          setError(progress.error ?? "Training failed");
          clearInterval(interval);
        }

        if (progress.status === "stopped") {

          clearInterval(interval);
        }
      } catch (err: any) {
        setError(err.message);
        clearInterval(interval);
      }
    },);

    return () => clearInterval(interval);
  }, [trainingJobId]);
  async function handleAnalyze() {
    try {
      setError("");
      setLoading("analyze");

      const result = await analyzeDataset(datasetPath);
      setDatasetReport(result.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }


  async function handleRecommend() {
    try {
      setError("");
      setLoading("recommend");

      const result = await generateRecommendations();
      setRecommendation(result.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }

  async function handleLoadHistory() {
    try {
      setError("");
      setLoading("history");

      const result = await getExperiments();
      setExperiments(result.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }

  async function handleBest() {
    try {
      setError("");
      setLoading("best");

      const result = await getBestExperiment();
      setBest(result.data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }

  const summary = datasetReport?.summary;
  const classes = datasetReport?.class_distribution ?? {};
  const issues = datasetReport?.issues ?? {};

  return (
    <div className="min-h-screen bg-slate-100 p-6 text-slate-900">
      <div className="mx-auto max-w-7xl space-y-6">
        <header>
          <h1 className="text-3xl font-bold">AI Model Studio</h1>
          <p className="text-slate-500">
            Dataset Analysis • Recommendation • Experiment Tracking
          </p>
        </header>

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        )}

        <section className="rounded-2xl bg-white p-5 shadow">
          <h2 className="mb-4 text-xl font-semibold">1. Dataset Analyzer</h2>

          <div className="flex gap-3">
            <input
              className="flex-1 rounded-xl border px-4 py-2"
              placeholder="D:/CTV/dataset/yolo_project"
              value={datasetPath}
              onChange={(e) => setDatasetPath(e.target.value)}
            />

            <button
              onClick={handleAnalyze}
              className="rounded-xl bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700"
            >
              {loading === "analyze" ? "Analyzing..." : "Analyze"}
            </button>
          </div>

          {summary && (
            <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-5">
              <Metric title="Images" value={summary.total_images} />
              <Metric title="Labels" value={summary.total_labels} />
              <Metric title="BBox" value={summary.total_bbox} />
              <Metric title="Classes" value={summary.total_classes} />
              <Metric title="Health" value={summary.health_score} />
            </div>
          )}

          {datasetReport && (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border p-4">
                <h3 className="mb-3 font-semibold">Class Distribution</h3>
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="py-2">Class ID</th>
                      <th>Class Name</th>
                      <th>BBox</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(classes).map(([id, info]: any) => (
                      <tr key={id} className="border-b">
                        <td className="py-2">{id}</td>
                        <td>{info.class_name}</td>
                        <td>{info.bbox_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="rounded-xl border p-4">
                <h3 className="mb-3 font-semibold">Dataset Issues</h3>
                <Issue title="Missing Labels" count={issues.missing_labels?.length ?? 0} />
                <Issue
                  title="Labels Without Images"
                  count={issues.labels_without_images?.length ?? 0}
                />
                <Issue title="Label Errors" count={issues.label_errors?.length ?? 0} />
              </div>
            </div>
          )}
        </section>

        <section className="rounded-2xl bg-white p-5 shadow">
          <h2 className="mb-4 text-xl font-semibold">2. Recommendation Engine</h2>

          <button
            onClick={handleRecommend}
            className="rounded-xl bg-emerald-600 px-5 py-2 font-medium text-white hover:bg-emerald-700"
          >
            {loading === "recommend" ? "Generating..." : "Generate Recommendation"}
          </button>

          {recommendation && (
            <div className="mt-4 space-y-3">
              {recommendation.recommendations?.map((item: any, index: number) => (
                <div key={index} className="rounded-xl border p-4">
                  <div className="font-semibold">{item.title}</div>
                  <div className="text-sm text-slate-600">{item.message}</div>
                  <div className="mt-2 text-sm font-medium text-blue-700">
                    Action: {item.action}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="rounded-2xl bg-white p-5 shadow">
          <h2 className="mb-4 text-xl font-semibold">
            3. Training Dashboard
          </h2>

          <div className="grid gap-4 md:grid-cols-2">

            <div>
              <label className="mb-1 block text-sm font-medium">
                YOLO Model
              </label>

              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full rounded-xl border px-4 py-2"
              >
                <option value="yolo11n.pt">yolo11n.pt</option>
                <option value="yolo11s.pt">yolo11s.pt</option>
                <option value="yolo11m.pt">yolo11m.pt</option>
                <option value="yolo11l.pt">yolo11l.pt</option>
              </select>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Epochs
              </label>

              <input
                type="number"
                value={epochs}
                onChange={(e) => setEpochs(Number(e.target.value))}
                className="w-full rounded-xl border px-4 py-2"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Image Size
              </label>

              <input
                type="number"
                value={imgsz}
                onChange={(e) => setImgsz(Number(e.target.value))}
                className="w-full rounded-xl border px-4 py-2"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Batch
              </label>

              <input
                value={batch}
                onChange={(e) => setBatch(e.target.value)}
                className="w-full rounded-xl border px-4 py-2"
              />
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium">
                Device
              </label>

              <input
                value={device}
                onChange={(e) => setDevice(e.target.value)}
                className="w-full rounded-xl border px-4 py-2"
              />
            </div>
          </div>


          <div className="mt-6 flex gap-3">

            <button
              onClick={handleTrain}
              className="rounded-xl bg-purple-600 px-6 py-3 font-medium text-white hover:bg-purple-700"
            >
              {loading === "train"
                ? "Starting..."
                : "Start Training"}
            </button>

            <button
              onClick={handleStopTraining}
              disabled={!trainingJobId}
              className="rounded-xl bg-red-600 px-6 py-3 font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Stop Training
            </button>

          </div>
          {trainingStatus && (
            <div className="mt-6 rounded-xl border bg-slate-50 p-4">
              <div className="mb-2 flex justify-between text-sm">
                <span>Status: {trainingStatus}</span>
                <span>
                  Epoch {currentEpoch} / {totalEpochs || epochs}
                </span>
              </div>

              <div className="h-5 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full bg-blue-600 transition-all duration-500"
                  style={{ width: `${trainingProgress}%` }}
                />
              </div>

              <div className="mt-2 text-sm text-slate-600">
                Progress: {trainingProgress}%
              </div>
            </div>
          )}
          {trainingResult && (
            <div className="mt-6 rounded-xl border bg-slate-50 p-4">
              <h3 className="mb-3 text-lg font-semibold">
                Training Result
              </h3>

              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">

                <Metric
                  title="Precision"
                  value={trainingResult.metrics?.precision}
                />

                <Metric
                  title="Recall"
                  value={trainingResult.metrics?.recall}
                />

                <Metric
                  title="mAP50"
                  value={trainingResult.metrics?.mAP50}
                />

                <Metric
                  title="mAP50-95"
                  value={trainingResult.metrics?.mAP50_95}
                />
              </div>

              <div className="mt-4 text-sm text-slate-600">
                Run: {trainingResult.run_name}
              </div>

              <div className="text-sm text-slate-600">
                Model: {trainingResult.model}
              </div>
            </div>
          )}
        </section>
        <section className="rounded-2xl bg-white p-5 shadow">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold">3. Experiment Tracking</h2>

            <div className="flex gap-2">
              <button
                onClick={handleLoadHistory}
                className="rounded-xl bg-slate-800 px-4 py-2 text-white"
              >
                Load History
              </button>
              <button
                onClick={handleBest}
                className="rounded-xl bg-purple-600 px-4 py-2 text-white"
              >
                Best Model
              </button>
            </div>
          </div>

          {best && (
            <div className="mb-4 rounded-xl border bg-purple-50 p-4">
              <div className="font-semibold">Best: {best.run_name}</div>
              <div className="text-sm text-slate-600">
                mAP50: {best.map50} | mAP50-95: {best.map50_95}
              </div>
            </div>
          )}

          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b">
                <th className="py-2">Run</th>
                <th>Model</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>mAP50</th>
                <th>mAP50-95</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((exp) => (
                <tr key={exp.id} className="border-b">
                  <td className="py-2">{exp.run_name}</td>
                  <td>{exp.model}</td>
                  <td>{exp.precision}</td>
                  <td>{exp.recall}</td>
                  <td>{exp.map50}</td>
                  <td>{exp.map50_95}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

function Metric({ title, value }: { title: string; value: any }) {
  return (
    <div className="rounded-xl border bg-slate-50 p-4 text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-slate-500">{title}</div>
    </div>
  );
}

function Issue({ title, count }: { title: string; count: number }) {
  return (
    <div className="flex justify-between border-b py-2">
      <span>{title}</span>
      <span className={count === 0 ? "font-bold text-green-600" : "font-bold text-red-600"}>
        {count}
      </span>
    </div>
  );
}