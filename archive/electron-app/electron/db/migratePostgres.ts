import * as pg from "pg";

const MIGRATION_SQL = `
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
create unique index if not exists ux_songs_song_uid on songs(song_uid);
create index if not exists idx_songs_created_at on songs(created_at desc);

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
alter table profiles add column if not exists updated_at timestamp default now();
create unique index if not exists ux_profiles_uid on profiles(uid);

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
`;

function assertSafeDbName(name: string) {
  if (!/^[a-zA-Z0-9_]+$/.test(name)) throw new Error("Database name must be alphanumeric/underscore");
}

async function connect(cfg: { host: string; port: number; user: string; password: string; database: string }) {
  const client = new pg.Client({
    host: cfg.host,
    port: cfg.port,
    user: cfg.user,
    password: cfg.password,
    database: cfg.database,
  });
  await client.connect();
  return client;
}

export async function ensureDatabaseAndMigrate(cfg: {
  host: string;
  port: number;
  user: string;
  password: string;
  database: string;
}) {
  assertSafeDbName(cfg.database);

  let client: pg.Client | null = null;
  try {
    client = await connect(cfg);
  } catch (e) {
    const err = e as { code?: string; message?: string };
    if (err.code !== "3D000") return { ok: false, message: err.message ?? "Connection failed" };

    const adminDb = cfg.database === "postgres" ? "template1" : "postgres";
    const admin = await connect({ ...cfg, database: adminDb });
    try {
      const db = cfg.database.replace(/"/g, "\"\"");
      await admin.query(`create database "${db}"`);
    } catch (e2) {
      await admin.end().catch(() => undefined);
      return { ok: false, message: e2 instanceof Error ? e2.message : "Create database failed" };
    }
    await admin.end().catch(() => undefined);

    try {
      client = await connect(cfg);
    } catch (e3) {
      return { ok: false, message: e3 instanceof Error ? e3.message : "Re-connect failed" };
    }
  }

  try {
    await client.query("begin");
    await client.query(MIGRATION_SQL);
    await client.query("commit");
    return { ok: true, message: "Migrations applied" };
  } catch (e) {
    await client.query("rollback").catch(() => undefined);
    return { ok: false, message: e instanceof Error ? e.message : "Migration failed" };
  } finally {
    await client.end().catch(() => undefined);
  }
}
