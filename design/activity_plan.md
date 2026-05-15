# 過去プロジェクト 要件ファイルフォーマット変更検討 活動計画

## ツール開発・改善履歴

| 日付 | 内容 | コミット / タグ |
|---|---|---|
| 2026-05-15 | GitHub Actions issue 管理ワークフロー 6 本追加 | `6f3f443` |
| 2026-05-15 | `--csv-out` オプション実装（Issue #1）・テスト 12/12 PASS | `5265af7`〜`de155e8` |
| 2026-05-15 | セルフレビュー第1〜4回・全 NG 修正済み | `416dbd1`〜`de155e8` |
| 2026-05-15 | Issue #1 クローズ・v0.1.0 リリースタグ公開 | `v0.1.0` |

---

## 背景・目的

過去プロジェクト（ver1/ver2/ver2.1）の要件ファイルフォーマットを ver3 相当に統一するにあたり、
**再解析結果（①）と過去解析済み結果（②）を比較して同等性を確認**し、変更可否を判断する根拠を整理する。

---

## 成果物

`過去プロジェクト(ver1_ver2_ver2.1)の要件ファイルフォーマット変更.xlsx`
→「Output差分」シートに全バリアントの差分を記入する

---

## 作業対象バリアント

| プロジェクト | バリ | ①再解析結果 | ②過去解析済み結果 | 状態 |
|---|---|---|---|---|
| ver1 | m02 | `ver1_m02_AP_再解析結果` | `scheduling_requirement_check_analysis_result` | ✅ 完了（42件・検出率15/15=100%、CSV出力済み） |
| ver1 | b01 | 未提供 | - | ⏳ 顧客提供待ち |
| ver1 | m01 | 未提供 | - | ⏳ 顧客提供待ち |
| ver2 | b01 | 未提供 | - | ⏳ 顧客提供待ち |
| ver2 | m01 | 未提供 | - | ⏳ 顧客提供待ち |
| ver2 | m02 | 未提供 | - | ⏳ 顧客提供待ち |
| ver2.1 | b01 | 未提供 | - | ⏳ 顧客提供待ち |
| ver2.1 | m01 | 未提供 | - | ⏳ 顧客提供待ち |
| ver2.1 | m02 | 未提供 | - | ⏳ 顧客提供待ち |

---

## 各バリアントの作業ステップ

各バリアントに対して以下の手順で差分を整理する。

### Step 1: 入力情報の確認

- `input_info.txt` を確認し、①②それぞれのツールバージョン・要件ファイルパスを記録する

### Step 2: 出力ファイルの比較

以下のファイルを対象に、①と②の差分を確認する。

| ファイル / フォルダ | 確認内容 |
|---|---|
| `schedule_result.csv` | 判定結果（PASS/FAIL）・id/name・etc の変化 |
| `schedule_result_fail_list.csv` | 列ヘッダ名の変化 |
| `processing_time_result.csv` | TaskID の増減・値の変化 |
| `processing_time_SWC_group_result.csv` | 内容の変化 |
| `node_straddling_slot_pickup_result.csv` | 内容の変化 |
| `input_data_ba.csv` / `input_data_igr.csv` | Node行の増減・順序変化 |
| `processing_load_duration_graph/` | 画像ファイルの増減・タイトル変化 |
| `Sequence_duration_graph/` | 画像ファイルの増減・タイトル変化 |
| `SWC_budget_duration_graph/` | 画像ファイルの増減 |
| `WakeupInterval_graph/` | 画像ファイルの増減 |
| `temp/before_requirements.csv` | RequirementId / RequirementOwner / Sequence 等の変化 |
| `temp/after_requirements.csv` | 同上 |
| `temp/before_cpuload_requirements.csv` | NodeName の変化・TaskID の増減 |
| `temp/after_cpuload_requirements.csv` | 同上 |
| `temp/before_budget.csv` | TaskList の変化 |
| `temp/after_budget.csv` | 内容の変化 |

### Step 3: 差分の分類・記録

差分を以下の観点で分類する。

| 分類 | 例 |
|---|---|
| ファイル消失 | `PF_1msTask(2SoC, Base).png` が存在しない |
| 画像差分 | タイトル名が変化 |
| NodeName の変化 | `VidDraw` → `viddraw` |
| id/name の変化 | `AhbAhs/Main` → `AhbAhs` |
| TaskID の追加 | `PF_window` が追加 |
| キーの追加 | Fsync 要件に `Target` キーが追加 |
| 列ヘッダの変化 | Node名が SWC名/Node名に統一 |
| 行の消失 | `pf_1ms_base` 行が消失 |
| 順序の変化 | `start_clock_ms` が同一の Node 間で順序が入れ替わり |

### Step 4: Output差分シートへの記入

Excel「Output差分」シートの以下の列を埋める。

| 列 | 項目 | 記載内容 |
|---|---|---|
| No. | 連番 | 自動採番（=前行+1） |
| フォルダ | フォルダ名 | 差分が発生したフォルダ名（なければ `-`） |
| ファイル | ファイル名 | 差分が発生したファイル名 |
| 差分 / 概要 | 差分の種類 | 上記「分類」の文言 |
| 差分 / 過去ツール/フォーマット | 過去の値 | 変更前の値・状態 |
| 差分 / ver3ツール/フォーマット | ver3後の値 | 変更後の値・状態 |
| 画像リンク | リンク先 | （既存の記載に合わせる） |
| プロジェクト | プロジェクト名 | `ver1` / `ver2` / `ver2.1` |
| バリ | バリアント名 | `b01` / `m01` / `m02` |
| 推定原因 | 変化の原因 | フォーマット変更番号（例: `infsimyml のフォーマット変更(1ｰ①)`）など |

※「差分許容できるか」列の判定は顧客側で実施いただく想定です。

---

## ver1 m02 の完了内容（参考）

以下 34 件を「Output差分」シートに記入済み。

| ファイル | 差分内容 | 推定原因 |
|---|---|---|
| `input_info.txt` | ツール差分・要件ファイル差分 | ver3ツール/フォーマット使用 |
| `processing_load_duration_graph` | `PF_1msTask(2SoC, Base/Mid).png` ファイル消失 | infsimyml フォーマット変更(1-③) |
| `Sequence_duration_graph` | `VidDraw-01.png` タイトルが `viddraw` に変化 | chksimyml フォーマット変更(2-③) |
| `tmp/before_cpuload_requirements` | NodeName 変化（VidDraw/ViewRdr系）・PF_window 追加 | infsimyml フォーマット変更(1-①③) |
| `tmp/after_cpuload_requirements` | PF_window 追加 | infsimyml フォーマット変更(1-③) |
| `tmp/before_requirements` | Sequence/Sender/Receiver 名統一・Fsync キー追加・VidDraw 変化 | chksimyml フォーマット変更(2-①②③) |
| `tmp/after_requirements` | 同上 + AhbAhs/Main→AhbAhs・LgtCtl/LightingControl→LgtCtl | chksimyml フォーマット変更 |
| `tmp/before_budget` | TaskList 変化（SplAd 系・(m01_m02) サフィックス削除） | budget.yaml フォーマット変更(4-②) |
| `input_data_ba.csv` | pf_1ms_base/mid 行消失・Node 順序入れ替わり（1008件） | - |
| `input_data_igr.csv` | pf_1ms_base/mid 行消失・Node 順序入れ替わり（1043件） | - |
| `processing_time_result.csv` | PF_window 追加 | infsimyml フォーマット変更(1-③) |
| `schedule_result.csv` | id/name 変化・etc 変化（Node名統一） | chksimyml フォーマット変更(2-①③) |
| `schedule_result_fail_list.csv` | 列ヘッダ変化（Node名統一） | chksimyml フォーマット変更(2-①) |

**差分なし**: `node_straddling_slot_pickup_result.csv`、`processing_time_SWC_group_result.csv`、`temp/after_budget.csv`

---

## 懸案事項

| # | 内容 | 対応方針 |
|---|---|---|
| 1 | ver1 b01/m01 および ver2/ver2.1 系の①②データが未提供 | 顧客から順次提供される予定。提供され次第、同手順で対応する |
| 2 | 「差分許容できるか」列の判定 | 顧客側での実施を想定。判断に必要な情報があればご連絡ください |
