#!/bin/sh
# Personal ACG Map launcher (Mac)
# Starts the local-only web server and opens ACG directly.
cd "$(dirname "$0")" || exit 1

PORT=8787

if command -v python3 >/dev/null 2>&1; then
  PY3="$(command -v python3)"
  if [ "$PY3" != "/usr/bin/python3" ] || xcode-select -p >/dev/null 2>&1; then
    exec python3 tools/server.py --open-path /acg/
  fi
fi

if [ -x /usr/bin/ruby ]; then
  echo ""
  echo "  PERSONAL ACG MAP"
  echo "  ------------------------------------------------"
  echo "  URL: http://localhost:$PORT/acg/"
  echo "  Press Ctrl+C or close this window to stop."
  echo ""
  ( sleep 2; open "http://localhost:$PORT/acg/" ) &
  exec /usr/bin/ruby -run -e httpd -- app -p "$PORT"
fi

echo "Neither python3 nor ruby was found."
echo "Install Python 3 from python.org, then try again."
read -r _
exit 1
