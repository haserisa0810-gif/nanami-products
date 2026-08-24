import os

FREEASTRO_BASE = os.getenv("FREEASTRO_BASE", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Birth Chart Museum Demo — 販売先URL（未設定なら購入ボタンは「近日発売」表示）
MUSEUM_SHOP_URL_EN = os.getenv("MUSEUM_SHOP_URL_EN", "")  # Etsy など海外向け
MUSEUM_SHOP_URL_JA = os.getenv("MUSEUM_SHOP_URL_JA", "")  # STORES など日本向け
ETSY_SHOP_URL = os.getenv("ETSY_SHOP_URL", "https://www.etsy.com/shop/nanamiastro")
