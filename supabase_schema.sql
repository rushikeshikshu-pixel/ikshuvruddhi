create table if not exists public.plot_predictions (
  plot_no bigint primary key,
  gat_no text,
  village text,
  farmer text,
  cane_type text,
  variety_name text,
  plantation_date date,
  satellite_status text,
  satellite_acquisition_date date,
  satellite_ndvi numeric,
  satellite_ndre numeric,
  registered_area_ha numeric,
  detected_cane_area_ha numeric,
  predicted_pol numeric,
  predicted_brix numeric,
  predicted_ccs numeric,
  predicted_tonnage_mt numeric,
  updated_at timestamptz default now()
);

create table if not exists public.lab_samples (
  plot_no bigint primary key references public.plot_predictions(plot_no),
  sample_date date,
  actual_pol numeric,
  actual_brix numeric,
  actual_ccs numeric,
  collector text,
  notes text,
  updated_at timestamptz default now()
);

-- Multi-date satellite history and crop screening. Store plot IDs, not farmer names.
create table if not exists public.crop_observations (
  plot_id text not null,
  gat_no text,
  observation_date date not null,
  ndvi numeric not null,
  ndre numeric,
  lswi numeric,
  usability_pct numeric,
  sar_vh_db numeric,
  source text not null default 'sentinel-2',
  updated_at timestamptz not null default now(),
  primary key (plot_id, observation_date)
);

create table if not exists public.crop_screenings (
  plot_id text primary key,
  gat_no text,
  predicted_crop text not null,
  heuristic_score_pct numeric,
  evidence_completeness_pct numeric,
  reasoning jsonb,
  phenology_summary jsonb,
  model_version text not null default 'phenology-heuristic-v1',
  screened_at timestamptz not null default now()
);

alter table public.plot_predictions enable row level security;
alter table public.lab_samples enable row level security;
alter table public.crop_observations enable row level security;
alter table public.crop_screenings enable row level security;
