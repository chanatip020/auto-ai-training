import json
from datetime import datetime
from pathlib import Path

from ultralytics import YOLO


def train_yolo_model(
    dataset_dir: Path,
    model: str = "yolo11s.pt",
    epochs: int = 100,
    imgsz: int = 640,
    batch: str = "auto",
    device: str = "0",
    job_id=None,
    training_jobs=None,
):
    dataset_dir = dataset_dir.resolve()
    data_yaml = dataset_dir / "data.yaml"

    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found: {data_yaml}")

    run_name = datetime.now().strftime("train_%Y%m%d_%H%M%S")
    project_dir = Path("runs") / "training"

    yolo_model = YOLO(model)

    def update_progress(trainer):

        if not training_jobs or not job_id:
            return

        current_epoch = int(trainer.epoch) + 1
        total_epochs = int(epochs)

        progress = int((current_epoch / total_epochs) * 100)

        training_jobs[job_id]["status"] = "training"
        training_jobs[job_id]["progress"] = min(progress, 99)
        training_jobs[job_id]["current_epoch"] = current_epoch
        training_jobs[job_id]["total_epochs"] = total_epochs

        # STOP REQUEST
        if training_jobs[job_id].get("stop_requested"):

            training_jobs[job_id]["status"] = "stopped"

            trainer.stop = True

    yolo_model.add_callback("on_train_epoch_end", update_progress)

    train_result = yolo_model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=str(project_dir),
        name=run_name,
        exist_ok=False,
        optimizer="AdamW",
        patience=50,
        cos_lr=True,
        close_mosaic=20,
    )

    result_path = Path(train_result.save_dir)
    best_model_path = result_path / "weights" / "best.pt"
    last_model_path = result_path / "weights" / "last.pt"

    if training_jobs and job_id:
        training_jobs[job_id]["progress"] = 100
        training_jobs[job_id]["current_epoch"] = epochs
        training_jobs[job_id]["total_epochs"] = epochs

    summary = {
        "run_name": run_name,
        "dataset_path": str(dataset_dir),
        "model": model,
        "epochs": epochs,
        "imgsz": imgsz,
        "batch": batch,
        "device": device,
        "result_path": str(result_path),
        "best_model_path": str(best_model_path),
        "last_model_path": str(last_model_path),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    summary_path = result_path / "training_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return summary