# 四柱推命 0.6.0: 伏吟・反吟・天干冲（special_relations）

2026-10-12 Claude Code 実装。ブランチ `claude/shichu-special-relations`（ベース `47896d0`）。
nanami-astro フェーズ2（`docs/CODEX_TASK_shichu_timing_phase2.md`、2026-07-14）の設計を nanami-products へ移植・適応した。背景と優先順位は `docs/claude_shichu_depth_roadmap_20261012.md`（リポジトリ本体側の未コミット資料）。

## 範囲と設計判断

- **追加したのは伏吟・反吟（天剋地冲）・天干冲の検出のみ**。astro の `detect_cross_interactions`（干合・支合・冲・刑・害・破・三合半会のクロス検出）は移植していない。products では `shichusuimei_structure.analyze_luck` の `interactions_with_natal` が大運・流年について同等の対関係を既に収録しており、丸ごと移すと同じ関係が二重収録になり原本YAMLが肥大化するため。
- **天干冲の単独記録（`stem_clash_v1`）は products 側の追加**。astro では天干冲表は反吟の構成要素のみだった。表自体は astro と同一の4組（甲庚・乙辛・丙壬・丁癸、戊己なし）で、lunar_python 1.4.8 `CHONG_GAN_4` との一致を照合済み（`docs/claude_shichu_calc_verification_20261012.md` G節）。反吟が成立した柱には天干冲を重複記録しない。
- **時柱の扱い**: astro の `provisional` フラグ方式ではなく、products 0.5.0 の方針（時刻不明・推定時は時柱を関係検出から除外）に合わせた。
- 方合（directional）は products に対系統ごと存在しないため今回見送り（ロードマップの別判断）。
- 既存キーの変更なし・追加キーのみ。`ENGINE_VERSION` を `0.6.0` に。

## 追加キー

| 位置 | キー | 内容 |
|---|---|---|
| `normalized_data.daiun.items[]` | `special_relations_natal` | 各大運×原局（scope `daiun_natal`） |
| `normalized_data.annual_fortune` | `special_relations_natal` / `special_relations_daiun` | 作成時流年×原局／×現大運（`ryunen_natal` / `ryunen_daiun`）。大運未確定（性別未指定）時は後者は空 |
| `normalized_data.annual_forecasts.items[]` | `special_relations_natal` | 各年流年×原局 |
| `…items[].daiun_contexts[]` | `special_relations_daiun` | 各年流年×対応大運 |
| `input.assumptions` | `special_relations_rules` | 採用規則の明文（伏吟=干支一致、反吟=天干冲＋地支冲、天干冲単独は stem_clash、反吟成立柱に重複記録しない） |

要素の形は astro と同形: `{rule_id, type, category, scope, pillars, members, status, tags, detail}`。`rule_id` は `fukugin_v1` / `hangin_v1` / `stem_clash_v1`。タグのみで解釈文は入れない。

## 変更ファイル

- `services/shichu_special_relations.py`（新規）: 表と検出関数。六冲表は循環import回避のため再掲し、同一性をテストで担保。
- `services/shichusuimei_calc.py`: 検出の組み込み、`ENGINE_VERSION 0.6.0`、assumptions の規則明文。
- `services/prompt_builder.py` / `services/shichusuimei_prompt_rules.py`（EN/ES/DE）: 「伏吟＝反復・強調、反吟・天干冲＝転換・動揺の材料。単独で吉凶を断定しない。キーが無い旧YAMLでは補完しない」を全経路の共通ガードへ追加。
- `tests/test_shichu_special_relations.py`（新規・11件）: 表の固定・エンジン表との同一性、伏吟/反吟/天干冲の成立・不成立（戊己の非成立、重複記録なし）、統合出力の全位置、60年一巡の月柱伏吟（1972-06-10×流年丙午）、年柱反吟（壬子×丙午）、時刻不明時の時柱除外、性別未指定時の空、既存キー保持、NP-SF addonへの伝播、engine_version。
- `tests/test_shichusuimei_overseas_engine.py`: engine_version の固定文字列3箇所を `core.ENGINE_VERSION` 参照に変更（文字列以外は不変更）。

## 検証（2026-10-12、ローカル）

- 新規テスト **11 PASS**。
- 四柱・プロンプト・YAML・addon・chart関連15ファイル **1,337 PASS＋9 subtests**（68.35秒）。
- 全体回帰: **2,161 PASS・85 skip・48 FAIL**。48件は `test_notification_compatibility_audit.py`（36）・`test_product_catalog.py`（9）・`test_unverified_product_warning.py`（3）で、**改変なしの素の `47896d0` で同一の48件が失敗することを別worktreeで確認済み**（本変更起因ゼロ。O03隣接の既存事象。`docs/CODEX_TASK_product_catalog_unverified_9fail.md` 参照）。
- before/after 同値確認: 代表3ケース（確定時刻・60年一巡・時刻不明×性別未指定）で、新キーと `engine_version` を除く全出力が 0.5.0（素の `47896d0`）と**完全一致**。差はエフェメリスのディレクトリパス（実行環境値）のみ。
- `git diff --check` PASS。`scripts/check_agent_governance.py` は `47896d0` に存在しないため未実行。

## 限界・未実施

- 伏吟・反吟の検出規則そのものの流派妥当性は、astro フェーズ2レビュー時の設計合意に依拠する（本実装はその移植）。
- 方合・三合完成の `completed_by` 明示は未移植（analyze_luck の三合収録で代替。必要なら別判断）。
- 実AIによる新キーの読み取り品質は未評価。
- commit・push・デプロイ・本番反映は未実施。
