#!/usr/bin/env python3
"""Birth Chart Museum — Personal Edition local server (cross-platform).

Serves the ../app directory on http://localhost:<port>/ and opens the browser.
Local-only: binds to 127.0.0.1 and sends nothing anywhere.
Stop with Ctrl+C (or close the terminal window).
"""
import mimetypes
import os
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

# Windows の cp932 コンソールでも日本語メッセージが落ちないようにする
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(os.path.dirname(HERE), "app")

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/yaml", ".yaml")
mimetypes.add_type("text/yaml", ".yml")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/svg+xml", ".svg")


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console quiet
        pass


def main():
    if not os.path.isdir(APP_DIR):
        sys.exit("app folder not found: %s" % APP_DIR)
    httpd = None
    port = 0
    for candidate in range(8787, 8797):
        try:
            httpd = ThreadingHTTPServer(
                ("127.0.0.1", candidate), partial(Handler, directory=APP_DIR)
            )
            port = candidate
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit("No free port found (8787-8796).")

    url = "http://localhost:%d/" % port
    print()
    print("  BIRTH CHART MUSEUM - Personal Edition")
    print("  ------------------------------------------------")
    print("  URL: %s" % url)
    print("  ブラウザが自動で開きます。開かない場合は上のURLをブラウザに貼ってください。")
    print("  終了するには Ctrl+C（またはこのウィンドウを閉じる）。")
    print("  (Press Ctrl+C or close this window to stop.)")
    print()
    threading.Timer(0.8, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
