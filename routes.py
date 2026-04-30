from __future__ import annotations

import os
import secrets

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services import pg_store
from services.location import PREFECTURE_OPTIONS
from services.yaml_exporter import build_product_yaml

app = FastAPI(title="nanami-products")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


PRODUCT_CONFIG = {
    "western_basic": {
        "label": "ホロスコープ基本版",
        "description": "西洋占星術の出生図データを生成します。小惑星・四柱推命・日替わり境界の選択項目は表示しません。",
        "features": [
            "西洋占星術の出生図データ",
            "小惑星オプションなし",
            "四柱推命なし",
            "トランジットなし",
        ],
        "include_asteroids": False,
        "include_shichusuimei": False,
        "include_transit": False,
    },
    "western_full": {
        "label": "ホロスコープFULL版",
        "description": "小惑星とトランジット（1ヶ月）をセットで含めます。購入者側での選択は不要です。",
        "features": [
            "西洋占星術の出生図データ",
            "小惑星込み",
            "トランジット（1ヶ月）込み",
            "四柱推命なし",
        ],
        "include_asteroids": True,
        "include_shichusuimei": False,
        "include_transit": True,
    },
    "shichu": {
        "label": "四柱推命版",
        "description": "四柱推命データを生成します。日替わり境界は、購入者が23時または1時から選択できます。",
        "features": [
            "四柱推命データ",
            "日替わり境界を選択可能",
            "標準選択は1時（丑の刻）",
            "小惑星・トランジットなし",
        ],
        "include_asteroids": False,
        "include_shichusuimei": True,
        "include_transit": False,
    },
}


def _product_type_from_request(request: Request) -> str:
    product_type = request.query_params.get("type", "western_basic").strip()
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    return product_type


def _product_context(product_type: str) -> dict:
    config = PRODUCT_CONFIG.get(product_type, PRODUCT_CONFIG["western_basic"])
    return {"product_type": product_type, "product": config}


def _buyer_template(prefix: str, product_type: str) -> str:
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    return f"{prefix}_{product_type}.html"


@app.on_event("startup")
def startup() -> None:
    import logging
    import os
    if not os.environ.get("DATABASE_URL"):
        logging.warning("DATABASE_URL が未設定のため DB 初期化をスキップしました")
        return
    try:
        pg_store.init_db()
    except Exception as exc:
        logging.error("DB 初期化に失敗しました: %s", exc)


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "nanami-products"}


# ─── 購入者フロー ────────────────────────────────────────────────

@app.get("/start", response_class=HTMLResponse)
def start(request: Request):
    product_type = _product_type_from_request(request)
    return templates.TemplateResponse(
        _buyer_template("start", product_type),
        {"request": request, **_product_context(product_type)},
    )


@app.get("/redeem", response_class=HTMLResponse)
def redeem_get(request: Request):
    product_type = _product_type_from_request(request)
    return templates.TemplateResponse(
        _buyer_template("redeem", product_type),
        {
            "request": request,
            "prefectures": PREFECTURE_OPTIONS,
            **_product_context(product_type),
        },
    )


@app.post("/redeem", response_class=HTMLResponse)
def redeem_post(
    request: Request,
    order_code: str = Form(...),
    buyer_name: str = Form(""),
    email: str = Form(""),
    birth_date: str = Form(...),
    birth_time: str = Form(""),
    prefecture: str = Form(...),
    gender: str = Form("unknown"),
    product_type: str = Form("western_basic"),
    day_change_at_23: str | None = Form(None),
    agree_final: str | None = Form(None),
):
    product_type = request.query_params.get("type", product_type).strip() or "western_basic"
    if product_type not in PRODUCT_CONFIG:
        product_type = "western_basic"
    product = PRODUCT_CONFIG[product_type]

    include_asteroids = bool(product["include_asteroids"])
    include_shichusuimei = bool(product["include_shichusuimei"])
    include_transit = bool(product.get("include_transit"))

    # 商品ごとに強制制御します。
    # western_basic / western_full では日替わり境界UIを出さず、必ず False。
    # shichu は購入者が 23時 / 1時 を選択できます。未選択時は 1時（False）を標準にします。
    if product_type == "shichu":
        day_change_at_23_bool = str(day_change_at_23).strip().lower() in {"1", "true", "on", "yes", "23"}
    else:
        day_change_at_23_bool = False

    def _form_err(msg: str, status: int = 400):
        return templates.TemplateResponse(
            _buyer_template("redeem", product_type),
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": msg,
                "form": {
                    "order_code": order_code,
                    "buyer_name": buyer_name,
                    "email": email,
                    "birth_date": birth_date,
                    "birth_time": birth_time,
                    "prefecture": prefecture,
                    "gender": gender,
                    "product_type": product_type,
                    "day_change_at_23": day_change_at_23_bool,
                    "agree_final": bool(agree_final),
                },
                **_product_context(product_type),
            },
            status_code=status,
        )

    order_code_clean = order_code.strip()
    if not order_code_clean:
        return _form_err("注文番号を入力してください。")
    if not agree_final:
        return _form_err("入力後は変更できないことを確認し、チェックを入れてください。")

    try:
        yaml_text, prompt_text, doc = build_product_yaml(
            title=buyer_name.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            prefecture=prefecture.strip(),
            gender=gender.strip() or "unknown",
            include_asteroids=include_asteroids,
            include_shichusuimei=include_shichusuimei,
            include_transit=include_transit,
            day_change_at_23=day_change_at_23_bool,
        )
    except Exception as e:
        return _form_err(f"データ生成に失敗しました: {e}")

    token = secrets.token_urlsafe(18)
    try:
        ok = pg_store.redeem_and_save(
        order_code=order_code_clean,
        email=email.strip() or None,
        buyer_name=buyer_name.strip() or None,
        token=token,
        birth_date=birth_date.strip(),
        birth_time=birth_time.strip() or None,
        birth_place=prefecture.strip(),
        options={**doc.get("product", {}).get("options", {}), "product_type": product_type},
        yaml_text=yaml_text,
            prompt_text=prompt_text,
        )
    except Exception as e:
        return _form_err(f"保存に失敗しました: {e}", status=500)

    if not ok:
        return _form_err(
            f"この注文番号（{order_code_clean}）はすでに使用済みです。"
            "別の注文番号をご確認ください。",
            status=409,
        )

    return RedirectResponse(f"/chart/{token}", status_code=303)


# ─── チャートページ（ルート順に注意） ──────────────────────────────
# {token}.yaml / {token}/prompt.txt を {token} より先に登録する

@app.get("/chart/{token}.yaml", response_class=PlainTextResponse)
def chart_yaml(token: str):
    chart = _load_chart_or_404(token)
    return PlainTextResponse(chart["yaml_text"], media_type="text/yaml; charset=utf-8")


@app.get("/chart/{token}/prompt.txt", response_class=PlainTextResponse)
def chart_prompt(token: str):
    chart = _load_chart_or_404(token)
    return PlainTextResponse(chart["prompt_text"], media_type="text/plain; charset=utf-8")


@app.get("/chart/{token}", response_class=HTMLResponse)
def chart_page(request: Request, token: str):
    chart = _load_chart_or_404(token)
    base_url = _public_base_url(request)
    return templates.TemplateResponse(
        "chart_page.html",
        {
            "request": request,
            "token": token,
            "chart": chart,
            "chart_url": f"{base_url}/chart/{token}",
            "yaml_url": f"{base_url}/chart/{token}.yaml",
            "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
        },
    )


# ─── 管理者フロー ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin/yaml/new", response_class=HTMLResponse)
def yaml_new(request: Request):
    return templates.TemplateResponse(
        "yaml_form.html",
        {"request": request, "prefectures": PREFECTURE_OPTIONS},
    )


@app.post("/admin/yaml/generate", response_class=HTMLResponse)
def yaml_generate(
    request: Request,
    title: str = Form(""),
    birth_date: str = Form(...),
    birth_time: str = Form(""),
    prefecture: str = Form(...),
    gender: str = Form("unknown"),
    include_asteroids: str | None = Form(None),
    include_shichusuimei: str | None = Form(None),
    include_transit: str | None = Form(None),
    day_change_at_23: str | None = Form(None),
):
    token = secrets.token_urlsafe(18)
    try:
        yaml_text, prompt_text, doc = build_product_yaml(
            title=title.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            prefecture=prefecture.strip(),
            gender=gender.strip() or "unknown",
            include_asteroids=bool(include_asteroids),
            include_shichusuimei=bool(include_shichusuimei),
            include_transit=bool(include_transit),
            day_change_at_23=bool(day_change_at_23),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "yaml_form.html",
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": str(e),
                "form": {
                    "title": title, "birth_date": birth_date, "birth_time": birth_time,
                    "prefecture": prefecture, "gender": gender,
                },
            },
            status_code=400,
        )

    try:
        pg_store.save_chart(
            token=token,
            order_code=None,
            buyer_name=title.strip() or None,
            birth_date=birth_date.strip(),
            birth_time=birth_time.strip() or None,
            birth_place=prefecture.strip(),
            options=doc.get("product", {}).get("options", {}),
            yaml_text=yaml_text,
            prompt_text=prompt_text,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "yaml_form.html",
            {
                "request": request,
                "prefectures": PREFECTURE_OPTIONS,
                "error": f"DB保存に失敗しました: {e}",
                "form": {
                    "title": title, "birth_date": birth_date, "birth_time": birth_time,
                    "prefecture": prefecture, "gender": gender,
                },
            },
            status_code=500,
        )
    return RedirectResponse(f"/admin/yaml/result/{token}", status_code=303)


@app.get("/admin/yaml/result/{token}", response_class=HTMLResponse)
def admin_yaml_result(request: Request, token: str):
    chart = _load_chart_or_404(token)
    base_url = _public_base_url(request)
    return templates.TemplateResponse(
        "admin_result.html",
        {
            "request": request,
            "token": token,
            "chart": chart,
            "chart_url": f"{base_url}/chart/{token}",
            "yaml_url": f"{base_url}/chart/{token}.yaml",
            "prompt_url": f"{base_url}/chart/{token}/prompt.txt",
        },
    )


# ─── 共通ヘルパー ────────────────────────────────────────────────

def _public_base_url(request: Request) -> str:
    env_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if env_url:
        return env_url
    base_url = str(request.base_url).rstrip("/")
    if base_url.startswith("http://chart.nanami-astro.com"):
        base_url = base_url.replace("http://", "https://", 1)
    return base_url


def _load_chart_or_404(token: str) -> dict:
    chart = pg_store.get_chart(token)
    if not chart:
        raise HTTPException(status_code=404, detail="chart not found")
    return chart
