# requirements-format-diff-checker

過去プロジェクト（ver1 / ver2 / ver2.1）の要件ファイルフォーマットを ver3 相当に統一するにあたり、  
**① ver3 ツール再解析結果** と **② 過去解析済み結果** の差分を抽出・検証する自動化ツール群です。

---

## 背景

顧客からの依頼として、過去プロジェクトの計測データに対して ver3 フォーマットの要件ファイルおよび ver3 解析ツールを用いた再解析を実施し、過去解析済み結果との差分を Excel の『Output 差分』シートに整理する作業が求められています。  
本リポジトリのスクリプトは、その差分抽出・記録・検証を自動化します。

---

## スクリプト構成

```
scripts/
  extract_and_write_diff.py   差分抽出・Excel転記ツール
  verify_diff.py              差分検証・品質ゲート判定ツール
```

### `extract_and_write_diff.py`

旧解析結果フォルダと新解析結果フォルダを比較し、差分エントリを自動抽出して Excel の『Output 差分』シートに転記します。

→ **詳細マニュアル: [docs/extract_and_write_diff_manual.adoc](docs/extract_and_write_diff_manual.adoc)** +
→ **手動実施手順書: [docs/manual_procedure.adoc](docs/manual_procedure.adoc)**

### `verify_diff.py`

Excel の『Output 差分』シートに記載された差分エントリを自動検証し、品質ゲート（QG）の総合判定を YAML レポートとして出力します。

→ **詳細マニュアル: [docs/verify_diff_manual.adoc](docs/verify_diff_manual.adoc)**

**使い方:**

```bash
python3 scripts/verify_diff.py \
  --project <プロジェクト名> \
  --variant <バリアント名> \
  --old     <旧解析結果ディレクトリ> \
  --new     <新解析結果ディレクトリ> \
  --xlsx    <Output差分シートを持つExcelファイル> \
  [--report-out <レポート出力先YAML>] \
  [--plan   <レビュー計画YAML>]
```

**終了コード:**

| コード | 意味 |
|--------|------|
| `0` | 全品質ゲート PASS |
| `1` | いずれかの品質ゲート FAIL |
| `2` | CLI 引数エラー（不正なパス等） |

---

## 対象バリアント

| プロジェクト | バリアント | 状態 |
|-------------|-----------|------|
| ver1  | m02 | 実装済み |
| ver1  | b01 | 顧客提供待ち |
| ver1  | m01 | 顧客提供待ち |
| ver2  | b01 | 顧客提供待ち |
| ver2  | m01 | 顧客提供待ち |
| ver2  | m02 | 顧客提供待ち |
| ver2.1 | b01 | 顧客提供待ち |
| ver2.1 | m01 | 顧客提供待ち |
| ver2.1 | m02 | 顧客提供待ち |

---

## 品質ゲート

| QG | 名称 | 内容 |
|----|------|------|
| QG-1 | 網羅性 | 差分ありファイルが Excel に全て記載され、差分なしファイルが誤記載されていないこと |
| QG-2 | 正確性 | 差分概要文言・フォルダ/ファイルの実在確認が全て OK であること |
| QG-3 | 推定原因形式 | 現バージョンでは自動判定対象外（常に PASS） |
| QG-4 | メタ整合性 | プロジェクト列・バリアント列・リンク列が全エントリで一致していること |

---

## ディレクトリ構成

```
.
├── scripts/                     実行スクリプト
│   ├── extract_and_write_diff.py
│   └── verify_diff.py
├── design/                      設計・仕様書（JSON）
│   ├── extract_and_write_diff_spec.json
│   ├── verify_diff_spec.json
│   ├── change_plan.json
│   └── self_review_plan.json
├── test/                        テスト仕様・実行記録
│   └── test_spec.json
└── input/                       入力データ（Git 管理対象外）
```

---

## 動作環境

- Python 3.13 以上
- 依存ライブラリ: `openpyxl`, `PyYAML`（標準ライブラリの `difflib`, `argparse`, `pathlib` を使用）

```bash
pip install openpyxl pyyaml
```
