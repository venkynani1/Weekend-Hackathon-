"""Optional local MLflow tracking for hackathon experiment comparison."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def log_experiment(
    metrics: dict[str, Any],
    output_dir: Path,
    artifact_dir: Path,
    experiment_name: str,
) -> str:
    try:
        import mlflow
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "MLflow is not installed. Run `python -m pip install -r requirements-mlflow.txt`."
        ) from error

    if not os.environ.get("MLFLOW_TRACKING_URI"):
        database = (Path.cwd() / "mlflow.db").resolve().as_posix()
        mlflow.set_tracking_uri(f"sqlite:///{database}")
    mlflow.set_experiment(experiment_name)

    selected = metrics["selected_model_score"]
    with mlflow.start_run(run_name="TalentGuard model selection") as parent:
        mlflow.log_params(
            {
                "records": metrics["dataset"]["records"],
                "source_columns": metrics["dataset"]["columns"],
                "cross_validation_folds": metrics["methodology"]["cross_validation_folds"],
                "review_capacity": metrics["methodology"]["capacity"],
                "selection_metric": metrics["selection_metric"],
                "selected_model": metrics["selected_model"],
            }
        )
        mlflow.log_metrics(
            {
                "average_precision": selected["average_precision"],
                "roc_auc": selected["roc_auc"],
                "precision_at_50": selected["precision_at_50"],
                "recall_at_50": selected["recall_at_50"],
                "lift_at_50": selected["lift_at_50"],
                "brier_score": metrics["calibration_report"]["brier_score"],
            }
        )
        mlflow.log_dict(metrics, "reports/model_metrics.json")
        for candidate in metrics["candidate_scores"]:
            with mlflow.start_run(run_name=candidate["name"], nested=True):
                mlflow.log_param("model", candidate["name"])
                mlflow.log_metrics(
                    {
                        "average_precision": candidate["average_precision"],
                        "roc_auc": candidate["roc_auc"],
                        "f1_at_capacity": candidate["f1_at_capacity"],
                        "precision_at_50": candidate["precision_at_50"],
                        "recall_at_50": candidate["recall_at_50"],
                        "lift_at_50": candidate["lift_at_50"],
                    }
                )
        if output_dir.exists():
            mlflow.log_artifacts(str(output_dir), artifact_path="actionable_outputs")
        if artifact_dir.exists():
            mlflow.log_artifacts(str(artifact_dir), artifact_path="model_artifacts")
        return parent.info.run_id
