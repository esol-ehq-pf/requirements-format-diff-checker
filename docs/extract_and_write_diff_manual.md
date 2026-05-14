# extract_and_write_diff.py 詳細マニュアル

## 概要

旧解析結果フォルダと新解析結果フォルダを比較し、差分エントリを自動抽出して  
Excel の『Output 差分』シートに転記するツールです。

---

## 1. ユーザーワークフロー

```
[事前準備]
  1. 旧解析結果ディレクトリを用意する
     （例: input/scheduling_requirement_check_analysis_result）
  2. ver3 ツールで再解析した新解析結果ディレクトリを用意する
     （例: input/ver1_m02_AP_再解析結果/output）
  3. 差分管理 Excel ファイルを用意する
     （例: input/過去プロジェクト(ver1_ver2_ver2.1)の要件ファイルフォーマット変更.xlsx）
        ※ Excel には「Output差分」シートと「リンク」シートが必要

        ┌──────────────────────────────────┐
        │ 「Output差分」シート列構成（4行目〜）│
        │ A: No    B: フォルダ  C: ファイル  │
        │ D: 差分概要  E: 旧値  F: 新値      │
        │ G: リンク  H: project  I: variant  │
        │ J: 推定原因                         │
        └──────────────────────────────────┘

[ドライラン: 書き込み前の確認]
  4a. --dry-run オプション付きで実行
      → Excel を変更せず、抽出される差分エントリ一覧を標準出力に表示する

[本番実行: Excel への転記]
  4b. --dry-run なしで実行
      → 同バリアントの既存エントリを削除し、抽出結果を末尾に追記する

[検証]
  5. verify_diff.py で転記内容の品質ゲート検証を実施する
     （詳細は README.md 参照）
```

---

## 2. 使い方（CLI リファレンス）

```bash
python3 scripts/extract_and_write_diff.py \
    --project <プロジェクト名> \
    --variant <バリアント名> \
    --old     <旧解析結果ディレクトリ> \
    --new     <新解析結果ディレクトリ> \
    --xlsx    <Excelファイルパス> \
    [--dry-run]
```

### 引数

| 引数 | 必須 | 説明 | 例 |
|------|------|------|----|
| `--project` | ✅ | プロジェクト名 | `ver1`, `ver2`, `ver2.1` |
| `--variant` | ✅ | バリアント名 | `m02`, `b01`, `m01` |
| `--old` | ✅ | 旧（過去解析済み）結果ディレクトリのパス | `input/scheduling_requirement_check_analysis_result` |
| `--new` | ✅ | 新（ver3 再解析）結果ディレクトリのパス | `input/ver1_m02_AP_再解析結果/output` |
| `--xlsx` | ✅ | Output 差分シートを含む Excel ファイルパス | `input/過去プロジェクト(...).xlsx` |
| `--dry-run` | ➖ | 指定すると Excel を書き換えず、抽出結果のみ表示する | — |

### 終了コード

| コード | 意味 |
|--------|------|
| `0` | 正常完了 |
| `1` | パスが存在しないエラー |

### 実行例

```bash
BASE=work/format-change

# ドライラン（確認のみ）
python3 "$BASE/scripts/extract_and_write_diff.py" \
    --project ver1 \
    --variant m02 \
    --old  "$BASE/input/scheduling_requirement_check_analysis_result" \
    --new  "$BASE/input/ver1_m02_AP_再解析結果/output" \
    --xlsx "$BASE/input/過去プロジェクト(ver1_ver2_ver2.1)の要件ファイルフォーマット変更.xlsx" \
    --dry-run

# 本番実行（Excel に転記）
python3 "$BASE/scripts/extract_and_write_diff.py" \
    --project ver1 \
    --variant m02 \
    --old  "$BASE/input/scheduling_requirement_check_analysis_result" \
    --new  "$BASE/input/ver1_m02_AP_再解析結果/output" \
    --xlsx "$BASE/input/過去プロジェクト(ver1_ver2_ver2.1)の要件ファイルフォーマット変更.xlsx"
```

---

## 3. 内部処理ワークフロー

```
main()
  │
  ├─ [入力検証] 旧/新ディレクトリ・xlsx が存在するか確認（非存在なら exit=1）
  │
  ├─ extract_all(old_dir, new_dir)          ← 全差分抽出
  │   │
  │   ├─ extract_input_info()               [1] input_info.txt
  │   ├─ extract_image_diffs()              [2] グラフ画像ディレクトリ群
  │   ├─ extract_cpuload_requirements() ×2  [3] before/after_cpuload_requirements.csv
  │   ├─ extract_requirements_csv() ×2      [4] before/after_requirements.csv
  │   ├─ extract_budget_csv() ×1            [5] before_budget.csv
  │   ├─ extract_input_data_csv() ×2        [6] input_data_ba/igr.csv
  │   ├─ extract_tsync_csv() ×2             [7] before/after_csv_data_tsync_PlusBA.csv
  │   ├─ extract_processing_time_result()   [8] processing_time_result.csv
  │   ├─ extract_schedule_result()          [9] schedule_result.csv
  │   └─ extract_schedule_fail_list()       [10] schedule_result_fail_list.csv
  │
  └─ write_to_excel(xlsx, project, variant, entries, dry_run)
      │
      ├─ [dry_run=True]  抽出結果を標準出力に表示して終了
      └─ [dry_run=False] 既存エントリ削除 → 末尾に追記 → xlsx 保存
```

---

## 4. 対象ファイルと差分抽出ロジック詳細

### [1] `input_info.txt` — `extract_input_info()`

旧/新で内容が異なる場合に以下の **2 件を固定出力** します。

| 差分概要 | 新値（説明） | 推定原因 |
|----------|------------|---------|
| 入力ファイルの差分 | 要件チェックツール差分 | ver3 ツールを用いたことによる差分 |
| 入力ファイルの差分 | 要件ファイル差分 | ver3 フォーマットを使用した要件ファイルに置き換わったことによる差分 |

> ファイルが一致している場合は 0 件。

---

### [2] グラフ画像ディレクトリ群 — `extract_image_diffs()`

対象ディレクトリ（`PASS` / `FAIL` サブフォルダ）:

- `processing_load_duration_graph`
- `Sequence_duration_graph`
- `SWC_budget_duration_graph`
- `WakeupInterval_graph`

**判定ロジック:**

```
削除された画像 = old にあって new にない画像
追加された画像 = new にあって old にない画像

削除画像に対し、追加画像との名前類似度（SequenceMatcher）を計算:
  類似度 ≤ 0.7  → 「ファイル消失」エントリを生成
  類似度 > 0.7  → 「画像差分」（リネーム）エントリを生成
```

| 差分概要 | 説明 |
|----------|------|
| ファイル消失 | 旧にあり新にない、かつ類似画像も見つからない場合 |
| 画像差分 | 旧→新でファイル名が類似度 0.7 超で変化（リネーム）した場合 |

---

### [3] `before/after_cpuload_requirements.csv` — `extract_cpuload_requirements()`

- **PF_window 追加**: 新 CSV に `PF_window` を含む DisplayName/NodeName が追加された場合  
  → 差分概要「TaskID の追加」、推定原因「infsimyml のフォーマット変更(1-③)」
- **NodeName の変化**: TaskID をキーに旧→新で NodeName が変化した場合  
  → 差分概要「NodeName の変化」、推定原因「infsimyml のフォーマット変更(1-①)」

---

### [4] `before/after_requirements.csv` — `extract_requirements_csv()`

| 検出内容 | 差分概要 | 推定原因 |
|----------|---------|---------|
| 新 CSV にキーが追加（例: Fsync 用 Target キー） | キーの追加 | chksimyml フォーマット変更(2-②) |
| Sequence/Sender/Receiver/FirstTask/SecondTask 列の値が変化 | Sequence/Sender/.../SecondTask の変化 | chksimyml フォーマット変更(2-①) |
| RequirementId 列の値が旧→新で変化 | RequirementId の変化 | chksimyml フォーマット変更(2-③) |
| RequirementOwner 列の値が旧→新で変化 | RequirementOwner の変化 | （原因なし） |

> `temp/` サブディレクトリ内のファイルを対象とします。Excel への folder 列は `tmp` と記録します。

---

### [5] `before_budget.csv` — `extract_budget_csv()`

旧/新で内容が異なる場合に以下の **1 件を固定出力** します。

| 差分概要 | 新値 | 推定原因 |
|----------|------|---------|
| TaskList の変化 | TaskList が Node 名で統一 | budget.yaml フォーマット変更(4-②) |

---

### [6] `input_data_ba.csv` / `input_data_igr.csv` — `extract_input_data_csv()`

| 検出内容 | 差分概要 |
|----------|---------|
| `pf_1ms_base` 行が新 CSV に存在しない | pf_1ms_base 行の消失 |
| `pf_1ms_mid` 行が新 CSV に存在しない | pf_1ms_mid 行の消失 |
| pf_1ms を除いた行で `start_clock_ms` 同一・`node` 異なるペアが存在 | Node の順序入れ替わり（N 件） |

---

### [7] `before/after_csv_data_tsync_PlusBA.csv` — `extract_tsync_csv()`

| 検出内容 | 差分概要 | 推定原因 |
|----------|---------|---------|
| `pf_1ms_base` 行が新 CSV に存在しない | pf_1ms_base 行の消失 | — |
| `pf_1ms_mid` 行が新 CSV に存在しない | pf_1ms_mid 行の消失 | — |
| pf_1ms 以外の行で差分あり（SequenceMatcher） | mid 行の時刻値変化 | infsimyml フォーマット変更(1-③) |

---

### [8] `processing_time_result.csv` — `extract_processing_time_result()`

新 CSV に `PF_window` を含む行が追加された場合:

| 差分概要 | 新値 | 推定原因 |
|----------|------|---------|
| TaskID の追加 | PF_window が追加 | infsimyml フォーマット変更(1-③) |

---

### [9] `schedule_result.csv` — `extract_schedule_result()`

| 検出内容 | 差分概要 | 推定原因 |
|----------|---------|---------|
| `id` または `name` 列の値が旧→新で変化（重複統合あり） | id/name の変化 | chksimyml フォーマット変更(2-③)（先頭エントリのみ） |
| `etc` 列の値が旧→新で変化 | etc の変化 | chksimyml フォーマット変更(2-①) |

> `id`/`name` の変化は末尾の `-NN` を除いた親名称が同一のペアを 1 件に統合します。

---

### [10] `schedule_result_fail_list.csv` — `extract_schedule_fail_list()`

1 行目（ヘッダ）または 2 行目（サブヘッダ）が旧→新で変化した場合:

| 差分概要 | 新値 | 推定原因 |
|----------|------|---------|
| 列ヘッダの変化 | SWC 名/Node 名に統一 | chksimyml フォーマット変更(2-①) |

---

## 5. Excel への書き込み仕様

| Excel 列 | 内容 |
|----------|------|
| A | No（前行の A 列 +1 の数式） |
| B | フォルダ名（`-` / `tmp` / グラフディレクトリ名） |
| C | ファイル名 |
| D | 差分概要（`ALLOWED_DIFF_TYPES` の値） |
| E | 旧値 |
| F | 新値 |
| G | リンク（固定文字列: `過去プロジェクト(ver1/ver2/ver2.1)の 要件ファイルフォーマット変更`） |
| H | project（`--project` 引数値） |
| I | variant（`--variant` 引数値） |
| J | 推定原因（`None` の場合は空白） |

**既存エントリの扱い:** 同 project/variant の行が既に存在する場合、全行を削除してから末尾に追記します（上書き相当）。

---

## 6. 注意事項

- 本スクリプトは **ver1/m02 で観測された差分パターン** を元に設計しています。  
  他バリアントで異なるパターンが存在する場合、抽出漏れが発生する可能性があります。
- `--dry-run` で事前確認してから本番実行することを推奨します。
- `input/` 配下のデータファイルは Git 管理対象外です（`.gitignore` 参照）。
- Excel ファイルへの書き込みは `openpyxl` が使用するため、Excel を開いたまま実行しないでください。
