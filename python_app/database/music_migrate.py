from __future__ import annotations

import re

from ..utils.music_common import connect_db
from .persistence import DbCfg


MIGRATION_SQL = """
create table if not exists songs (
  id serial primary key,
  song_uid text,
  title text,
  lyrics_raw text,
  lyrics_polished text,
  album text,
  song_description text,
  song_structure text,
  language text,
  creativity int,
  batch_id text,
  batch_index int,
  status text,
  created_at timestamp default now()
);

alter table songs add column if not exists song_uid text;
alter table songs add column if not exists language text;
alter table songs add column if not exists creativity int;
alter table songs add column if not exists batch_id text;
alter table songs add column if not exists batch_index int;
alter table songs add column if not exists run_date date;
alter table songs add column if not exists profile_ok_id text;
alter table songs add column if not exists profile_alt_id text;
create unique index if not exists ux_songs_song_uid on songs(song_uid);
create index if not exists idx_songs_created_at on songs(created_at desc);
create index if not exists idx_songs_run_date on songs(run_date desc);
create index if not exists idx_songs_batch_id on songs(batch_id);

alter table songs add column if not exists hidden boolean not null default false;
create index if not exists idx_songs_hidden on songs(hidden);

alter table songs add column if not exists song_description text;
alter table songs add column if not exists song_structure text;

create table if not exists history (
  id serial primary key,
  kind text,
  song_uid text,
  message text,
  created_at timestamp default now()
);

create index if not exists idx_history_created_at on history(created_at desc);

create table if not exists images (
  id serial primary key,
  song_id int,
  type text,
  path text,
  created_at timestamp default now()
);

create table if not exists car_models (
  id serial primary key,
  uid text,
  make text,
  model text,
  trim text,
  year int,
  category text,
  updated_at timestamp default now()
);

alter table car_models add column if not exists uid text;
alter table car_models add column if not exists updated_at timestamp default now();
create unique index if not exists ux_car_models_uid on car_models(uid);

create table if not exists image_samples (
  id serial primary key,
  file_path text,
  tags text[],
  created_at timestamp default now()
);

create table if not exists prompt_templates (
  id serial primary key,
  uid text,
  name text,
  content text,
  tags text[],
  scene text,
  negative_prompt text,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table prompt_templates add column if not exists uid text;
alter table prompt_templates add column if not exists updated_at timestamp default now();
alter table prompt_templates add column if not exists scene text;
alter table prompt_templates add column if not exists negative_prompt text;
update prompt_templates set scene = content where (scene is null or scene = '') and (content is not null and content <> '');
update prompt_templates set negative_prompt = content where (negative_prompt is null or negative_prompt = '') and (content is not null and content <> '') and (tags is not null) and array_position(tags, 'negative') is not null;
update prompt_templates set scene = '' where (tags is not null) and array_position(tags, 'negative') is not null;
create unique index if not exists ux_prompt_templates_uid on prompt_templates(uid);

create table if not exists text_styles (
  id serial primary key,
  uid text,
  name text,
  title text,
  subtitle text,
  subtitle2 text,
  prompt text,
  opacity float,
  position text,
  updated_at timestamp default now()
);

alter table text_styles add column if not exists uid text;
alter table text_styles add column if not exists subtitle2 text;
alter table text_styles add column if not exists prompt text;
alter table text_styles add column if not exists preset_id text;
alter table text_styles add column if not exists palette_id text;
alter table text_styles add column if not exists updated_at timestamp default now();
create unique index if not exists ux_text_styles_uid on text_styles(uid);

create table if not exists song_structures (
  id serial primary key,
  uid text,
  name text,
  content text,
  match_key text,
  updated_at timestamp default now()
);

alter table song_structures add column if not exists uid text;
alter table song_structures add column if not exists match_key text;
create unique index if not exists ux_song_structures_uid on song_structures(uid);

create table if not exists song_descriptions (
  id serial primary key,
  uid text,
  name text,
  content text,
  match_key text,
  updated_at timestamp default now()
);

alter table song_descriptions add column if not exists uid text;
alter table song_descriptions add column if not exists match_key text;
create unique index if not exists ux_song_descriptions_uid on song_descriptions(uid);

create table if not exists automation_logs (
  id serial primary key,
  song_id int,
  status text,
  message text,
  created_at timestamp default now()
);

create table if not exists opening_pairs (
  id serial primary key,
  line1 text,
  line2 text,
  norm text,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_opening_pairs_norm on opening_pairs(norm);
create index if not exists idx_opening_pairs_used on opening_pairs(used_count, id);

create table if not exists title_pool (
  id serial primary key,
  title text,
  norm text,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_title_pool_norm on title_pool(norm);
create index if not exists idx_title_pool_used on title_pool(used_count, id);

create table if not exists album_pool (
  id serial primary key,
  album text,
  norm text,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_album_pool_norm on album_pool(norm);
create index if not exists idx_album_pool_used on album_pool(used_count, id);

create table if not exists app_settings (
  key text primary key,
  value text not null,
  updated_at timestamp default now()
);

alter table app_settings add column if not exists updated_at timestamp default now();

create table if not exists app_json (
  key text primary key,
  value jsonb not null,
  updated_at timestamp default now()
);

alter table app_json add column if not exists updated_at timestamp default now();

create table if not exists profiles (
  uid text primary key,
  name text not null,
  folder_name text not null,
  run_prefix text not null default '',
  logo_path text not null default '',
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table profiles add column if not exists uid text;
alter table profiles add column if not exists folder_name text;
alter table profiles add column if not exists run_prefix text not null default '';
alter table profiles add column if not exists logo_path text not null default '';
alter table profiles add column if not exists video_template_id text not null default '';
alter table profiles add column if not exists youtube_visibility_mode text not null default 'unlisted';
alter table profiles add column if not exists youtube_publish_at timestamp;
alter table profiles add column if not exists youtube_publish_time text not null default '';
alter table profiles add column if not exists youtube_category_id text not null default '';
alter table profiles add column if not exists youtube_playlist_id text not null default '';
alter table profiles add column if not exists youtube_tags text not null default '';
alter table profiles add column if not exists youtube_title_template text not null default '';
alter table profiles add column if not exists youtube_description_template text not null default '';
alter table profiles add column if not exists youtube_made_for_kids boolean not null default false;
alter table profiles add column if not exists youtube_contains_synthetic_media boolean not null default false;
alter table profiles add column if not exists youtube_oauth_app_id text not null default '';
alter table profiles add column if not exists image_config jsonb not null default '{}'::jsonb;
alter table profiles add column if not exists output_resolution text not null default '';
alter table profiles add column if not exists updated_at timestamp default now();
create unique index if not exists ux_profiles_uid on profiles(uid);
create index if not exists idx_profiles_video_template_id on profiles(video_template_id);
create index if not exists idx_profiles_youtube_visibility_mode on profiles(youtube_visibility_mode);

create table if not exists video_templates (
  uid text primary key,
  name text not null,
  source text not null default 'user',
  template jsonb not null,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table video_templates add column if not exists uid text;
alter table video_templates add column if not exists source text not null default 'user';
alter table video_templates add column if not exists updated_at timestamp default now();
create unique index if not exists ux_video_templates_uid on video_templates(uid);

create table if not exists youtube_accounts (
  id text primary key,
  profile_id text not null,
  channel_id text not null default '',
  channel_title text not null default '',
  refresh_token_enc text not null default '',
  scopes text not null default '',
  created_at timestamp default now(),
  updated_at timestamp default now()
);

create unique index if not exists ux_youtube_accounts_profile_id on youtube_accounts(profile_id);
create index if not exists idx_youtube_accounts_channel_id on youtube_accounts(channel_id);

create table if not exists youtube_oauth_apps (
  id text primary key,
  name text not null,
  client_id text not null,
  client_secret_enc text not null default '',
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table youtube_oauth_apps add column if not exists updated_at timestamp default now();
create unique index if not exists ux_youtube_oauth_apps_id on youtube_oauth_apps(id);
create unique index if not exists ux_youtube_oauth_apps_name on youtube_oauth_apps(name);

create table if not exists youtube_upload_jobs (
  id serial primary key,
  job_uid text not null,
  batch_id text,
  profile_id text,
  role text,
  file_path text,
  status text,
  attempt_count int not null default 0,
  error text,
  youtube_video_id text,
  youtube_url text,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table youtube_upload_jobs add column if not exists updated_at timestamp default now();
create unique index if not exists ux_youtube_upload_jobs_uid on youtube_upload_jobs(job_uid);
create index if not exists idx_youtube_upload_jobs_status on youtube_upload_jobs(status, updated_at desc);
create index if not exists idx_youtube_upload_jobs_profile on youtube_upload_jobs(profile_id);

create table if not exists suno_tasks (
  id serial primary key,
  request_hash text,
  song_uid text,
  batch_id text,
  track_no int,
  model text,
  title text,
  style text,
  instrumental boolean,
  task_id text,
  status text,
  audio_url_ok text,
  audio_url_alt text,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

create unique index if not exists ux_suno_tasks_request_hash on suno_tasks(request_hash);
create index if not exists idx_suno_tasks_song_uid on suno_tasks(song_uid);
create index if not exists idx_suno_tasks_task_id on suno_tasks(task_id);
create index if not exists idx_suno_tasks_batch_updated on suno_tasks(batch_id, updated_at desc, id desc);
alter table suno_tasks add column if not exists request_hash text;
alter table suno_tasks add column if not exists song_uid text;
alter table suno_tasks add column if not exists batch_id text;
alter table suno_tasks add column if not exists track_no int;
alter table suno_tasks add column if not exists model text;
alter table suno_tasks add column if not exists title text;
alter table suno_tasks add column if not exists style text;
alter table suno_tasks add column if not exists instrumental boolean;
alter table suno_tasks add column if not exists task_id text;
alter table suno_tasks add column if not exists status text;
alter table suno_tasks add column if not exists audio_url_ok text;
alter table suno_tasks add column if not exists audio_url_alt text;
alter table suno_tasks add column if not exists output_dir text;
alter table suno_tasks add column if not exists output_dir_ok text;
alter table suno_tasks add column if not exists output_dir_alt text;
alter table suno_tasks add column if not exists downloaded_ok boolean not null default false;
alter table suno_tasks add column if not exists downloaded_alt boolean not null default false;
alter table suno_tasks add column if not exists updated_at timestamp default now();
create unique index if not exists ux_suno_tasks_request_hash on suno_tasks(request_hash);
create index if not exists idx_suno_tasks_song_uid on suno_tasks(song_uid);
create index if not exists idx_suno_tasks_task_id on suno_tasks(task_id);

alter table opening_pairs add column if not exists norm text;
alter table opening_pairs add column if not exists used_count int not null default 0;
alter table title_pool add column if not exists norm text;
alter table title_pool add column if not exists used_count int not null default 0;
alter table album_pool add column if not exists norm text;
alter table album_pool add column if not exists used_count int not null default 0;

create unique index if not exists ux_opening_pairs_norm on opening_pairs(norm);
create unique index if not exists ux_title_pool_norm on title_pool(norm);
create unique index if not exists ux_album_pool_norm on album_pool(norm);

create table if not exists batch_run_dirs (
  batch_id text primary key,
  ok_dir text not null,
  alt_dir text not null,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table batch_run_dirs add column if not exists batch_id text;
alter table batch_run_dirs add column if not exists ok_dir text;
alter table batch_run_dirs add column if not exists alt_dir text;
alter table batch_run_dirs add column if not exists updated_at timestamp default now();

create table if not exists image_jobs (
  id serial primary key,
  job_uid text,
  batch_id text not null,
  run_date date,
  pair_index int not null default 0,
  profile_id text not null,
  channel_role text not null default '',
  kind text not null,
  status text not null,
  prompt text not null default '',
  prompt_source text not null default '',
  sample_paths jsonb not null default '[]'::jsonb,
  input_image_path text not null default '',
  output_image_path text not null default '',
  error text not null default '',
  attempt_count int not null default 0,
  created_at timestamp default now(),
  updated_at timestamp default now()
);

alter table image_jobs add column if not exists job_uid text;
alter table image_jobs add column if not exists run_date date;
alter table image_jobs add column if not exists pair_index int not null default 0;
alter table image_jobs add column if not exists profile_id text;
alter table image_jobs add column if not exists channel_role text not null default '';
alter table image_jobs add column if not exists prompt text not null default '';
alter table image_jobs add column if not exists prompt_source text not null default '';
alter table image_jobs add column if not exists sample_paths jsonb not null default '[]'::jsonb;
alter table image_jobs add column if not exists input_image_path text not null default '';
alter table image_jobs add column if not exists output_image_path text not null default '';
alter table image_jobs add column if not exists error text not null default '';
alter table image_jobs add column if not exists attempt_count int not null default 0;
alter table image_jobs add column if not exists updated_at timestamp default now();

create unique index if not exists ux_image_jobs_job_uid on image_jobs(job_uid);
create unique index if not exists ux_image_jobs_key on image_jobs(batch_id, profile_id, kind);
create index if not exists idx_image_jobs_status on image_jobs(status, updated_at);
create index if not exists idx_image_jobs_run_date on image_jobs(run_date desc);
create index if not exists idx_image_jobs_batch_id on image_jobs(batch_id);

create table if not exists image_prompt_presets (
  id serial primary key,
  kind text not null default 'background',
  name text not null,
  prompt text not null,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now()
);

create unique index if not exists ux_image_prompt_presets_kind_name on image_prompt_presets(kind, name);
create index if not exists idx_image_prompt_presets_used on image_prompt_presets(kind, used_count, id);

insert into image_prompt_presets(kind, name, prompt) values
  ('background', 'Cinematic Cover', 'cinematic lighting, high contrast, moody atmosphere, ultra detailed, sharp focus'),
  ('background', 'Neon Club', 'neon lights, nightclub vibe, vibrant colors, glow, high detail'),
  ('background', 'Retro Poster', 'retro poster style, bold shapes, grain, high contrast, graphic design'),
  ('thumbnail', 'Bold Title', 'bold readable typography style, centered title, strong contrast, clean layout'),
  ('thumbnail', 'Glow Text', 'glow typography style, neon text, high contrast, clean safe margins'),
  ('thumbnail', 'Minimal Clean', 'minimal typography style, lots of negative space, clean modern layout')
on conflict do nothing;

create table if not exists image_random_history (
  kind text not null,
  value text not null,
  used_count int not null default 0,
  used_at timestamp,
  created_at timestamp default now(),
  primary key (kind, value)
);

create table if not exists text_style_presets (
  id              serial primary key,
  name            text not null unique,
  font_path       text not null default '',
  font_size       integer not null default 72,
  primary_color   text not null default '#FFFFFFFF',
  position        text not null default 'center',

  glow_color      text not null default '#00000000',
  glow_radius     integer not null default 0,
  shadow_offset_x integer not null default 0,
  shadow_offset_y integer not null default 0,
  shadow_color    text not null default '#00000080',
  stroke_width    integer not null default 0,
  stroke_color    text not null default '#000000FF',

  gradient_enabled boolean not null default false,
  gradient_start_color text not null default '#FFFFFFFF',
  gradient_end_color   text not null default '#000000FF',

  line_spacing        real not null default 1.4,
  alignment           text not null default 'center',
  max_text_width_pct  integer not null default 80,
  vertical_padding_pct integer not null default 10,

  used_count      integer not null default 0,
  used_at         timestamp,

  created_at      timestamp not null default now(),
  updated_at      timestamp not null default now()
);

insert into text_style_presets(
  name, font_size, primary_color, position,
  glow_color, glow_radius,
  stroke_width, stroke_color,
  gradient_enabled, gradient_start_color, gradient_end_color
) values
(
  'Neon Glow', 72, '#00FFFFFF', 'bottom',
  '#00FFFFFF', 15,
  0, '#000000FF',
  false, '#FFFFFFFF', '#000000FF'
),
(
  'Bold Modern', 96, '#FFFFFFFF', 'center',
  '#00000000', 0,
  3, '#000000FF',
  false, '#FFFFFFFF', '#000000FF'
),
(
  'Streetwear', 84, '#FFFFFFFF', 'bottom',
  '#00000000', 0,
  0, '#000000FF',
  true, '#FF6B35FF', '#F7C948FF'
)
on conflict (name) do nothing;

alter table video_templates add column if not exists kind text not null default 'video';
create index if not exists idx_video_templates_kind on video_templates(kind);

alter table profiles add column if not exists reel_template_id text not null default '';
"""


def _assert_safe_db_name(name: str) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9_]+", str(name or "").strip()):
        raise ValueError("Database name must be alphanumeric/underscore")


def test_db_connection(cfg: DbCfg) -> dict:
    conn = None
    try:
        conn = connect_db(cfg)
        return {"ok": True, "message": "Connection successful"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        if conn is not None:
            conn.close()


def ensure_database_and_migrate(cfg: DbCfg) -> dict:
    _assert_safe_db_name(cfg.database)
    conn = None
    try:
        try:
            conn = connect_db(cfg)
        except Exception as exc:
            code = getattr(exc, "pgcode", None)
            message = str(exc)
            if str(code) != "3D000" and 'does not exist' not in message.lower():
                return {"ok": False, "message": message}
            admin_db = "template1" if str(cfg.database).strip().lower() == "postgres" else "postgres"
            admin = None
            try:
                admin = connect_db(cfg, database=admin_db, autocommit=True)
                db_name = str(cfg.database).replace('"', '""')
                with admin.cursor() as cur:
                    cur.execute(f'create database "{db_name}"')
            except Exception as exc2:
                return {"ok": False, "message": str(exc2)}
            finally:
                if admin is not None:
                    admin.close()
            conn = connect_db(cfg)

        assert conn is not None
        with conn:
            with conn.cursor() as cur:
                cur.execute(MIGRATION_SQL)
        return {"ok": True, "message": "Migrations applied"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        if conn is not None:
            conn.close()
