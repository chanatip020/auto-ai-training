from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.dataset_analyzer import analyze_yolo_dataset
from core.recommendation_engine import generate_recommendations
from core.database import list_experiments, get_best_experiment

from core.result_parser import parse_training_result
from core.database import save_experiment

from core.trainer import train_yolo_model
from core.result_parser import parse_training_result
from core.database import save_experiment

import threading
import uuid

BASE_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI Model Studio API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRAINING_JOBS = {}
class TrainRequest(BaseModel):
    dataset_path: str
    model: str = "yolo11s.pt"
    epochs: int = 100
    imgsz: int = 640
    batch: int = 8
    device: str = "0"

class ParseTrainingRequest(BaseModel):
    run_dir: str

class AnalyzeRequest(BaseModel):
    dataset_path: str


class RecommendRequest(BaseModel):
    dataset_report_path: Optional[str] = None
    training_result_path: Optional[str] = None


@app.get("/")
def health_check():
    return {
        "message": "AI Model Studio API is running",
        "status": "ok",
    }

@app.post("/api/training/stop/{job_id}")
def stop_training(job_id: str):

    if job_id not in TRAINING_JOBS:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    TRAINING_JOBS[job_id]["stop_requested"] = True

    return {
        "success": True,
        "message": "Stop requested",
    }

@app.post("/api/training/start")
def start_training(request: TrainRequest):

    job_id = str(uuid.uuid4())

    TRAINING_JOBS[job_id] = {
        "status": "starting",
        "progress": 0,
        "current_epoch": 0,
        "total_epochs": request.epochs,
        "result": None,
        "error": None,
        "stop_requested": False,
    }

    def run_training():

        try:
            TRAINING_JOBS[job_id]["status"] = "training"

            train_result = train_yolo_model(
                dataset_dir=Path(request.dataset_path),
                model=request.model,
                epochs=request.epochs,
                imgsz=request.imgsz,
                batch=request.batch,
                device=request.device,
                job_id=job_id,
                training_jobs=TRAINING_JOBS,
            )

            parsed = parse_training_result(
                Path(train_result["result_path"])
            )

            save_experiment(parsed)

            TRAINING_JOBS[job_id]["status"] = "completed"
            TRAINING_JOBS[job_id]["progress"] = 100
            TRAINING_JOBS[job_id]["result"] = parsed

        except Exception as e:
            TRAINING_JOBS[job_id]["status"] = "failed"
            TRAINING_JOBS[job_id]["error"] = str(e)

    threading.Thread(target=run_training).start()

    return {
        "success": True,
        "job_id": job_id,
    }

@app.get("/api/training/progress/{job_id}")
def get_training_progress(job_id: str):

    if job_id not in TRAINING_JOBS:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return TRAINING_JOBS[job_id]

@app.post("/api/training/parse-and-save")
def parse_and_save_training(request: ParseTrainingRequest):

    run_dir = Path(request.run_dir)

    if not run_dir.exists():
        raise HTTPException(
            status_code=400,
            detail="Run directory not found"
        )

    result = parse_training_result(run_dir)

    # parse error
    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )

    save_experiment(result)

    return {
        "success": True,
        "message": "Training result saved to Supabase",
        "data": result,
    }

@app.post("/api/dataset/analyze")
def analyze_dataset(request: AnalyzeRequest):
    dataset_dir = Path(request.dataset_path)

    if not dataset_dir.exists():
        raise HTTPException(status_code=400, detail="Dataset path not found")

    output_path = REPORT_DIR / "dataset_report.json"

    report = analyze_yolo_dataset(
        dataset_dir=dataset_dir,
        output_path=output_path,
    )

    return {
        "success": True,
        "report_path": str(output_path),
        "data": report,
    }


@app.post("/api/recommendations")
def create_recommendations(request: RecommendRequest):
    dataset_report_path = (
        Path(request.dataset_report_path)
        if request.dataset_report_path
        else REPORT_DIR / "dataset_report.json"
    )

    training_result_path = (
        Path(request.training_result_path)
        if request.training_result_path
        else None
    )

    if not dataset_report_path.exists():
        raise HTTPException(status_code=400, detail="Dataset report not found")

    result = generate_recommendations(
        dataset_report_path=dataset_report_path,
        training_result_path=training_result_path,
    )

    output_path = REPORT_DIR / "recommendation_report.json"
    output_path.write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "success": True,
        "report_path": str(output_path),
        "data": result,
    }


@app.get("/api/experiments")
def get_experiments(limit: int = 20):
    return {
        "success": True,
        "data": list_experiments(limit=limit),
    }


@app.get("/api/experiments/best")
def get_best():
    return {
        "success": True,
        "data": get_best_experiment(),
    }