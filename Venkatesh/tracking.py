"""MLflow experiment tracking (bonus +5).

    pip install -r requirements-dev.txt
    python train.py --mlflow
    mlflow ui --port 5001   # open http://127.0.0.1:5001, tick the runs, press Compare

One run per approach (3 ML candidates + 2 baselines) inside a parent run, all
logging the same metrics so MLflow's compare view lines them up side by side.
The selected run also stores the watch list, metrics JSON and model pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

EXPERIMENT = "TalentGuard attrition"


def log_experiment(metrics: dict[str, Any], output_dir: Path, artifact_dir: Path) -> str:
    try:
        import mlflow
    except ImportError as error:  # keep the core app free of heavy dependencies
        raise SystemExit("MLflow is not installed. Run: pip install -r requirements-dev.txt") from error

    from services import MODEL_EXCLUDED_COLUMNS, build_model_frame, candidate_models, load_dataset

    frame = build_model_frame(load_dataset())
    pipelines = candidate_models(frame)
    selected = metrics["selected_model"]
    capacity = metrics["methodology"]["capacity"]

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="talentguard-training") as parent:
        mlflow.log_params({
            "cv_folds": metrics["methodology"]["cross_validation_folds"],
            "hr_capacity": capacity,
            "selection_metric": "average_precision",
            "excluded_columns": ",".join(MODEL_EXCLUDED_COLUMNS),
            "n_features_before_encoding": frame.shape[1],
            "rows": metrics["dataset"]["records"],
            "base_rate": round(metrics["dataset"]["attrition_rate"], 4),
        })

        for score in metrics["candidate_scores"]:
            with mlflow.start_run(run_name=score["name"], nested=True):
                estimator = pipelines[score["name"]].named_steps["model"]
                params = {k: v for k, v in estimator.get_params().items() if isinstance(v, (int, float, str, bool)) or v is None}
                mlflow.log_params({"approach": "ML", **{f"model__{k}": v for k, v in params.items()}})
                mlflow.log_metrics({
                    "pr_auc": score["average_precision"],
                    "roc_auc": score["roc_auc"],
                    "precision_at_50": score["precision_at_50"],
                    "recall_at_50": score["recall_at_50"],
                    "lift_at_50": score["lift_at_50"],
                    "f1_at_capacity": score["f1_at_capacity"],
                })
                mlflow.set_tag("selected", str(score["name"] == selected))
                if score["name"] == selected:
                    mlflow.log_metrics({
                        "holdout_pr_auc": metrics["holdout"]["average_precision"],
                        "holdout_precision_at_capacity": metrics["holdout"]["precision_at_capacity"],
                        "net_savings_per_cycle": metrics["insights"]["business"]["cycle"]["net_savings"],
                    })
                    for name in ("top_50_watchlist.csv", "top_10_action_plan.csv", "model_metrics.json", "action_queue.json"):
                        path = Path(output_dir) / name
                        if path.exists():
                            mlflow.log_artifact(str(path), artifact_path="outputs")
                    model_path = Path(artifact_dir) / "talentguard_pipeline.joblib"
                    if model_path.exists():
                        mlflow.log_artifact(str(model_path), artifact_path="model")

        for baseline in metrics["insights"]["baselines"]:
            if baseline["kind"] == "ML (selected)":
                continue
            with mlflow.start_run(run_name=f"Baseline: {baseline['name']}", nested=True):
                mlflow.log_param("approach", baseline["kind"])
                mlflow.log_metrics({
                    "pr_auc": baseline["average_precision"],
                    "roc_auc": baseline["roc_auc"],
                    "precision_at_50": baseline["precision_at_50"],
                    "recall_at_50": baseline["recall_at_50"],
                    "lift_at_50": baseline["lift_at_50"],
                })
        return parent.info.run_id
