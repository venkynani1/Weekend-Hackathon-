export type RiskBand = "Priority" | "High" | "Elevated";

export interface EmployeeRisk {
  Rank: number;
  EmployeeNumber: number;
  RiskScore: number;
  RiskBand: RiskBand;
  Department: string;
  JobRole: string;
  YearsAtCompany: number;
  YearsInCurrentRole: number;
  OverTime: string;
  JobSatisfaction: number;
  WorkLifeBalance: number;
  MonthlyIncome: number;
  HistoricalOutcome: "Yes" | "No";
  RiskReason1: string;
  RiskReason2: string;
  RiskReason3: string;
  ReasonFeatures: string;
  PrimaryAction: string;
  Recommendation: string;
}

export interface ModelScore {
  name: string;
  average_precision: number;
  roc_auc: number;
  f1_at_capacity: number;
  recall_at_capacity: number;
  precision_at_50: number;
  recall_at_50: number;
  lift_at_50: number;
  capacity_threshold: number;
}

export interface DashboardMetrics {
  dataset: {
    records: number;
    columns: number;
    attrition_count: number;
    attrition_rate: number;
    all_no_accuracy: number;
    missing_cells: number;
  };
  selected_model: string;
  selection_metric: string;
  selected_model_score: ModelScore;
  candidate_scores: ModelScore[];
  holdout: {
    test_records: number;
    capacity: number;
    average_precision: number;
    roc_auc: number;
    precision_at_capacity: number;
    recall_at_capacity: number;
    lift_at_capacity: number;
    confusion_matrix: number[][];
  };
  department_summary: Array<{
    department: string;
    employees: number;
    historical_attrition_rate: number;
    average_risk: number;
    watchlist_count: number;
  }>;
  driver_summary: Array<{ feature: string; label: string; count: number }>;
  historical_eda: {
    overtime_yes_rate: number;
    overtime_no_rate: number;
    sales_representative_rate: number;
    frequent_travel_rate: number;
    rare_travel_rate: number;
    low_satisfaction_rate: number;
    high_satisfaction_rate: number;
    attrited_income_median: number;
    retained_income_median: number;
    attrited_tenure_median: number;
    retained_tenure_median: number;
    attrited_age_median: number;
    retained_age_median: number;
  };
  methodology: {
    cross_validation_folds: number;
    capacity: number;
    priority_capacity: number;
    excluded_columns: string[];
    explanation_method: string;
    scope: string;
  };
  fairness_report?: FairnessReport;
  calibration_report?: CalibrationReport;
  model_version?: {
    id: string;
    version: string;
    trained_at: string;
    scoring_run_id: string;
    snapshot_date: string;
  };
}

export interface DashboardPayload {
  watchlist: EmployeeRisk[];
  top_ten: EmployeeRisk[];
  metrics: DashboardMetrics;
  departments: string[];
  source?: "local" | "supabase";
}

export interface CalibrationReport {
  brier_score?: number;
  bins?: Array<{ predicted: number; observed: number; count: number }>;
  status?: string;
}

export interface FairnessGroup {
  group: string;
  records: number;
  selection_rate: number;
  observed_attrition_rate: number;
  true_positive_rate: number | null;
  average_risk: number;
}

export interface FairnessReport {
  status?: string;
  note?: string;
  attributes?: Record<string, FairnessGroup[]>;
}

export type InterventionStatus = "not_reviewed" | "reviewed" | "intervention_planned" | "follow_up_scheduled" | "closed";

export interface InterventionCase {
  id: string;
  organization_id: string;
  source_employee_id: number;
  status: InterventionStatus;
  intervention_type: string | null;
  notes: string | null;
  assigned_to_name: string | null;
  follow_up_at: string | null;
  outcome: string | null;
  created_at: string;
  updated_at: string;
}

export interface InterventionEvent {
  id: number;
  event_type: "created" | "updated";
  from_status: InterventionStatus | null;
  to_status: InterventionStatus;
  notes: string | null;
  created_at: string;
}

export interface InterventionResponse {
  case: InterventionCase | null;
  events: InterventionEvent[];
}

export interface InterventionPayload {
  source_employee_id: number;
  status: InterventionStatus;
  intervention_type?: string | null;
  notes?: string | null;
  assigned_to_name?: string | null;
  follow_up_at?: string | null;
  outcome?: string | null;
}

export interface IngestionRun {
  id: string;
  source_type: string;
  source_name: string;
  status: "pending" | "running" | "completed" | "failed";
  source_cursor: string | null;
  records_read: number;
  records_written: number;
  records_rejected: number;
  started_at: string;
  completed_at: string | null;
  error_summary: string | null;
  metadata: Record<string, unknown>;
}
