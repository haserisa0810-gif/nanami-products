from __future__ import annotations

from services.birth_time import BIRTH_TIME_ACCURACY_NOTE

TRANSIT_DATE_GUIDANCE = (
    '- today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。',
    '- 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。',
    '- next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。',
    '- 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。',
)

WESTERN_PROMPT = """あなたは西洋占星術の鑑定者です。以下のYAMLは、天体計算済みの出生図データです。

重要ルール:
- 天体位置・ハウス・アスペクトの計算結果は変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- 断定しすぎず、傾向・使い方・活かし方として表現してください。
- 一般論だけではなく、配置同士のつながりから具体的に読んでください。
- このYAMLは出生図の基礎データです。後からトランジット追加YAMLが渡された場合は、再計算せず、この出生図を土台に現在や今後の流れを重ねて読んでください。

出力してほしい内容:
- 全体像
- 才能・強み
- つまずきやすいパターン
- 仕事・活動の向き
- 人間関係の傾向
- 今後の活かし方

以下のYAMLを読み込んで鑑定してください。
"""

WESTERN_TRANSIT_PROMPT_TEMPLATE = """あなたは西洋占星術の鑑定者です。以下のYAMLは、{data_description}を含む計算済みデータです。

重要ルール:
- 天体位置・ハウス・アスペクト・トランジットの計算結果は変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- 断定しすぎず、傾向・使い方・活かし方として表現してください。
- 出生図を土台に、{transit_instruction}をつなげて読んでください。
- 月は朝・昼・夜の動きが入っています。日内の変化を読む時に参照してください。
- transitデータは「現在の流れ」の根拠として使ってください。
- moon_timepoints は「朝・昼・夜」の日内の使い方の根拠として使ってください。
- 今後数日の動きは、トランジットのタイトなアスペクトを優先して判断してください。
- transiting_bodies[].natal_house は出生図カスプに対する在住ハウスです。mundane_house はその時刻のマンデンハウスなので、出生図への解釈根拠にしないでください。
- today.selected_date を基準日として扱い、next_31_days_summary 内の日付が基準日より前の場合は、「今後の予定」ではなく「過去の流れ・振り返り」として扱ってください。
- 「動きやすい日」「注意したい日」には、today.selected_date 以降の日付を優先して出力してください。
- next_31_days_summary に過去日しか存在しない場合は、過去日を無理に未来の予定として書かず、「この期間に出た違和感や発想は今後の参考になる」などの振り返り表現にしてください。
- 当日以降の判断は today と next_few_days を優先し、next_31_days_summary は補助として使ってください。
- 「良い・悪い」ではなく、「どう使うとズレにくいか」を優先して書いてください。
- 「ラッキー」などの軽い表現は避け、具体的な行動ヒントに置き換えてください。

出力してほしい内容:
- 全体像
- 才能・強み
- つまずきやすいパターン
- 仕事・活動の向き
- 人間関係の傾向
- 今後31日間の流れ
- 動きやすい日・注意したい日
- 現在の流れ（トランジット）
- 今日の使い方（朝・昼・夜）
- 今後数日の動き
- 今後の活かし方

以下のYAMLを読み込んで鑑定してください。
"""

WESTERN_FULL_PROMPT = WESTERN_TRANSIT_PROMPT_TEMPLATE.format(
    data_description="出生図・小惑星・31日分のトランジット",
    transit_instruction="小惑星と今後31日分のトランジット",
)

SHICHUSUIMEI_PROMPT = """あなたは四柱推命の鑑定者です。以下のYAMLは、四柱・蔵干・十神・十二運・五行バランス・大運・流年・刑冲合害・神殺を含む計算済みデータです。

重要ルール:
- 四柱推命の計算結果は変更しないでください。
- 生年月日から再計算しないでください。
- YAML内の計算結果を唯一の根拠として解釈してください。
- systems.western が null の場合、西洋占星術の解釈はしないでください。
- 断定しすぎず、傾向・使い方・活かし方として表現してください。
- 日干、月令、五行、十神、十二運、身強身弱スコア、空亡（旬空）、大運、流年、刑冲合害、神殺のつながりから具体的に読んでください。
- 神殺は補助情報として扱い、命式全体・大運・流年より優先しすぎないでください。
- 神殺データがYAMLにない場合は、神殺の項目は無理に作らずスキップしてください。
- 流年は今年の時事性として扱い、命式・大運との関係を優先して読んでください。

出力してほしい内容:
- 命式の全体像
- 日干と五行バランス
- 才能・強み
- つまずきやすいパターン
- 仕事・活動の向き
- 人間関係の傾向
- 大運の流れ
- 今年の流年と刑冲合害から見たテーマ
- 天乙貴人・文昌・天徳が示す補助的な強み
- 今後の活かし方

以下のYAMLを読み込んで鑑定してください。
"""


def ensure_transit_date_guidance(prompt: str) -> str:
    if all(line in prompt for line in TRANSIT_DATE_GUIDANCE):
        return prompt
    guidance = "\n".join(line for line in TRANSIT_DATE_GUIDANCE if line not in prompt)
    for marker in ("\n出力してほしい内容:", "\n以下のYAMLを読み込んで"):
        if marker in prompt:
            return prompt.replace(marker, f"\n{guidance}\n{marker}", 1)
    return prompt.rstrip() + "\n" + guidance + "\n"


def build_prompt(
    *,
    include_shichusuimei: bool = False,
    include_asteroids: bool = False,
    include_transit: bool = False,
    birth_time_accuracy: str = "exact",
    interpretation_flags: dict | None = None,
) -> str:
    if include_shichusuimei and not include_asteroids and not include_transit:
        prompt = SHICHUSUIMEI_PROMPT
    elif include_transit:
        if include_asteroids:
            data_description = "出生図・小惑星・31日分のトランジット"
            transit_instruction = "小惑星と今後31日分のトランジット"
        else:
            data_description = "出生図・31日分のトランジット"
            transit_instruction = "今後31日分のトランジット"
        prompt = WESTERN_TRANSIT_PROMPT_TEMPLATE.format(
            data_description=data_description,
            transit_instruction=transit_instruction,
        )
    else:
        prompt = WESTERN_PROMPT
    flags = interpretation_flags or {}
    if birth_time_accuracy in {"unknown", "approximate"} or flags.get("use_houses_as_reference_only"):
        prompt = prompt.replace("以下のYAMLを読み込んで鑑定してください。", BIRTH_TIME_ACCURACY_NOTE + "\n\n以下のYAMLを読み込んで鑑定してください。")
    return prompt.strip() + "\n"
