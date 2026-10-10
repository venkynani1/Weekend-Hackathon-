create extension if not exists pgcrypto;

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.organization_members (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('org_admin', 'hr_analyst', 'manager', 'auditor')),
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table if not exists public.ingestion_runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  source_type text not null,
  source_name text not null,
  status text not null check (status in ('pending', 'running', 'completed', 'failed')),
  source_cursor text,
  records_read integer not null default 0,
  records_written integer not null default 0,
  records_rejected integer not null default 0,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  error_summary text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.employee_snapshots (
  id bigint generated always as identity primary key,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  ingestion_run_id uuid references public.ingestion_runs(id) on delete set null,
  snapshot_date date not null,
  source_employee_id integer not null,
  attrition boolean not null,
  age smallint not null,
  business_travel text not null,
  daily_rate integer not null,
  department text not null,
  distance_from_home smallint not null,
  education smallint not null,
  education_field text not null,
  employee_count smallint not null,
  environment_satisfaction smallint not null,
  gender text not null,
  hourly_rate smallint not null,
  job_involvement smallint not null,
  job_level smallint not null,
  job_role text not null,
  job_satisfaction smallint not null,
  marital_status text not null,
  monthly_income integer not null,
  monthly_rate integer not null,
  num_companies_worked smallint not null,
  over_18 text not null,
  over_time boolean not null,
  percent_salary_hike smallint not null,
  performance_rating smallint not null,
  relationship_satisfaction smallint not null,
  standard_hours smallint not null,
  stock_option_level smallint not null,
  total_working_years smallint not null,
  training_times_last_year smallint not null,
  work_life_balance smallint not null,
  years_at_company smallint not null,
  years_in_current_role smallint not null,
  years_since_last_promotion smallint not null,
  years_with_current_manager smallint not null,
  source_payload jsonb,
  created_at timestamptz not null default now(),
  unique (organization_id, source_employee_id, snapshot_date)
);

create index if not exists employee_snapshots_org_date_idx
  on public.employee_snapshots (organization_id, snapshot_date desc);
create index if not exists employee_snapshots_org_attrition_idx
  on public.employee_snapshots (organization_id, attrition);
create index if not exists employee_snapshots_org_role_idx
  on public.employee_snapshots (organization_id, job_role);
create index if not exists ingestion_runs_org_started_idx
  on public.ingestion_runs (organization_id, started_at desc);

create or replace function public.is_organization_member(target_organization_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members
    where organization_id = target_organization_id
      and user_id = auth.uid()
  );
$$;

revoke all on function public.is_organization_member(uuid) from public;
grant execute on function public.is_organization_member(uuid) to authenticated;

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.ingestion_runs enable row level security;
alter table public.employee_snapshots enable row level security;

drop policy if exists "members can read their organizations" on public.organizations;
create policy "members can read their organizations"
  on public.organizations for select to authenticated
  using (public.is_organization_member(id));

drop policy if exists "members can read memberships" on public.organization_members;
create policy "members can read memberships"
  on public.organization_members for select to authenticated
  using (public.is_organization_member(organization_id));

drop policy if exists "members can read ingestion runs" on public.ingestion_runs;
create policy "members can read ingestion runs"
  on public.ingestion_runs for select to authenticated
  using (public.is_organization_member(organization_id));

drop policy if exists "members can read employee snapshots" on public.employee_snapshots;
create policy "members can read employee snapshots"
  on public.employee_snapshots for select to authenticated
  using (public.is_organization_member(organization_id));

insert into public.organizations (name, slug)
values ('TalentGuard Demo', 'talentguard-demo')
on conflict (slug) do update set name = excluded.name;

comment on table public.employee_snapshots is
  'Point-in-time employee records. Initial rows come from the synthetic IBM HR attrition dataset.';
