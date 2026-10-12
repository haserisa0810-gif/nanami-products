# 計算ロジック検証

## 正確性と整合性を分けた方法

既存テストは891件合格しましたが、同じコード・同じSwiss Ephemerisを同じ条件で呼び直す検証は独立精度確認と数えません。今回の正確性確認には、別実装の暦、国立天文台の暦要項、JPL Horizons、および独立に組み立てた球面幾何・Placidus方程式を使いました。用神・身強など流派／係数に依存する指標は、数値が一貫していることと占術上の妥当性を区別しています。

環境：Windows、Python 3.14、Swiss Ephemeris `2.10.03`、`lunar_python 1.4.8`。独立ライブラリはリポジトリ外の試作用ディレクトリへ配置し、アプリのrequirementsは変更していません。今回の天文チェックでSwiss返却flagはSWIEPH（2）、ローカル天文ファイルあり。全商品のあらゆるfallbackを検証したものではありません。

## 四柱推命

| 項目 | 状態 | 方法・結果・限界 |
|---|---|---|
| 節入り時刻 | PASS | 2026年の12「節」を国立天文台のJST分表示に照合。許容60秒、最大差28.015136秒 |
| 月柱／立春年柱切替 | PASS | 12節の±2分で月が切替。年は立春のみ切替。全年代は未実施 |
| 日柱 | FAIL：P0 | 独立暦の6日付×5地域=30条件中15不一致。UTCオフセット0以下で+1日。JST・Sydneyは一致 |
| 日替わり設定 | FAIL：P1 | 23時設定が23時から翌日ではなく、0時台を前日扱い。falseは0時切替だがUIは1時と表記 |
| 時柱 | PASS（子刻以外）／未実施（子刻の採用方式） | 独立暦から10日干×11時間帯を照合。表は一致。日柱バグのある地域では派生時柱も影響 |
| 蔵干 | PASS（集合）／未実施（全重み・順序の流派妥当性） | 12支の蔵干集合を別実装と照合。巳の配列順は異なり、中気・余気の固定重みへの影響は別評価が必要 |
| 十神 | PASS | 相生相剋と陰陽から独立構成した10干×10干の100組 |
| 十二運 | PASS（照合範囲） | 独立暦による60日干支×午、追加10干×11支。陰干逆行・火土同根。子支全表の実行照合は未実施（Claude手照合のみ） |
| 空亡 | PASS | 全60干支の日柱旬空を独立暦と照合。元の日柱が誤る入力は別問題 |
| 神殺 | PASS（既存テスト・Claude表確認）／未実施（独立実行全表） | 天乙・文昌・天徳等の表読解。流派差のある表は誤りと断定しない |
| 五行集計・季節補正 | PASS（出力契約）／未実施（係数の占術校正） | 原局と運の参照値を区別。単純合算を吉凶確定とはしない。係数の唯一の正解は認定しない |
| 月令と日主 | FAIL（旧指標の説明）：P2 | 甲日主×午月が「中立・直接関係弱い」、木生火の洩気を明示していない。正しい点数までは未検証 |
| 通根・透干・十神配置／活性 | PASS（既存整合性・不確実性）／未実施（全組合せ独立照合） | 蔵干・位置・重みを計算材料として出力。格局／用神を断定しない |
| 格局・用神・喜忌 | PASS（断定防止）／未実施（占術的候補の正確性） | definitive_useful_godはnull、method・confidence・limitations保持。試験候補を確定する処理は確認されない |
| 食傷生財など十神の流れ | PASS（候補・両者存在の出力契約） | both_presentを成立／金運確定としない。全解釈の正確性は未実施 |
| 合化 | PASS（不確定の保持） | サンプルのscreeningにconfirmed=false、element_change_applied=false。成立条件の占術上の完全性は未実施 |
| 大運順逆 | PASS（性別指定）／FAIL（未指定） | 陽男陰女順行の4組一致。未指定が女性に変換される |
| 起運年齢・交運日時 | PASS（近似明示・期間整合性）／未実施（厳密起運値） | 3日=1年の換算と約10年のperiod。日時はapprox_*、境界暫定を保持 |
| 大運干支連続性 | PASS | exact/unknown/approximateの各大運、60周期上の±1で連続 |
| 流年と大運の重複期間 | PASS | 立春～翌立春と近似大運の半開区間交差を独立に照合。2033年の2大運を単一確定にしない |
| 冲・六合・害 | PASS | 66地支ペア×3種類を対向・鏡映の独立規則で実行照合 |
| 刑・破・三刑・半会・三合・干合 | PASS（既存テスト＋Claude表読解）／未実施（全組合せ独立実行） | 判定対象の追跡・重複・複合関係の全網羅を合格とはしない |
| 1970年以前のWindows計算 | FAIL：P2 | 1950-07-15 13:30 JST、起運日時のdatetime.fromtimestampでInvalid argument |

参照：[国立天文台2026年暦要項](https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html)、[lunar-python公式実装](https://github.com/6tail/lunar-python)。独立ライブラリも絶対的な権威ではなく、採用規則の違いは切り分けました。日柱の反例はソースの代数解析とも一致します。

## 西洋占星術

| 項目 | 状態 | 方法・結果・限界 |
|---|---|---|
| 太陽～冥王星10天体の黄経 | PASS | JPL Horizonsの地心・見かけ・日付の黄道座標と2024-04-08 18:00 UTCで照合。許容0.02°、最大差0.0000234689964°（約0.085秒角） |
| 逆行 | PASS（検証日の10天体） | JPLの翌日との差から符号判定。留・日内反転・全年代は未実施 |
| サイン | PASS（既存テスト＋サンプル整合性） | 黄経から区分。浮動小数の360°近傍全境界は未実施 |
| ASC・MC・12カスプ | PASS（4地点56値） | 東京・Sydney・London・Reykjavikで、独立GMST／傾斜・球面幾何とPlacidus半日弧方程式を比較。許容0.03° |
| 高緯度Placidus | FAIL：P2 | 69.65°、-75°でPython wrapperが例外。対応不能の方式自体と、商品のエラー案内不足を区別 |
| アスペクト／オーブ／接近離反 | PASS（既存境界と新規有限差分） | 採用orb内で速度と微小時間差の偏差変化を比較。同じ天体計算からの契約検証であり天文位置の独立証明ではない |
| 月・ノード・Lilith等の設定 | PASS（コード設定確認）／未実施（すべての独立数値照合） | 月はJPL照合対象。ノード等は現行Swiss body ID・flagsを確認、代替独立数値なし |
| 小惑星ローカル計算 | PASS（生成／解析）／未実施（外部精度） | 実装はローカルSwissと任意fallback。未収録項目を必須扱いしない |
| FreeAstro fallback | 未実施（実サービス照合） | モック送信でtimezone／UTC offset不在を確認。サービスの期待時刻が未確認なので誤位置と断定しない |
| 短期トランジット | PASS（期間・構造）／未実施（全日全アスペクト独立精度） | 初回31日・追加38日を区別。日次sampleは正確なイベント時刻の探索とは異なる |
| 長期トランジット | PASS（実生成365日・53週次sample） | 要約とFullを解析。ピーク日付は週次近似、厳密通過時刻の精度は未実施 |
| DST・タイムゾーン | FAIL：P1 | 不存在2:30を無警告で別時刻へ対応、重複1:30のfold選択なし |
| 出生地 | PASS（既存市区町村入力契約）／未実施（全都市精度） | 購入経路に市区町村の位置解決あり。都道府県代表座標だけの入力と区別 |
| 出生時刻不明 | PASS（出生図の制約・実AI）／FAIL（transit.natal_house）：P1 | 仮置き出生ハウスが日次310/310項目に値として残る。出生図の暫定flagを消費者が参照する必要あり |
| 不正API入力 | FAIL：P2 | 日付・24:00・緯度100に400ではなく500。購入フォーム全体が同様とは断定しない |

参照：[JPL Horizons API仕様](https://ssd-api.jpl.nasa.gov/doc/horizons.html)、[Horizonsマニュアル](https://ssd.jpl.nasa.gov/horizons/manual.html)、[Swiss Ephemeris公式仕様](https://www.astro.com/swisseph/swephprg.htm)。JPL quantity31、CENTER=500@399、CSV、EXTRA_PREC、AIRLESSで比較。JPLとSwissは天文モデルの系統を共有する部分があり、独立観測による証明とはしません。JPL生応答10件を`horizons_*.json`に保存しました。

## 実行と証跡

- 主プローブ：[new_verification_results.json](new_verification_results.json)、`scripts/quality_verify_astrology.py`。442 PASS／21 FAIL。
- 追加：[followup_probe_results.json](followup_probe_results.json)、`scripts/quality_followup_probes.py`。436 PASS／9 FAIL／2 未実施。
- 終了：[final_checks.json](final_checks.json)、16 PASS。
- 既存pytest実行：`C:/Users/haser/nanami-products/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=C:/Users/haser/AppData/Local/Temp/nanami-quality-existing-20261010`。891 passed、160 subtests、5611 warnings、99.97秒。別途`node --test tests/test_shichusuimei_year_selection_ui.cjs`で6件PASS。
- 検証スクリプト自体の初期の引数名・翻訳名・メタデータキー・CRLFハッシュの不一致は調整して再実行しました。製品の不具合件数には含めません。合格するようにアプリの計算を変更したものではありません。
- スクリプトを再実行すると架空の証跡を再生成します。天文資料の取得／Claude呼出にはネットワーク・認証が必要で、本番DB接続を設定する必要はありません。既存pytestはDBをモックしたローカル試験です。
