from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_remember_checkbox_keeps_native_checkbox_dimensions() -> None:
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")

    assert '.api-admin-token-save input[type="checkbox"]' in css
    assert "height: 20px;" in css
    assert "width: 20px;" in css
    assert "appearance: auto;" in css


def test_token_storage_reports_success_and_empty_token_error() -> None:
    html = (ROOT / "templates" / "test_site.html").read_text(encoding="utf-8")

    assert "管理トークンをこの端末に保存しました。" in html
    assert "先に管理トークンを入力してから保存を選択してください。" in html
    assert "保存した管理トークンを読み込みました。" in html
    assert 'localStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, token)' in html
    assert 'localStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY)' in html
    assert 'aria-live="polite"' in html
