create schema if not exists private;

revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.is_organization_member(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select (select auth.uid()) is not null
    and exists (
      select 1
      from public.organization_members
      where organization_id = target_organization_id
        and user_id = (select auth.uid())
    );
$$;

revoke all on function private.is_organization_member(uuid) from public;
grant execute on function private.is_organization_member(uuid) to authenticated;

drop policy if exists "members can read their organizations" on public.organizations;
create policy "members can read their organizations"
  on public.organizations for select to authenticated
  using ((select private.is_organization_member(id)));

drop policy if exists "members can read memberships" on public.organization_members;
create policy "members can read memberships"
  on public.organization_members for select to authenticated
  using ((select private.is_organization_member(organization_id)));

drop policy if exists "members can read ingestion runs" on public.ingestion_runs;
create policy "members can read ingestion runs"
  on public.ingestion_runs for select to authenticated
  using ((select private.is_organization_member(organization_id)));

drop policy if exists "members can read employee snapshots" on public.employee_snapshots;
create policy "members can read employee snapshots"
  on public.employee_snapshots for select to authenticated
  using ((select private.is_organization_member(organization_id)));

drop function if exists public.is_organization_member(uuid);

create index if not exists employee_snapshots_ingestion_run_idx
  on public.employee_snapshots (ingestion_run_id);
create index if not exists organization_members_user_idx
  on public.organization_members (user_id);

create table if not exists public.model_versions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null,
  version text not null,
  status text not null default 'approved'
    check (status in ('draft', 'approved', 'retired')),
  trained_at timestamptz not null,
  training_data_start date,
  training_data_end date,
  metrics jsonb not null default '{}'::jsonb,
  methodology jsonb not null default '{}'::jsonb,
  fairness_report jsonb not null default '{}'::jsonb,
  calibration_report jsonb not null default '{}'::jsonb,
  artifact_uri text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (organization_id, name, version)
);

create table if not exists public.scoring_runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  model_version_id uuid not null references public.model_versions(id) on delete restrict,
  ingestion_run_id uuid references public.ingestion_runs(id) on delete set null,
  snapshot_date date not null,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'failed')),
  records_scored integer not null default 0 check (records_scored >= 0),
  capacity integer not null default 50 check (capacity > 0),
  threshold numeric,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  error_summary text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.risk_scores (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  scoring_run_id uuid not null references public.scoring_runs(id) on delete cascade,
  employee_snapshot_id bigint not null references public.employee_snapshots(id) on delete cascade,
  source_employee_id integer not null,
  risk_probability numeric not null check (risk_probability >= 0 and risk_probability <= 1),
  risk_rank integer not null check (risk_rank > 0),
  risk_band text not null check (risk_band in ('Priority', 'High', 'Elevated', 'Monitored')),
  explanations jsonb not null default '[]'::jsonb
    check (jsonb_typeof(explanations) = 'array'),
  reason_features text[] not null default '{}',
  primary_action text,
  recommendation text,
  historical_outcome boolean,
  created_at timestamptz not null default now(),
  unique (scoring_run_id, source_employee_id),
  unique (scoring_run_id, risk_rank)
);

create table if not exists public.intervention_cases (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  source_employee_id integer not null,
  employee_snapshot_id bigint references public.employee_snapshots(id) on delete set null,
  scoring_run_id uuid references public.scoring_runs(id) on delete set null,
  status text not null default 'not_reviewed'
    check (status in ('not_reviewed', 'reviewed', 'intervention_planned', 'follow_up_scheduled', 'closed')),
  intervention_type text,
  notes text,
  assigned_to uuid references auth.users(id) on delete set null,
  assigned_to_name text,
  follow_up_at timestamptz,
  outcome text,
  created_by uuid not null references auth.users(id) on delete restrict,
  updated_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, source_employee_id)
);

create table if not exists public.intervention_events (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  intervention_case_id uuid not null references public.intervention_cases(id) on delete cascade,
  event_type text not null check (event_type in ('created', 'updated')),
  from_status text,
  to_status text not null,
  notes text,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists model_versions_org_created_idx
  on public.model_versions (organization_id, created_at desc);
create index if not exists scoring_runs_org_completed_idx
  on public.scoring_runs (organization_id, completed_at desc);
create index if not exists scoring_runs_model_version_idx
  on public.scoring_runs (model_version_id);
create index if not exists scoring_runs_ingestion_run_idx
  on public.scoring_runs (ingestion_run_id);
create index if not exists risk_scores_run_rank_idx
  on public.risk_scores (scoring_run_id, risk_rank);
create index if not exists risk_scores_org_employee_idx
  on public.risk_scores (organization_id, source_employee_id);
create index if not exists risk_scores_employee_snapshot_idx
  on public.risk_scores (employee_snapshot_id);
create index if not exists intervention_cases_org_status_idx
  on public.intervention_cases (organization_id, status, updated_at desc);
create index if not exists intervention_cases_employee_snapshot_idx
  on public.intervention_cases (employee_snapshot_id);
create index if not exists intervention_cases_scoring_run_idx
  on public.intervention_cases (scoring_run_id);
create index if not exists intervention_cases_assigned_to_idx
  on public.intervention_cases (assigned_to);
create index if not exists intervention_events_case_created_idx
  on public.intervention_events (intervention_case_id, created_at desc);
create index if not exists intervention_events_org_created_idx
  on public.intervention_events (organization_id, created_at desc);
create index if not exists intervention_events_actor_idx
  on public.intervention_events (actor_user_id);

create or replace function private.prepare_intervention_case_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.organization_id is distinct from old.organization_id
     or new.source_employee_id is distinct from old.source_employee_id
     or new.created_by is distinct from old.created_by
     or new.created_at is distinct from old.created_at then
    raise exception 'Intervention case identity fields cannot be changed';
  end if;

  new.updated_by := (select auth.uid());
  new.updated_at := now();
  return new;
end;
$$;

create or replace function private.record_intervention_event()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.intervention_events (
    organization_id,
    intervention_case_id,
    event_type,
    from_status,
    to_status,
    notes,
    actor_user_id,
    event_payload
  ) values (
    new.organization_id,
    new.id,
    case when tg_op = 'INSERT' then 'created' else 'updated' end,
    case when tg_op = 'UPDATE' then old.status else null end,
    new.status,
    new.notes,
    coalesce((select auth.uid()), new.updated_by, new.created_by),
    jsonb_build_object(
      'intervention_type', new.intervention_type,
      'assigned_to_name', new.assigned_to_name,
      'follow_up_at', new.follow_up_at,
      'outcome', new.outcome
    )
  );
  return new;
end;
$$;

revoke all on function private.prepare_intervention_case_update() from public;
revoke all on function private.record_intervention_event() from public;

drop trigger if exists prepare_intervention_case_update on public.intervention_cases;
create trigger prepare_intervention_case_update
before update on public.intervention_cases
for each row execute function private.prepare_intervention_case_update();

drop trigger if exists record_intervention_event on public.intervention_cases;
create trigger record_intervention_event
after insert or update on public.intervention_cases
for each row execute function private.record_intervention_event();

alter table public.model_versions enable row level security;
alter table public.scoring_runs enable row level security;
alter table public.risk_scores enable row level security;
alter table public.intervention_cases enable row level security;
alter table public.intervention_events enable row level security;

create policy "members can read model versions"
  on public.model_versions for select to authenticated
  using ((select private.is_organization_member(organization_id)));

create policy "members can read scoring runs"
  on public.scoring_runs for select to authenticated
  using ((select private.is_organization_member(organization_id)));

create policy "members can read risk scores"
  on public.risk_scores for select to authenticated
  using ((select private.is_organization_member(organization_id)));

create policy "members can read intervention cases"
  on public.intervention_cases for select to authenticated
  using ((select private.is_organization_member(organization_id)));

create policy "members can create intervention cases"
  on public.intervention_cases for insert to authenticated
  with check (
    (select private.is_organization_member(organization_id))
    and created_by = (select auth.uid())
    and updated_by = (select auth.uid())
  );

create policy "members can update intervention cases"
  on public.intervention_cases for update to authenticated
  using ((select private.is_organization_member(organization_id)))
  with check ((select private.is_organization_member(organization_id)));

create policy "members can read intervention events"
  on public.intervention_events for select to authenticated
  using ((select private.is_organization_member(organization_id)));

revoke all on table public.organizations from anon;
revoke all on table public.organization_members from anon;
revoke all on table public.ingestion_runs from anon;
revoke all on table public.employee_snapshots from anon;
revoke all on table public.model_versions from anon;
revoke all on table public.scoring_runs from anon;
revoke all on table public.risk_scores from anon;
revoke all on table public.intervention_cases from anon;
revoke all on table public.intervention_events from anon;

grant select on table public.organizations to authenticated;
grant select on table public.organization_members to authenticated;
grant select on table public.ingestion_runs to authenticated;
grant select on table public.employee_snapshots to authenticated;
grant select on table public.model_versions to authenticated;
grant select on table public.scoring_runs to authenticated;
grant select on table public.risk_scores to authenticated;
grant select, insert, update on table public.intervention_cases to authenticated;
grant select on table public.intervention_events to authenticated;

comment on table public.risk_scores is
  'Immutable employee risk rankings produced by a completed scoring run.';
comment on table public.intervention_cases is
  'Human-owned retention interventions. Risk scores never automate employment actions.';
