#!/bin/sh
# Birth Chart Museum — Personal Edition (Mac launcher)
# Starts a local-only web server and opens the museum in your browser.
# ダブルクリックで起動できない場合: 右クリック →「開く」を選んでください。
cd "$(dirname "$0")" || exit 1

PORT=8787

# Prefer python3 when developer tools are present (best MIME handling).
# On a fresh Mac, calling the python3 stub would pop an Xcode install dialog,
# so only use it when xcode-select confirms tools exist or it's a real install.
if command -v python3 >/dev/null 2>&1; then
  PY3="$(command -v python3)"
  if [ "$PY3" != "/usr/bin/python3" ] || xcode-select -p >/dev/null 2>&1; then
    exec python3 tools/server.py
  fi
fi

# Fallback: the ruby shipped with macOS (webrick static server).
if [ -x /usr/bin/ruby ]; then
  echo ""
  echo "  BIRTH CHART MUSEUM — Personal Edition"
  echo "  ------------------------------------------------"
  echo "  URL: http://localhost:$PORT/"
  echo "  終了するには Ctrl+C（またはこのウィンドウを閉じる）。"
  echo ""
  ( sleep 2; open "http://localhost:$PORT/" ) &
  exec /usr/bin/ruby -run -e httpd -- app -p "$PORT"
fi

echo "python3 も ruby も見つかりませんでした。"
echo "Neither python3 nor ruby was found."
echo "python.org から Python 3 をインストール後、もう一度お試しください。"
read -r _
exit 1
