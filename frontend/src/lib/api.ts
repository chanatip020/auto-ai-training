const API_BASE_URL = "http://127.0.0.1:8000";

export async function analyzeDataset(datasetPath: string) {
    const res = await fetch(`${API_BASE_URL}/api/dataset/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset_path: datasetPath }),
    });

    if (!res.ok) throw new Error(await res.text());
    return res.json();
}



export async function generateRecommendations(datasetReportPath?: string) {
    const res = await fetch(`${API_BASE_URL}/api/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            dataset_report_path: datasetReportPath ?? null,
            training_result_path: null,
        }),
    });

    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function getExperiments() {
    const res = await fetch(`${API_BASE_URL}/api/experiments?limit=20`);

    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function getBestExperiment() {
    const res = await fetch(`${API_BASE_URL}/api/experiments/best`);

    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function startTraining(payload: {
    dataset_path: string;
    model: string;
    epochs: number;
    imgsz: number;
    batch: string;
    device: string;
}) {
    const res = await fetch(`${API_BASE_URL}/api/training/start`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });

    if (!res.ok) {
        throw new Error(await res.text());
    }

    return res.json();
}

export async function getTrainingProgress(jobId: string) {
    const res = await fetch(`${API_BASE_URL}/api/training/progress/${jobId}`);

    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

export async function stopTraining(jobId: string) {

    const res = await fetch(
        `${API_BASE_URL}/api/training/stop/${jobId}`,
        {
            method: "POST",
        }
    );

    if (!res.ok) {
        throw new Error(await res.text());
    }

    return res.json();
}