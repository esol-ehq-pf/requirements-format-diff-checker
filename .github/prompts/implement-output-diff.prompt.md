---
mode: agent
description: output_diff.py をイテレーティブに実装・テスト・コミットする（フレームワーク→機能拡張→評価）
---

# output_diff.py 実装タスク

## 目的

`design/output_diff_spec.json` の仕様に従い、**フレームワーク先行・段階的機能拡張**のアプローチで `scripts/output_diff.py` を実装する。テストを各 Iteration で作成・実行してコミットする。このスクリプトは継続使用を前提とするため、**汎用性・保守性**を最優先とする。

## 前提情報

- **仕様書**: `design/output_diff_spec.json`
- **実装計画**: `plans/output_diff_plan.md`（調査・設計・実装・評価の詳細フェーズを記載）
- **リポジトリ**: `/home/y-shinohara/adas/work/format-change/`
- **Python バージョン**: 3.13.12（pyenv）、標準ライブラリのみ使用
- **既存スクリプト参考**: `scripts/extract_and_write_diff.py`（argparse・出力スタイルを踏襲）
- **テスト配置**: `test/test_output_diff.py`（`test/test_csv_out.py` のスタイルに準拠）

## 開発方針（汎用性・保守性）

- **関数単位の責務分離**: 比較ロジック・出力ロジック・CLI 解析を独立した関数に分離する
- **中間データ構造**: 出力形式（HTML/CSV）に依存しない `DiffEntry` dataclass を設ける
- **出力フォーマットはプラガブル**: `write_html()` / `write_csv()` を独立させ、将来の形式追加を容易にする
- **テキストエンコード検出は共通関数化**: UTF-8 → Shift-JIS → latin-1 フォールバックを一箇所に集約する
- **定数はモジュールトップに集約**: 色コード・バイナリ拡張子・列名などを変更容易にする

## イテレーション計画

計画の詳細は `plans/output_diff_plan.md` を参照。各 Iteration で「実装 → pytest → コミット」を完結させること。

| Iteration | 実装内容 | 対応 TC |
|-----------|---------|--------|
| IT-1 | フレームワーク（CLI・DiffEntry・スタブ出力） | TC-7, TC-8 |
| IT-2 | 比較ロジック（4分類・テキスト/バイナリ判定） | TC-1〜4, TC-10 |
| IT-3 | CSV 出力 | TC-6 |
| IT-4 | HTML 出力（テーブル・行色・サマリ） | TC-5 |
| IT-5 | unified diff 展開（`<details>`） | TC-9 |
| IT-6 | セルフレビュー・実データ確認・最終コミット | TC-11 |

## 各 Iteration の共通手順

1. `plans/output_diff_plan.md` で該当 Iteration の詳細を確認する
2. 実装する
3. pytest を実行して対象 TC が PASS することを確認する（既存 TC も PASS であること）
4. コミットする（例: `feat(it-1): output_diff フレームワーク実装`）
5. `plans/output_diff_plan.md` の Iteration 状態を `done` に更新する

## テストケース一覧

| TC | 内容 | Iteration |
|----|------|-----------|
| TC-1 | Identical ファイルが正しく分類されること | IT-2 |
| TC-2 | Different テキストファイルが正しく分類されること | IT-2 |
| TC-3 | Left only ファイルが正しく分類されること | IT-2 |
| TC-4 | Right only ファイルが正しく分類されること | IT-2 |
| TC-5 | HTML 出力が生成されること（ファイル存在・件数・行色・**ソート順**） | IT-4 |
| TC-6 | CSV 出力が生成されること（ヘッダ・列数・utf-8-sig） | IT-3 |
| TC-7a | `--old` が存在しない場合に exit=1 で終了すること | IT-1 |
| TC-7b | `--new` が存在しない場合に exit=1 で終了すること（RQ-8） | IT-1 |
| TC-8 | `--html` と `--csv` を同時指定した場合に exit=1 で終了すること | IT-1 |
| TC-9 | Different テキストファイルの HTML に unified diff が含まれること | IT-5 |
| TC-10 | バイナリファイルが Different / Identical に正しく分類されること | IT-2 |
| TC-11 | 実データ（input/ 配下）で比較結果が生成されること | IT-6 |
| TC-12 | stdout に `比較完了: N 件 → {out_path}` が含まれること（cli.stdout_on_success） | IT-3 |

## セルフレビュー（IT-6 で必須）

`design/output_diff_spec.json` の全 requirements（RQ-1〜RQ-9）と実装を突き合わせた表を作成し、全て OK であることを確認してからコミットする。

## 制約

- 標準ライブラリのみ使用（`pathlib`, `difflib`, `csv`, `argparse`, `datetime`, `dataclasses`）
- 外部ライブラリは使用しない
