import os

FREEASTRO_BASE = os.getenv("FREEASTRO_BASE", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Birth Chart Museum Demo — 販売先URL（未設定なら購入ボタンは「近日発売」表示）
MUSEUM_SHOP_URL_EN = os.getenv("MUSEUM_SHOP_URL_EN", "")  # Etsy など海外向け
MUSEUM_SHOP_URL_JA = os.getenv("MUSEUM_SHOP_URL_JA", "")  # STORES など日本向け
ETSY_SHOP_URL = os.getenv("ETSY_SHOP_URL", "https://www.etsy.com/shop/nanamiastro")

# Chief Editor Neko sample hub — language-specific paid-product destinations.
# ES/DE stay hidden until their corresponding FULL Edition listings are ready.
# JA also stays hidden until the domestic destination is explicitly approved.
NEKO_SHOP_URL_EN = os.getenv("NEKO_SHOP_URL_EN", ETSY_SHOP_URL)
NEKO_SHOP_URL_JA = os.getenv("NEKO_SHOP_URL_JA", "")
NEKO_SHOP_URL_ES = os.getenv("NEKO_SHOP_URL_ES", "")
NEKO_SHOP_URL_DE = os.getenv("NEKO_SHOP_URL_DE", "")
