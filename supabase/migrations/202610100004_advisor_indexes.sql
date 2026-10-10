create index if not exists model_versions_created_by_idx
  on public.model_versions (created_by);
create index if not exists intervention_cases_created_by_idx
  on public.intervention_cases (created_by);
create index if not exists intervention_cases_updated_by_idx
  on public.intervention_cases (updated_by);
