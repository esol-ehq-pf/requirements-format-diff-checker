# format-change パターン蓄積ログ（設計検討用）

最終更新: 2026-05-15

## プロジェクト概要

- **目的**: 過去プロジェクト(ver1/ver2/ver2.1)の要件ファイルフォーマットを ver3 へ変換可能か検討
- **作業**: ver3 ツールで再解析した結果①と、過去解析結果②の差分を整理する
- **現在の対象**: ver1 m02（b01 も実データで確認済み）
- **リポジトリ root**: `/home/y-shinohara/adas/work/format-change/`

## 最終ゴール（要求）

| # | 要求 |
|---|------|
| G-1 | **機械的に自動判定したい**（差分の cause を自動分類） |
| G-2 | **自動で判定できない場合は候補を提示する** |
| G-3 | **AI による判定補助も活用したい** |

---

## パターン全体サマリ

| パターン# | ファイル | 変化内容 | cause | 自動判定レベル |
|---|---|---|---|---|
| 1-① | cpuload_requirements.csv NodeName列 | PascalCase → lowercase（括弧削除） | infsimyml フォーマット変更 | G-1 |
| 1-② | before/after_requirements.csv RequirementID等 | normalize()適用 | infsimyml フォーマット変更 | G-1 |
| 1-③ | cpuload_requirements.csv / processing_time_result.csv | PF_window 行追加（13→30行） | infsimyml フォーマット変更 | G-1 |
| 2-① | before/after_requirements.csv Sequence等 | SWC名/Node名統一 | chksimyml フォーマット変更 | G-1/G-2/G-3 混在 |
| 2-② | before/after_requirements.csv Target列 | Fsync行にTarget列追加 | chksimyml フォーマット変更 | G-1 |
| 2-③ | before/after_requirements.csv RequirementId等 | normalize()適用 | chksimyml フォーマット変更 | G-1 |
| 3-① | input_info.txt L01 | Tool Tag→Tool Branch キー変更 | slot.yaml フォーマット変更 | G-1 |
| 3-② | schedule_result.csv id/name | normalize()適用 | slot.yaml フォーマット変更 | G-2 |
| 4-① | input_info.txt | ツールバージョン変化 | budget.yaml フォーマット変更 | G-1 |
| 4-② | before/after_budget.csv TaskList | Node名統一（A/B/C 3サブパターン） | budget.yaml フォーマット変更 | G-1/G-2/G-3 混在 |
| 8 | after_cpuload_requirements.csv | PF_window 行追加 | 1-③ と同一 | G-1 |
| 9 | after_cpuload_requirements.csv NodeName | pf_1ms_base → PF_1msTask(...) 逆変換 | ツール起因か要確認 | G-2 |
| 10 | before_requirements.csv Sequence等 | SWC名/Node名統一 | 2-① と同一 | G-1/G-2/G-3 |
| 11 | before_requirements.csv Target列 | Fsync行にTarget列追加 | 2-② と同一 | G-1 |
| 12 | before_requirements.csv RequirementId | normalize()適用 | 2-③ と同一 | G-1 |
| 13 | before_requirements.csv RequirementOwner | normalize()適用 | 2-③ と同一 | G-1 |
| 14 | after_requirements.csv Sequence等 | SWC名/Node名統一（一部既変換） | 2-① と同一 | G-1/G-2/G-3 |
| 15 | after_requirements.csv Target列 | Fsync行にTarget列追加 | 2-② と同一 | G-1 |
| 16 | after_requirements.csv RequirementId | normalize()適用 | 2-③ と同一 | G-1 |
| 17 | after_requirements.csv RequirementOwner | VidDraw→viddraw | 2-③ と同一 | G-1 |
| 18 | after_requirements.csv RequirementOwner | AhbAhs/Main→AhbAhs（逆変換） | ツール起因か要確認 | G-2 |
| 19 | after_requirements.csv RequirementOwner | LgtCtl/LightingControl→LgtCtl（逆変換） | ツール起因か要確認 | G-2 |
| 20 | before_budget.csv TaskList | Node名統一 | 4-② と同一 | G-1/G-2/G-3 |
| 21 | input_data_ba.csv node列 | pf_1ms_base/mid 消失（-533,131行） | パターン9/28の連鎖（ツール起因） | — |
| 22 | input_data_ba.csv 行順序 | Node順序入れ替わり | パターン21の連鎖 | — |
| 23 | input_data_igr.csv node列 | pf_1ms_base/mid 消失（-532,975行） | パターン9/28の連鎖（ツール起因） | — |
| 24 | input_data_igr.csv 行順序 | Node順序入れ替わり | パターン23の連鎖 | — |
| 25 | input_info.txt L01 | Tool Tag→Tool Branch | ver3ツール使用 | G-1 |
| 26 | input_info.txt L04-07 | 要件ファイルパス変更 | ver3フォーマット要件ファイル使用 | G-1 |
| 27 | processing_time_result.csv | PF_window 行追加（全NA） | 1-③ と同一 | G-1 |
| 28 | processing_time_result.csv NodeName | pf_1ms_base→PF_1msTask (result=NA) | ツール起因か要確認 | G-2 |
| 29 | schedule_result.csv id | VidDraw-01→viddraw-01 | 2-③ と同一 | G-1 |
| 30 | schedule_result.csv name | AhbAhs/Main→AhbAhs（逆変換） | ツール起因か要確認 | G-2 |
| 31 | schedule_result.csv name | LgtCtl/LightingControl→LgtCtl（逆変換） | ツール起因か要確認 | G-2 |
| 32 | schedule_result.csv etc | [X]→[X/X] FAILメッセージ内ノード名 | 2-① と同一 | G-1 |
| 33 | schedule_result_fail_list.csv L1サブヘッダ | X_suffix→X/X_suffix | 2-① と同一 | G-1 |

---

## infsimyml（1-系）パターン詳細

**cause タグ統一形式:** `infsimyml のフォーマット変更(1ｰN)に伴う変化点`

---

### 1-① PFタスク NodeName 変更

**変換ルール:**

| 旧 NodeName | 新 NodeName | 変換規則 |
|---|---|---|
| `VidDraw` | `viddraw` | 大文字→小文字 |
| `ViewRdr_CIREND(2SoC, PVM)` | `viewrdr_cirend` | 大文字→小文字 ＋ `(...)` 削除 |
| `ViewRdr_SCRM(2SoC, PVM)` | `viewrdr_scrm` | 大文字→小文字 ＋ `(...)` 削除 |
| `ViewRdr_UIREND(2SoC, PVM)` | `viewrdr_uirend` | 大文字→小文字 ＋ `(...)` 削除 |

**一般則:** `re.sub(r'\(.*\)', '', name).lower()`  
（括弧内に関わらず共通。variant 表記は b01/m02 で異なる）

**波及ファイル:** `before/after_cpuload_requirements.csv`, `before/after_requirements.csv` 等  
**cause タグ:** `infsimyml のフォーマット変更(1ｰ①)に伴う変化点`

---

### 1-② PFタスク RequirementCheckKey 変更

**変換ルール:** 1-① と同一の `normalize()` が RequirementCheckKey 列に波及

| CSV 列名 | 旧値 | 新値 |
|---|---|---|
| `RequirementID` | `VidDraw-01` | `viddraw-01` |
| `RequirementOwner` | `VidDraw` | `viddraw` |
| `RequirementId` | `VidDraw-01` | `viddraw-01` |

**判別:** 値の変換式は 1-① と同一だが、列名で区別する

| 列名 | 該当パターン |
|---|---|
| `NodeName` | 1-① |
| `RequirementID`, `RequirementOwner`, `RequirementId` | 1-② |

**cause タグ:** `infsimyml のフォーマット変更(1ｰ②)に伴う変化点`

---

### 1-③ 全パターンの PF_window を記載

**変更の種類:** 行の追加

| 項目 | 旧 | 新 |
|---|---|---|
| PF_window の種類数 | 8種（1〜8） | 15種（1〜16、13除く） |
| 行数（cpuload_requirements.csv） | 13行 | 30行 |

- 新にのみある行: 17行（PF_window9〜16 の各 Ca/SoC 組み合わせ）
- `processing_time_result.csv` では新追加行が全て NA（Node not found from input csv）

**cause タグ:** `infsimyml のフォーマット変更(1ｰ③)に伴う変化点`

---

## chksimyml（2-系）パターン詳細

**cause タグ統一形式:** `chksimyml のフォーマット変更(2ｰN)に伴う変化点`

---

### 2-① Sequence/Sender/Receiver/FirstTask/SecondTask を SWC名/Node名 に統一

**変換ルール:**

| ケース | 旧形式 | 新形式 | 例 |
|---|---|---|---|
| SWC名 = Node名 | `X` | `X/X` | `Fm` → `Fm/Fm` |
| SWC名 ≠ Node名 | `NodeName` | `SWCName/NodeName` | `AhbAhs` → `AhbAhs/Main` |
| 括弧付き Node名 | `SWC(C1C3)` | `SWC/SWC(C1C3)` | `InlyrBsr(C1C3)` → `InlyrBsr/InlyrBsr(C1C3)` |
| PF タスク（1-①適用後） | `viddraw` | `Preempt/viddraw` | `viewrdr_cirend` → `Preempt/viewrdr_cirend` |

**自動判定:**
- `X/X` 形式: 正規表現 `^(\w+)/\1` で検出 → G-1
- `X/Y`（X≠Y）: SWC↔Node 対応表が必要 → G-2/G-3

**波及ファイル:** `before/after_requirements.csv`（Sequence 列はリスト形式文字列。各要素に適用）  
**cause タグ:** `chksimyml のフォーマット変更(2ｰ①)に伴う変化点`

---

### 2-② RequirementType: Fsync に対して Target キーを追加

- 旧: `Target` 列なし
- 新: `Target` 列追加（Fsync行: SWC名/Node名、それ以外: 空文字）
- m02 実データ: Fsync 16件、`Target='AhbAhs/Main'`、`Target='RFsn/RFsn'` 等

**cause タグ:** `chksimyml のフォーマット変更(2ｰ②)に伴う変化点`

---

### 2-③ RequirementId/RequirementOwner の変更

**変換ルール:** `VidDraw` → `viddraw`（normalize()、1-① と同一）

**cause タグ:** `chksimyml のフォーマット変更(2ｰ③)に伴う変化点`

---

## slot.yaml（3-系）パターン詳細

**cause タグ統一形式:** `slot.yaml のフォーマット変更(3ｰN)に伴う変化点`

---

### 3-① ツールバージョンの変化（input_info.txt L01）

| 項目 | 旧 | 新 |
|---|---|---|
| キー名 | `Tool Tag:` | `Tool Branch:` |
| 値 | `1AR2_RC1_VER2(1082357de...)` | `tmp/ymlcheck(db5da36b...)` |

- キー名変化で G-1 検出可能（値は毎回異なるため値ではなくキー名で判定）

**cause タグ:** `slot.yaml のフォーマット変更(3ｰ①)に伴う変化点`

---

### 3-② RequirementId の変更

- 変換ルール: 2-③ と同一（normalize()）
- schedule_result.csv 上では 2-③ と同一セルに出現するため cause の区別が困難 → G-2

**cause タグ:** `slot.yaml のフォーマット変更(3ｰ②)に伴う変化点`

---

## budget.yaml（4-系）パターン詳細

**cause タグ統一形式:** `budget.yaml のフォーマット変更(4ｰN)に伴う変化点`

---

### 4-① ツールバージョンの追加

- output CSV への直接影響なし（input_info.txt は 3-① として記録済み）

**cause タグ:** `budget.yaml のフォーマット変更(4ｰ①)に伴う変化点`

---

### 4-② TaskList を Node名で統一

**変換パターン（3種類）:**

| パターン | 説明 | 例 | 自動判定 |
|---|---|---|---|
| **A: variant 削除** | `X(variant)` → `X` | `ViewMo(m01_m02)` → `ViewMo` | G-1 |
| **B: SplAd ラッパー除去** | `SplAd(X)` → `X` | `SplAd(EventSpm)` → `EventSpm` | G-1 |
| **C: 別名変換** | `X(variant)` → `別のNode名` | `AhbAhs(b01_m01_m02)` → `Main` | G-2/G-3 |

**C タイプ変換ペア（m02 確認）:**

| 旧 | 新 |
|---|---|
| `AhbAhs(b01_m01_m02)` | `Main` |
| `LgtCtl(b01_m01_m02)` | `LightingControl` |
| `SplAd(TJSupport)` | `TrafficJamSupport` |

**A タイプ（m02 全件）:**
`ViewMo`, `SnrRcg`, `Pksb`, `Pksa`, `PkArbM`, `MdColBA0`, `VseB`, `Pab`, `TrCh`, `RctaUnit`, `RctaIntg`, `Rctb`, `OmiArb`, `Bsm`, `InstBld`, `TrgrDtct`, `MdSnd`

**B タイプ（m02 全件）:**
`SplAd(CSpm)`, `SplAd(EventSpm)`, `SplAd(MapEnd)`, `SplAd(Rob)`, `SplAd(Ymv)`

**cause タグ:** `budget.yaml のフォーマット変更(4ｰ②)に伴う変化点`

---

## b01 ケースの変化点詳細（パターン8〜33）

### temp/after_cpuload_requirements.csv（パターン8/9）

**行数変化（m02）:** 旧 355行 → 新 372行（+17行）

| # | 変化内容 | cause | 備考 |
|---|---|---|---|
| 8 | PF_window の行追加（13→30行） | 1-③ と同一 | — |
| 9 | NodeName: `pf_1ms_base` → `PF_1msTask(2SoC, Base)` | **ツール起因か要確認** | 逆変換（小文字→PascalCase+variant）。新では NodeName=TaskID と同一値 |

**⚠️ パターン9 の注意点:**
- 1-① は PascalCase → lowercase だが、パターン9 は逆（lowercase → PascalCase+variant）
- `old_nodename` = `re.sub(r'\(.*\)', '', TaskID).lower().replace(' ', '_')` に相当
- パターン9 → パターン28 → パターン21/23 の連鎖を引き起こす

---

### temp/before_requirements.csv（パターン10〜13）

**行数変化（m02）:** 旧 524行 → 新 524行 / **ヘッダ追加:** `Target` 列

| # | 列 | 変化内容 | 件数（m02） | cause |
|---|---|---|---|---|
| 10 | Sequence/Sender/Receiver/FirstTask/SecondTask | SWC名/Node名統一 | Sender:415件, Receiver:415件, Sequence:87件, First/Second:6件 | 2-① |
| 11 | Target | Fsync行にTarget列追加 | Fsync 16件 | 2-② |
| 12 | RequirementId | VidDraw-01→viddraw-01 | 1件 | 2-③ |
| 13 | RequirementOwner | VidDraw→viddraw | 1件 | 2-③ |

**Sequence 列は `リスト形式の文字列`**: リスト内各要素に 2-① の変換が適用される

---

### temp/after_requirements.csv（パターン14〜19）

**行数変化（m02）:** 旧 524行 → 新 524行 / **ヘッダ追加:** `Target` 列

| # | 列 | 変化内容 | 件数（m02） | cause |
|---|---|---|---|---|
| 14 | Sequence/Sender/Receiver/FirstTask/SecondTask | SWC名/Node名統一 | Sender:412件, Receiver:414件, Sequence:87件, First/Second:6件 | 2-① |
| 15 | Target | Fsync行にTarget列追加 | Fsync 16件 | 2-② |
| 16 | RequirementId | VidDraw-01→viddraw-01 | 1件 | 2-③ |
| 17 | RequirementOwner | VidDraw→viddraw | 1件 | 2-③ |
| 18 | RequirementOwner | AhbAhs/Main→AhbAhs | 3件 | **ツール起因か要確認**（逆変換: SWC/Node → SWC名） |
| 19 | RequirementOwner | LgtCtl/LightingControl→LgtCtl | 1件 | **ツール起因か要確認**（逆変換） |

**⚠️ after_requirements の特徴:** 旧データに既に `AhbAhs/Main`（SWC/Node形式）が入っていた。
新では `AhbAhs` のみ（SWC名）に戻る。`new == old.split('/')[0]` で判定可能。

---

### temp/before_budget.csv（パターン20）

**行数変化（m02）:** 旧 54行 → 新 54行（変化なし）

| # | 変化内容 | 件数 | cause |
|---|---|---|---|
| 20 | TaskList が Node 名で統一 | 変化12件/変化なし42件 | 4-② と同一（A/B/C 3サブパターン） |

**m02 実データ（B-CA0-ECP-1 のみ C タイプ）:**
- `AhbAhs(b01_m01_m02)` → `Main`
- `LgtCtl(b01_m01_m02)` → `LightingControl`

---

### input_data_ba.csv（パターン21/22）

**行数変化（m02）:** 旧 3,306,295行 → 新 2,773,164行（**-533,131行**）

| # | 変化内容 | cause |
|---|---|---|
| 21 | `pf_1ms_base`/`pf_1ms_mid` node の完全消失（533,131件） | パターン9/28の連鎖（ツール起因） |
| 22 | Node の順序入れ替わり | パターン21の連鎖（行シフト） |

---

### input_data_igr.csv（パターン23/24）

**行数変化（m02）:** 旧 3,304,338行 → 新 2,771,363行（**-532,975行**）

| # | 変化内容 | cause |
|---|---|---|
| 23 | `pf_1ms_base`/`pf_1ms_mid` node の完全消失（532,975件） | パターン21と同一原因 |
| 24 | Node の順序入れ替わり | パターン22と同一原因 |

---

### input_info.txt（パターン25/26）

**行数変化（m02）:** 旧 11行 → 新 11行

| # | 変化行 | 旧 | 新 | cause |
|---|---|---|---|---|
| 25 | L01 ツール識別 | `Tool Tag: 1AR2_RC1_VER2(...)` | `Tool Branch: tmp/ymlcheck(...)` | ver3ツール使用 |
| 26 | L04〜L07 要件ファイルパス | `TSS4_1AR2_RC01/m02/...` | `TSS4_V3_1A_RC01/m02/...` | ver3フォーマット要件ファイル使用 |

**変化なし:** `launch.yaml`, `input_tsync_csv`, `log_path`, `base_csv`, `mid_csv`

---

### processing_time_result.csv（パターン27/28）

**行数変化（m02）:** 旧 355行 → 新 372行（+17行）

| # | 変化内容 | cause | 備考 |
|---|---|---|---|
| 27 | PF_window 行追加（13→30行） | 1-③ と同一 | 新追加行は全て `[NA] Node not found from input csv` |
| 28 | NodeName: `pf_1ms_base` → `PF_1msTask(2SoC, Base)` | **ツール起因か要確認** | result=PASS → NA。パターン21/23の直接原因 |

**⚠️ パターン9→28→21/23 の連鎖（重要）:**
```
ツール側の変更（infsimyml 変更なし）
  ↓
NodeName: pf_1ms_base → PF_1msTask(2SoC, Base)  ← パターン9/28
  ↓
ツールが input_data の node='pf_1ms_base' を見つけられない
  ↓
input_data_ba/igr.csv に pf_1ms 行が出力されない  ← パターン21/23
processing_time_result が NA 判定になる            ← パターン28
```

---

### schedule_result.csv（パターン29〜32）

**行数変化（m02）:** 旧 524行 → 新 524行

| # | 列 | 変化内容 | 件数 | cause |
|---|---|---|---|---|
| 29 | id | VidDraw-01→viddraw-01 | 1件 | 2-③ |
| 30 | name | AhbAhs/Main→AhbAhs | 3件 | **ツール起因か要確認**（パターン18と同一） |
| 31 | name | LgtCtl/LightingControl→LgtCtl | 1件 | **ツール起因か要確認**（パターン19と同一） |
| 32 | etc | `[X]`→`[X/X]`（FAILメッセージ内ノード名） | 22件 | 2-① |

**パターン32 の注意点:** result 列（PASS/FAIL）への影響なし。etc のメッセージ文字列内のみ。

---

### schedule_result_fail_list.csv（パターン33）

**行数変化（m02）:** 旧 10,648行 → 新 10,648行

**ファイル構造（特殊2段ヘッダ）:**
- L0（ヘッダ）: 要件ID（`Pksa-03(deterministic)` 等）
- L1（サブヘッダ）: ノード変数名 ← **ここが変化**
- L2〜: 実測値（変化なし）

| # | 変化箇所 | 旧 | 新 | cause |
|---|---|---|---|---|
| 33 | L1 サブヘッダ（全48列） | `PkArbM_end_clock` | `PkArbM/PkArbM_end_clock` | 2-① |

**変換パターン:** `X_suffix` → `X/X_suffix`（`_` 区切り前のノード名部分に 2-① X→X/X 適用）

---

## 設計検討メモ

### 共通変換式

```python
def normalize(name: str) -> str:
    """1-①/1-②/2-③/3-② 共通の変換式"""
    return re.sub(r'\(.*\)', '', name).lower()
```

### 逆変換パターン（要注意）

パターン18/19/28/30/31 は、旧データに既に SWC/Node 形式が入っている場合の逆変換：
- `SWC/Node → SWC名のみ`: `new == old.split('/')[0]`
- `pf_1ms_base → PF_1msTask(...)`: `normalize(new) == normalize(TaskID)`

### SWC↔Node 対応表が必要な変換

2-① および 4-② のうち SWC名≠Node名 のケースは対応表が必要:
- `AhbAhs` ↔ `Main`
- `LgtCtl` ↔ `LightingControl`
- `SplAd(TJSupport)` ↔ `TrafficJamSupport`

### 未解決の残課題

| 課題 | 状態 |
|---|---|
| pf_1ms_base/mid 消失の原因 | ✅ 解消（パターン9/28の連鎖→ツール起因） |
| RequirementOwner 変化の原因 | ✅ 解消（パターン13=2-③、パターン18/19=ツール起因） |
| パターン9/18/19/28/30/31 の「ツール起因」の確定 | ⬜ 要確認 |
| ver1 m03以降の対象ファイルがあるか | ⬜ 未確認 |
