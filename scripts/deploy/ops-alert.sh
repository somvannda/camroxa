#!/usr/bin/env bash
# CamXora ops monitor: every application (systemd unit + public endpoint),
# database/Redis, the nightly backup, and host resources — paged to Telegram.
#
# Driven by ops-alert.timer every 5 minutes. For each app this keeps a
# "down since" marker, so every page states how long the app has been down and
# what the concrete issue is (unit state and/or HTTP status). A single app
# failure produces one message, not one message per check:
#
#   🔴 CAMXORA DOWN · Production
#   • Music web — down 1h 12m (since 04:08 +07)
#     issue: service inactive (failed); HTTP 502
#
# While an app stays down the report repeats at most once an hour (fresh
# duration). Recovery sends one message with the total downtime. A daily
# 09:00 Asia/Phnom_Penh summary lists every app with its status, downtime over
# the last 24h and its last issue.
#
# The user portal (app.camxora.com / camxora-portal) is deliberately not
# monitored: it was retired in favour of music.camxora.com and is stopped and
# disabled on the host, so alerting on it only produced false "down" pages.
#
# Run standalone to test:
#   bash scripts/deploy/ops-alert.sh --status    # print + send full status
#   bash scripts/deploy/ops-alert.sh --dry-run   # print, send nothing
#   bash scripts/deploy/ops-alert.sh --test      # one Telegram ping
set -u

ENV_FILE="${ENV_FILE:-/opt/camxora/repo/platform_api/.env}"
STATE_DIR="${STATE_DIR:-/var/lib/camxora-ops-alert}"
mkdir -p "$STATE_DIR" 2>/dev/null || true

# Consecutive 5-minute runs an app must fail before the first page, so one
# stalled outbound handshake does not page the whole channel.
FAIL_STREAK_ALERT="${FAIL_STREAK_ALERT:-2}"
# While still down, refresh the page at most this often (seconds).
REALERT_SECONDS="${REALERT_SECONDS:-3600}"
# Daily all-app summary hour (Asia/Phnom_Penh, 24h clock).
DAILY_HOUR="${DAILY_HOUR:-9}"
HTTP_TIMEOUT="${HTTP_TIMEOUT:-15}"
HTTP_RETRIES="${HTTP_RETRIES:-2}"
# A dump older than this is treated as a broken backup even when the unit is
# not "failed" (timer disabled, deploy deleted the script, host was down).
BACKUP_MAX_AGE_H="${BACKUP_MAX_AGE_H:-26}"
BACKUP_DIR_MUSICAPI="${BACKUP_DIR_MUSICAPI:-/opt/camxora/backups/musicapi}"
BACKUP_DIR_PLATFORM="${BACKUP_DIR_PLATFORM:-/opt/camxora/backups/platform}"

case "$FAIL_STREAK_ALERT" in ''|*[!0-9]*|0) FAIL_STREAK_ALERT=2;; esac
case "$REALERT_SECONDS" in ''|*[!0-9]*|0) REALERT_SECONDS=3600;; esac
case "$DAILY_HOUR" in ''|*[!0-9]*) DAILY_HOUR=9;; esac
[ "$DAILY_HOUR" -le 23 ] 2>/dev/null || DAILY_HOUR=9
case "$HTTP_RETRIES" in ''|*[!0-9]*|0) HTTP_RETRIES=2;; esac

TIMER_TZ="Asia/Phnom_Penh"
DRY_RUN="${DRY_RUN:-0}"

read_env() {
  sed -n "s/^$1=//p" "$ENV_FILE" 2>/dev/null | head -n1 \
    | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//" | tr -d '\r'
}

TOKEN="${OPS_TELEGRAM_BOT_TOKEN:-$(read_env PLATFORM_TELEGRAM_BOT_TOKEN)}"
CHAT="${OPS_TELEGRAM_CHAT_ID:-$(read_env PLATFORM_TELEGRAM_CHAT_ID)}"
DEPLOY_ENV="$(read_env PLATFORM_ENVIRONMENT)"
DEPLOY_ENV="$(printf '%s' "$DEPLOY_ENV" | tr '[:upper:]' '[:lower:]')"
HOST="$(hostname)"

env_label() {
  case "$DEPLOY_ENV" in
    production|prod) printf 'Production' ;;
    sandbox|staging) printf 'Sandbox' ;;
    *) printf '%s' "${DEPLOY_ENV:-Unknown}" ;;
  esac
}

esc() {
  printf '%s' "${1//&/&amp;}" | sed -e 's/</\&lt;/g' -e 's/>/\&gt;/g'
}

one_line() {
  printf '%s' "${1//$'\n'/ }" | tr '\t' ' ' | tr -s ' '
}

send() {
  local text="$1"
  if [ "$DRY_RUN" = "1" ]; then
    printf '%s\n' "----- (dry run) -----"
    printf '%s\n' "$text"
    return 0
  fi
  if [[ "$DEPLOY_ENV" != "production" && "$DEPLOY_ENV" != "prod" ]]; then
    printf 'ops-alert: non-production environment (%s); not delivered\n' "${DEPLOY_ENV:-unknown}" >&2
    return 0
  fi
  if [ -z "$TOKEN" ] || [ -z "$CHAT" ]; then
    printf 'ops-alert: telegram not configured\n' >&2
    return 0
  fi
  if ! curl -sS --max-time 15 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT}" \
    --data-urlencode "text=${text}" \
    --data-urlencode "parse_mode=HTML" \
    --data-urlencode "disable_web_page_preview=true" >/dev/null 2>&1; then
    printf 'ops-alert: telegram send failed\n' >&2
    return 1
  fi
  return 0
}

fmt_duration() {
  local s="${1:-0}"
  if [ "$s" -lt 60 ]; then printf '%ds' "$s"; return; fi
  if [ "$s" -lt 3600 ]; then printf '%dm' $(( s / 60 )); return; fi
  if [ "$s" -lt 86400 ]; then printf '%dh %dm' $(( s / 3600 )) $(( (s % 3600) / 60 )); return; fi
  printf '%dd %dh' $(( s / 86400 )) $(( (s % 86400) / 3600 ))
}

fmt_time() {
  TZ="$TIMER_TZ" date -d "@$1" '+%d %b %H:%M' 2>/dev/null || printf '%s' "$1"
}

fmt_stamp() {
  TZ="$TIMER_TZ" date '+%d %b %Y %H:%M'
}

# label|unit|url|extra   (extra: pg, redis, backup, or empty)
APPS=(
  "Website|camxora-website|https://camxora.com/|"
  "Music web|camxora-music|https://music.camxora.com/|"
  "Admin console||https://admin.camxora.com/|"
  "Platform API|camxora-api|https://api.camxora.com/health|"
  "Music API|camxora-musicapi|https://musicapi.camxora.com/health|"
  "Music API playground|camxora-musicapi-web-user|http://127.0.0.1:4001/|"
  "Music API admin|camxora-musicapi-web-admin|http://127.0.0.1:4002/|"
  "PostgreSQL|postgresql||pg"
  "Redis|redis-server||redis"
  "Nginx|nginx||"
  "Nightly DB backup|||backup"
  "Nightly platform backup|||backup-platform"
)

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed -e 's/^-//' -e 's/-$//'
}

http_code() {
  local url="$1" code="" attempt
  for (( attempt = 1; attempt <= HTTP_RETRIES; attempt++ )); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' \
      --connect-timeout 10 -m "$HTTP_TIMEOUT" --retry 1 --retry-delay 2 \
      --retry-all-errors "$url" 2>/dev/null || true)"
    code="${code:-000}"
    # Retry only a missing answer or a server error; a 2xx/3xx/4xx is a real
    # answer (4xx still counts as "the app answered" and is judged by caller).
    case "$code" in
      000|5??) ;;
      *) printf '%s' "$code"; return ;;
    esac
    [ "$attempt" -lt "$HTTP_RETRIES" ] && sleep 2
  done
  printf '%s' "${code:-000}"
}

# Hours since the newest dump in a directory, or "missing" when there is none.
newest_dump_age_h() {
  local dir="$1" pattern="$2" newest
  newest="$(find "$dir" -maxdepth 1 -type f -name "$pattern" -printf '%T@\n' 2>/dev/null \
    | sort -n | tail -1)"
  if [ -z "$newest" ]; then
    printf 'missing'
    return
  fi
  printf '%s' $(( ( $(date +%s) - ${newest%.*} ) / 3600 ))
}

backup_issue() {
  local unit="$1" dir="$2" pattern="$3" age msg="" when
  if systemctl is-failed --quiet "$unit" 2>/dev/null; then
    when="$(systemctl show "$unit" -p ExecMainExitTimestamp --value 2>/dev/null)"
    msg="last backup failed${when:+ at $when}"
  fi
  age="$(newest_dump_age_h "$dir" "$pattern")"
  if [ "$age" = "missing" ]; then
    msg="${msg:+$msg; }no dump found"
  elif [ "$age" -gt "$BACKUP_MAX_AGE_H" ]; then
    msg="${msg:+$msg; }newest dump is ${age}h old"
  fi
  printf '%s' "$msg"
}

# Prints the concrete issue(s) for one app, or nothing when healthy.
probe_app() {
  local unit="$1" url="$2" extra="$3"
  local issues="" state code

  if [ -n "$unit" ]; then
    state="$(systemctl is-active "$unit" 2>/dev/null || true)"
    if [ "$state" != "active" ]; then
      issues="service ${state:-unknown}"
    fi
  fi

  case "$extra" in
    pg)
      if command -v pg_isready >/dev/null 2>&1; then
        pg_isready -q 2>/dev/null || issues="${issues:+$issues; }postgres not accepting connections"
      fi
      ;;
    redis)
      if command -v redis-cli >/dev/null 2>&1; then
        [ "$(redis-cli ping 2>/dev/null)" = "PONG" ] || issues="${issues:+$issues; }redis did not answer PONG"
      fi
      ;;
    backup)
      issues="$(backup_issue camxora-musicapi-backup.service "$BACKUP_DIR_MUSICAPI" 'sunoapi-*.dump')"
      ;;
    backup-platform)
      issues="$(backup_issue camxora-platform-db-backup.service "$BACKUP_DIR_PLATFORM" 'camxora_platform-*.dump')"
      ;;
  esac

  if [ -n "$url" ]; then
    code="$(http_code "$url")"
    case "$code" in
      000) issues="${issues:+$issues; }no HTTP response" ;;
      ''|*[!0-9]*) issues="${issues:+$issues; }HTTP ${code}" ;;
      *) [ "$code" -ge 400 ] && issues="${issues:+$issues; }HTTP $code" ;;
    esac
  fi

  printf '%s' "$issues"
}

# --- host resources ---------------------------------------------------------
host_section() {
  local total avail pct disk swt swf swp oom
  total=$(awk '/^MemTotal:/{print int($2/1024)}' /proc/meminfo)
  avail=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
  pct=$(( total > 0 ? avail * 100 / total : 100 ))
  disk=$(df -P / | awk 'NR==2{print $5}' | tr -d '%')
  swt=$(awk '/^SwapTotal:/{print int($2/1024)}' /proc/meminfo)
  swf=$(awk '/^SwapFree:/{print int($2/1024)}' /proc/meminfo)
  swp=0
  [ "$swt" -gt 0 ] && swp=$(( (swt - swf) * 100 / swt ))
  oom=$(journalctl -k --since '10 min ago' --no-pager 2>/dev/null | grep -c 'Out of memory: Killed process' || true)

  printf 'host: RAM %s%% available · disk %s%% · swap %s%% · OOM kills 10m: %s' \
    "$pct" "$disk" "$swp" "${oom:-0}"
  [ "${oom:-0}" -gt 0 ] && printf ' ⚠️'
}

host_alerts() {
  local total avail pct disk swt swf swp api_mem
  total=$(awk '/^MemTotal:/{print int($2/1024)}' /proc/meminfo)
  avail=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
  pct=$(( total > 0 ? avail * 100 / total : 100 ))
  [ "$pct" -lt 10 ] && alert_once mem "⚠️ <b>${HOST}</b>: low memory — ${pct}% available (${avail} MB of ${total} MB)"

  swt=$(awk '/^SwapTotal:/{print int($2/1024)}' /proc/meminfo)
  swf=$(awk '/^SwapFree:/{print int($2/1024)}' /proc/meminfo)
  if [ "$swt" -gt 0 ]; then
    swp=$(( (swt - swf) * 100 / swt ))
    [ "$swp" -gt 50 ] && alert_once swap "⚠️ <b>${HOST}</b>: swap ${swp}% used ($((swt - swf)) MB)"
  fi

  disk=$(df -P / | awk 'NR==2{print $5}' | tr -d '%')
  [ "$disk" -gt 85 ] && alert_once disk "⚠️ <b>${HOST}</b>: disk ${disk}% used"

  local oom
  oom=$(journalctl -k --since '10 min ago' --no-pager 2>/dev/null | grep -c 'Out of memory: Killed process' || true)
  [ "${oom:-0}" -gt 0 ] && alert_once oom "🚨 <b>${HOST}</b>: ${oom} OOM kill(s) in the last 10 minutes"

  api_mem=$(systemctl show camxora-api -p MemoryCurrent --value 2>/dev/null || echo 0)
  case "$api_mem" in ''|*[!0-9]*) api_mem=0;; esac
  [ "$api_mem" -gt 4831838208 ] && alert_once api-mem "⚠️ <b>${HOST}</b>: camxora-api at $((api_mem/1024/1024)) MB (over 4.5 GB)"
}

alert_once() {
  local key="$1" msg="$2" f="$STATE_DIR/host-$1.last"
  local now last=0
  now=$(date +%s)
  [ -f "$f" ] && last=$(cat "$f" 2>/dev/null || echo 0)
  case "$last" in ''|*[!0-9]*) last=0;; esac
  if [ $(( now - last )) -ge 1800 ]; then
    printf '%s' "$now" > "$f"
    send "$msg"
  fi
}

# --- full status (--status / --dry-run) -------------------------------------
status_report() {
  local lines=() row label unit url extra slug since dur issue
  lines+=("📊 <b>CAMXORA status</b> · $(env_label)")
  lines+=("${HOST} · $(fmt_stamp) +07")
  lines+=("")
  for row in "${APPS[@]}"; do
    IFS='|' read -r label unit url extra <<<"$row"
    slug="$(slugify "$label")"
    issue="$(one_line "$(probe_app "$unit" "$url" "$extra")")"
    since="$(cat "$STATE_DIR/app-$slug.down_since" 2>/dev/null || true)"
    if [ -n "$issue" ]; then
      dur=0
      [ -n "$since" ] && dur=$(( $(date +%s) - since ))
      lines+=("• <b>$(esc "$label")</b> — 🔴 down $(fmt_duration "$dur")")
      lines+=("  issue: $(esc "$issue")")
    else
      lines+=("• <b>$(esc "$label")</b> — 🟢 up")
    fi
  done
  lines+=("")
  lines+=("$(host_section)")
  printf '%s\n' "${lines[@]}"
}

if [ "${1:-}" = "--test" ]; then
  send "✅ CamXora ops alerts connected on ${HOST}"
  printf 'test alert sent\n'
  exit 0
fi

# Run one full check but print the would-be Telegram text instead of sending.
[ "${1:-}" = "--print" ] && DRY_RUN=1

if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  status_report
  exit 0
fi

if [ "${1:-}" = "--status" ]; then
  text="$(status_report)"
  printf '%s\n' "$text"
  send "$text"
  exit 0
fi

# --- transitions ------------------------------------------------------------
report_down=()
report_up=()
paged_slugs=()
now=$(date +%s)

for row in "${APPS[@]}"; do
  IFS='|' read -r label unit url extra <<<"$row"
  slug="$(slugify "$label")"
  since_file="$STATE_DIR/app-$slug.down_since"
  issue_file="$STATE_DIR/app-$slug.issue"
  streak_file="$STATE_DIR/app-$slug.streak"
  notify_file="$STATE_DIR/app-$slug.notified"
  hist_file="$STATE_DIR/history.log"

  issue="$(one_line "$(probe_app "$unit" "$url" "$extra")")"

  if [ -n "$issue" ]; then
    printf '%s' "$issue" > "$issue_file"
    printf '%s\t%s\t%s\n' "$now" "$slug" "$issue" >> "$STATE_DIR/issues.log"

    streak=0
    [ -f "$streak_file" ] && streak=$(cat "$streak_file" 2>/dev/null || echo 0)
    case "$streak" in ''|*[!0-9]*) streak=0;; esac
    streak=$(( streak + 1 ))
    printf '%s' "$streak" > "$streak_file"

    since="$(cat "$since_file" 2>/dev/null || true)"
    if [ -z "$since" ]; then
      since=$now
      printf '%s' "$since" > "$since_file"
      printf '%s\t%s\tdown\t0\t%s\n' "$now" "$slug" "$issue" >> "$hist_file"
    fi

    last=0
    [ -f "$notify_file" ] && last=$(cat "$notify_file" 2>/dev/null || echo 0)
    case "$last" in ''|*[!0-9]*) last=0;; esac

    if [ "$streak" -ge "$FAIL_STREAK_ALERT" ] \
      && { [ "$last" -eq 0 ] || [ $(( now - last )) -ge "$REALERT_SECONDS" ]; }; then
      dur=$(( now - since ))
      report_down+=("• <b>$(esc "$label")</b> — down $(fmt_duration "$dur") (since $(fmt_time "$since") +07)")
      report_down+=("  issue: $(esc "$issue")")
      paged_slugs+=("$slug")
      printf '%s' "$now" > "$notify_file"
    fi
  else
    since="$(cat "$since_file" 2>/dev/null || true)"
    if [ -n "$since" ]; then
      dur=$(( now - since ))
      printf '%s\t%s\tup\t%s\t%s\n' "$now" "$slug" "$dur" "$(cat "$issue_file" 2>/dev/null)" >> "$hist_file"
      # Only announce a recovery for an app we actually paged about.
      [ -f "$notify_file" ] && report_up+=("• <b>$(esc "$label")</b> — back up after $(fmt_duration "$dur")")
    fi
    rm -f "$streak_file" "$since_file" "$notify_file"
    # Keep issue_file so the daily report can show the most recent issue.
  fi
done

# --- immediate alert --------------------------------------------------------
if [ "${#report_down[@]}" -gt 0 ] || [ "${#report_up[@]}" -gt 0 ]; then
  msg=""
  if [ "${#report_down[@]}" -gt 0 ]; then
    msg="🔴 <b>CAMXORA DOWN</b> · $(env_label)"$'\n'
    msg+="${HOST} · $(fmt_stamp) +07"$'\n'$'\n'
    msg+="$(printf '%s\n' "${report_down[@]}")"
  fi
  if [ "${#report_up[@]}" -gt 0 ]; then
    [ -n "$msg" ] && msg+=$'\n\n'
    msg+="🟢 <b>CAMXORA RECOVERED</b>"$'\n'
    msg+="$(printf '%s\n' "${report_up[@]}")"
  fi
  [ -n "$msg" ] && { send "$msg" || for slug in "${paged_slugs[@]}"; do rm -f "$STATE_DIR/app-$slug.notified"; done; }
fi

host_alerts

# --- daily all-app summary --------------------------------------------------
today="$(TZ="$TIMER_TZ" date +%F)"
hour_now="$(TZ="$TIMER_TZ" date +%H)"
hour_now=$((10#$hour_now))
last_daily="$(cat "$STATE_DIR/last_daily" 2>/dev/null || true)"
if [ "$last_daily" != "$today" ] && [ "$hour_now" -eq "$DAILY_HOUR" ]; then
  cutoff=$(( $(date +%s) - 86400 ))
  hist_file="$STATE_DIR/history.log"
  lines=("📊 <b>CAMXORA daily status</b> · $(env_label)")
  lines+=("${HOST} · $(fmt_stamp) +07")
  lines+=("")
  for row in "${APPS[@]}"; do
    IFS='|' read -r label unit url extra <<<"$row"
    slug="$(slugify "$label")"
    issue="$(one_line "$(probe_app "$unit" "$url" "$extra")")"
    since="$(cat "$STATE_DIR/app-$slug.down_since" 2>/dev/null || true)"
    down=0
    cur=0
    if [ -n "$since" ]; then
      cur=$(( $(date +%s) - since ))
      down=$cur
      [ "$down" -gt 86400 ] && down=86400
    fi
    if [ -f "$hist_file" ]; then
      past="$(awk -F'\t' -v s="$slug" -v c="$cutoff" '$2==s && $3=="up" && $1>=c {t+=$4} END{print t+0}' "$hist_file")"
      down=$(( down + ${past:-0} ))
      [ "$down" -gt 86400 ] && down=86400
    fi
    last_issue="$(awk -F'\t' -v s="$slug" -v c="$cutoff" '$2==s && $1>=c && $5!="" {m=$5} END{print m}' "$hist_file" 2>/dev/null)"
    [ -z "$issue" ] && issue="$last_issue"
    if [ -n "$issue" ]; then
      if [ -n "$since" ]; then
        lines+=("• <b>$(esc "$label")</b> — 🔴 down $(fmt_duration "$cur") · downtime 24h: $(fmt_duration "$down")")
      else
        lines+=("• <b>$(esc "$label")</b> — 🟢 up · downtime 24h: $(fmt_duration "$down")")
      fi
      lines+=("  issue: $(esc "$issue")")
    else
      lines+=("• <b>$(esc "$label")</b> — 🟢 up · downtime 24h: $(fmt_duration "$down")")
    fi
  done
  lines+=("")
  lines+=("$(host_section)")
  text="$(printf '%s\n' "${lines[@]}")"
  if send "$text"; then
    printf '%s' "$today" > "$STATE_DIR/last_daily"
  fi
fi
