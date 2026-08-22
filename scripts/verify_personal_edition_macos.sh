#!/bin/bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dist_dir="$repo_root/personal-edition/dist"
scratch_root="$(mktemp -d "${RUNNER_TEMP:-/tmp}/nanami-personal-edition-macos.XXXXXX")"
server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$scratch_root"
}
trap cleanup EXIT

fail() {
  echo "macOS verification failed: $*" >&2
  exit 1
}

shopt -s nullglob
version="$(awk -F'"' '/^VERSION = / { print $2; exit }' "$repo_root/personal-edition/build.py")"
[[ -n "$version" ]] || fail "could not read Personal Edition version"
archives=("$dist_dir"/BirthChartMuseum-PersonalEdition-*-v"$version".zip)
[[ ${#archives[@]} -eq 2 ]] || fail "expected exactly two EN/JA template ZIPs, found ${#archives[@]}"

launch_bundle=""
for archive in "${archives[@]}"; do
  archive_name="$(basename "$archive" .zip)"
  extract_dir="$scratch_root/$archive_name"
  mkdir -p "$extract_dir"
  /usr/bin/ditto -x -k "$archive" "$extract_dir"
  bundle="$extract_dir/BirthChartMuseum-PersonalEdition"

  [[ -d "$bundle/app" ]] || fail "app directory missing from $(basename "$archive")"
  [[ -x "$bundle/START-MUSEUM-MAC.command" ]] || fail "museum launcher is not executable in $(basename "$archive")"
  [[ -x "$bundle/START-ACG-MAC.command" ]] || fail "ACG launcher is not executable in $(basename "$archive")"
  [[ -x "$bundle/tools/server.py" ]] || fail "server.py is not executable in $(basename "$archive")"

  if LC_ALL=C grep -q $'\r' "$bundle/START-MUSEUM-MAC.command" "$bundle/START-ACG-MAC.command"; then
    fail "Mac launcher contains CRLF line endings in $(basename "$archive")"
  fi

  grep -Fq "選んだ場所の星のメッセージをAIに聞く" "$bundle/app/acg/index.html" \
    || fail "new AI reading action missing from $(basename "$archive")"
  grep -Fq "占術データへ戻る" "$bundle/app/acg/index.html" \
    || fail "updated return label missing from $(basename "$archive")"

  if [[ -z "$launch_bundle" ]]; then
    launch_bundle="$bundle"
  fi
done

run_launcher() {
  local launcher="$1"
  local url="$2"
  local expected="$3"
  local log_file="$scratch_root/${launcher}.log"
  local body_file="$scratch_root/${launcher}.html"

  BROWSER=/usr/bin/true "$launch_bundle/$launcher" >"$log_file" 2>&1 &
  server_pid=$!

  local ready=0
  for _ in {1..30}; do
    if curl --fail --silent --show-error "$url" >"$body_file"; then
      ready=1
      break
    fi
    sleep 1
  done
  if [[ "$ready" -ne 1 ]]; then
    cat "$log_file" >&2 || true
    fail "$launcher did not serve $url"
  fi
  grep -Fq "$expected" "$body_file" || fail "$launcher served unexpected content at $url"

  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
  server_pid=""
  sleep 1
}

run_launcher "START-ACG-MAC.command" "http://127.0.0.1:8787/acg/" "選んだ場所の星のメッセージをAIに聞く"
run_launcher "START-MUSEUM-MAC.command" "http://127.0.0.1:8787/" "me-yaml-input"

echo "Personal Edition macOS ZIP and launcher verification passed."
