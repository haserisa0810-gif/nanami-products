from datetime import datetime, timezone

from services import pg_store
from services.prompt_builder import WESTERN_FULL_PROMPT

sample = """schema_version: "1.0"
product:
  product_type: western_full
  options:
    western: true
    transit: true
birth_time:
  accuracy: exact
systems:
  western:
    natal:
      planets: []
    transit:
      today:
        selected_date: 2026-07-12
      transiting_bodies: []
"""

preview_chart = {
    "token": "chart-companion-preview",
    "order_code": None,
    "buyer_name": "Preview",
    "birth_date": "1990-01-01",
    "birth_time": "12:00",
    "birth_place": "Tokyo",
    "options": {"product_type": "western_full"},
    "yaml_text": sample,
    "prompt_text": WESTERN_FULL_PROMPT,
    "share_yaml_text": sample,
    "expires_at": None,
    "created_at": datetime.now(timezone.utc),
}

pg_store.init_db = lambda: None
pg_store.get_chart = lambda token, include_svgs=True: (
    preview_chart.copy() if token == preview_chart["token"] else None
)

import uvicorn
import routes

routes._chart_expiry_label = lambda expires_at: "Preview"
app = routes.app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
