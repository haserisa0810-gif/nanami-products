"""四柱推命FULL版の鑑定指示文（日本語）。

基本版と共通の指示文は「出力してほしい内容」が基本版の章立てのままで、FULL版の深掘り
（表と裏・通根・才能の組み合わせ・宮位・用神）が章として出にくかった。FULL版だけ、
章ごとに読むYAMLの場所を示し、その命式に当てはまる注意だけを入れる。計算は行わない。
"""
from __future__ import annotations

from typing import Any

TIME_SENSITIVE = {"unknown", "approximate", "estimated", "provisional"}
SHINSATSU_NAMES = ("天乙貴人", "文昌", "天徳")


def _shichu(doc: dict[str, Any]) -> dict[str, Any]:
    return ((doc.get("systems") or {}).get("shichusuimei") or {}) if isinstance(doc, dict) else {}


def is_full_shichu_doc(doc: dict[str, Any]) -> bool:
    """四柱推命単独のFULL版原本か（年運アドオンを統合した原本を含む）。"""
    if not isinstance(doc, dict):
        return False
    systems = doc.get("systems") or {}
    if not isinstance(systems, dict) or systems.get("western"):
        return False
    shichu = _shichu(doc)
    options = ((doc.get("product") or {}).get("options") or {})
    if shichu.get("edition") == "full" or options.get("shichusuimei_edition") == "full":
        return True
    return bool((shichu.get("normalized_data") or {}).get("structural_analysis"))


def _accuracy(doc: dict[str, Any]) -> str:
    return str((doc.get("birth_time") or {}).get("accuracy")
               or (doc.get("input") or {}).get("birth_time_accuracy") or "exact")


def _shinsatsu_hits(nd: dict[str, Any]) -> list[str]:
    stars = ((nd.get("shinsatsu") or {}).get("stars") or [])
    return [s.get("name_ja") for s in stars if isinstance(s, dict) and s.get("hit") and s.get("name_ja")]


def _has_special_relations(nd: dict[str, Any]) -> bool:
    items = (nd.get("daiun") or {}).get("items") or []
    if any(item.get("special_relations_natal") for item in items if isinstance(item, dict)):
        return True
    annual = nd.get("annual_fortune") or {}
    return bool(annual.get("special_relations_natal") or annual.get("special_relations_daiun"))


def year_section(mode: str, years: list[int] | None = None) -> str:
    """7章（年の運勢）の指示。mode は complete / basic / selected。"""
    common = "annual_fortune は原本作成時の流年で、会話時点の「今年」に置き換えないでください。"
    if mode == "basic":
        return ("7. 原本作成時の年のテーマ — common の annual_fortune（effective_year の年）を、命式・その年の大運との"
                f"関係から読む。{common}年ごとの詳しい年運はこのデータに含まれていません（鑑定ページで年を選ぶと追加できます）。")
    if mode == "selected":
        label = "・".join(map(str, years or [])) + "年" if years else "選んだ年"
        return (f"7. {label}の運勢 — year_selection.included_years の年について、selected_base_forecasts の各年"
                "（effective_year）の natal_analysis（命式との関係）と daiun_contexts（その年の大運との関係）、"
                "special_relations_natal を読む。年は立春から翌立春まで。大運の切り替わりの年（daiun_boundary_in_window）は"
                f"両方の大運を示し、交運日を断定しない。{common}")
    return ("7. 年ごとの運勢 — normalized_data.annual_forecasts.items の各年（effective_year）の natal_analysis と"
            "daiun_contexts を読む。年は立春から翌立春まで。収録年が多いので、聞かれた年・今年・来年を中心にまとめ、"
            f"ほかの年は要点だけにする。{common}")


def build_full_shichu_prompt(doc: dict[str, Any], *, years_mode: str = "complete",
                             years: list[int] | None = None) -> str:
    nd = _shichu(doc).get("normalized_data") or {}
    daiun = nd.get("daiun") or {}
    status = str(daiun.get("status") or "")
    time_unknown = _accuracy(doc) in TIME_SENSITIVE
    shinsatsu = _shinsatsu_hits(nd)

    palace = ("4. 宮位から見る暮らし — 年柱＝家系・幼少期・外の社会、月柱＝仕事・社会での役割・両親、"
              "日支＝本人の私生活・配偶者、時柱＝子ども・部下・晩年・内面の志向、という伝統的な対応で、"
              "仕事・家庭・人間関係を読む（宮位の取り方には流派差があることを一言添える）。")
    if time_unknown:
        palace += "出生時刻が不明・推定のため、時柱の宮位は使わない。"
    luck = ("6. 大運の流れ — daiun.items の各期（kanshi・approx_start_at〜approx_end_at）と items[].structural_analysis を、"
            "今の大運と次の大運を中心に読む。切り替わりの時期は近似で、交運日を断定しない。")
    if _has_special_relations(nd):
        luck += ("special_relations_natal の伏吟（同じ干支の重なり）はテーマの反復・強調、反吟（天剋地冲）と天干冲は"
                 "転換・動揺の材料として、単独で吉凶を決めずに読む。")
    chapters = [
        "1. 命式の全体像 — pillars・day_master・月支（生まれた季節）、structural_analysis.day_master_support"
        "（日主の強さ）、useful_god_analysis.useful_god_selection（用神）を最初に短くまとめる。",
        "2. 性格の表と裏 — ten_gods.pillars（天干の十神＝外に見える振る舞い・役割）と、ten_gods.hidden_stems・"
        "main_hidden_stems.month（蔵干・月支の本気＝内側の動機・本音・土台）を対比する。"
        "structural_analysis.roots_and_exposure で、根の強い性質（実際に発揮しやすい）、根の弱い性質（表に出ても"
        "続きにくい）、透干した蔵干（内面の資質が表に出やすい）を分ける。",
        "3. 才能の組み合わせ — structural_analysis.ten_god_flow の各 label を、両側の通根と ten_god_strength から"
        "「活かしやすい組み合わせ」と「ぶつかりやすい組み合わせ」に分けて説明する。both_present は配置の併存で、"
        "成立の断定ではない。",
        palace,
        "5. 用神と喜忌の活かし方 — useful_god_selection の useful_god を「この鑑定の用神」としてはっきり伝え、"
        "basis を理由、favorable_elements を喜、unfavorable_elements を忌として、日常での活かし方に落とし込む。"
        "取り方は method_label のとおり。alternatives は「流派によっては〜を重視する見方もあります」と一言だけ添える。",
        luck,
        year_section(years_mode, years),
        "8. これからの活かし方 — ここまでの章をまとめ、具体的な行動のヒントを3つほど挙げる。",
    ]

    cautions = []
    if time_unknown:
        cautions.append("出生時刻が不明・推定のため、時柱は参考値です。年・月・日の三柱を根拠にし、時柱の蔵干・"
                        "十二運・空亡・神殺・合冲を確定根拠にしないでください（structural_analysis は時柱を除いて計算済み）。")
    if status == "undetermined_gender":
        cautions.append("性別が未指定のため、大運は計算していません。女性へ補完せず、6章は「性別が分かれば大運を出せる」と"
                        "伝え、大運や起運を推測しないでください。命式と年ごとの natal_analysis は使えます。")
    if status in {"undetermined_month_pillar", "undetermined_year_pillar"}:
        cautions.append("生まれた日に節入り・立春があり、出生時刻で命式が変わるため、大運と年ごとの運勢を保留しています。"
                        "daiun.candidates は参考計算で、確定根拠にしないでください。時刻が分かれば確定できます。")
    if shinsatsu:
        cautions.append("神殺（" + "・".join(shinsatsu) + "）は補助情報として、関係する章に一言添える程度にしてください。")

    lines = [
        "あなたは四柱推命の鑑定者です。以下のYAMLは、この人の命式・大運・年運と、命式の構造分析まで計算済みの"
        "データ（四柱推命FULL版）です。計算はやり直さず、YAMLの値だけを根拠に、専門用語はかみくだいて鑑定してください。",
        "",
        "【鑑定の章立て】次の順に書いてください。読む場所は systems.shichusuimei.normalized_data からの位置です"
        + ("（このデータでは common の中にあります）。" if years_mode in {"basic", "selected"} else "。"),
        *chapters,
        "",
        "【書き方】",
        "- 記述ごとに【計算】（YAMLの値そのもの）【伝統的解釈】（四柱推命の一般的な読み）【推論】"
        "（それらを組み合わせた鑑定者の解釈）を付けて区別してください。",
        "- 具体的な出来事・行動・人間関係は断定せず、本人に思い当たるかを確かめる形にしてください。",
        "- 吉凶を一律に決めず、強みと注意点の両方を書いてください。",
        "- 日柱・時柱は出生地の現地暦日と日替わり方式（input.assumptions.day_boundary_rule）で計算済みです。"
        "読み替えないでください。",
        "- 計算結果を変更・再計算せず、YAMLに無い項目は補わないでください。合・三合があっても "
        "combination_screening の条件を見て、合化を断定しないでください。",
        "- 用神は「未確定」「データが不足」と書かないでください。confidence・conflicting_rules・"
        "methodology.limitations は内部の注記で、「計算が未完成」という説明には使わないでください。",
    ]
    if cautions:
        lines += ["", "【この命式の注意】", *("- " + c for c in cautions)]
    return "\n".join(lines) + "\n"
