# yaml_diff.py 実装計画

作成日: 2026-05-17  
仕様書: `design/yaml_diff_spec.json`（v0.1.2）  
プロンプト: `.github/prompts/implement-yaml-diff.prompt.md`

---

## フェーズ 1: 調査（完了）

### 1-1. 実データ構造の確認

| 項目 | 内容 |
|------|------|
| 比較対象フォルダ | `input/requirement_file/{variant}-before/` vs `input/requirement_file/{variant}-after/` |
| 対象拡張子 | `.slot.yaml`（list 形式） / `_budget.yaml`（dict 形式） |
| `.yml` 対象外 | 実データに .yml ファイルが存在しないことを確認済み（2026-05-17） |
| m01 ファイル名の差異 | before: `TSS4_1AR2_RC01_m01_schedreq_relax.slot.yaml` / after: `TSS4_V1_m01.slot.yaml` |
| ペアリング方式 | ファイル名完全一致は使えない → **サフィックス（`.slot.yaml` / `_budget.yaml`）で1フォルダあたり1ファイルずつペア** |
| before 入手状況 | m01-before / m02-before: 入手済み。b01-before: 未入手（N-02 参照） |

### 1-2. 実データの差分実測（m01）

| 差分種別 | 件数 |
|---------|------|
| BudgetGroup変化 | 12 件 |
| タイムスロット変化 | 0 件 |
| キー追加/削除 | 0 件 |
| エントリ追加/削除 | 0 件（before/after ともに 467 件） |

→ テストは人工データで全 diff_type をカバーする。実データ確認は IT-6 で行う。

### 1-3. slot.yaml 構造

```python
# list 形式（各エントリの例）
{"RequirementId": "AhbAhs-01", "SequenceStartTimeSlotList": ["Timeslot2", "Timeslot4"]}
# RequirementId をキーとしてペアリング
```

### 1-4. budget.yaml 構造

```python
# dict 形式
{"BudgetGroupDefinition": [
    {"BudgetGroupID": "M-CA1-PVM-1", "TaskList": ["ViewMo(m01_m02)"]}
]}
# BudgetGroupID をキーとしてペアリング
```

### 1-5. カバレッジチェック設計（方式 B: MATCHER_REGISTRY inspect）

`cause_classifier.py` を `importlib.util` で動的インポートし、
`MATCHER_REGISTRY` の各 `match_fn` のソースを `inspect.getsource()` で取得。
`diff_type == '...'` および `diff_type in ('...')` のパターンを正規表現で抽出する。

```python
import importlib.util, inspect, re
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'cause_classifier', Path('scripts/cause_classifier.py'))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

known = set()
for _mid, _grp, match_fn, _cause in cc.MATCHER_REGISTRY:
    src = inspect.getsource(match_fn)
    known.update(re.findall(r"diff_type\s*==\s*'([^']+)'", src))
    for tup in re.findall(r"diff_type\s+in\s+\(([^)]+)\)", src):
        known.update(re.findall(r"'([^']+)'", tup))
```

---

## フェーズ 2: 設計

### 2-1. モジュール構成（`scripts/yaml_diff.py`）

```
scripts/yaml_diff.py
├── 定数ブロック
│   ├── SLOT_SUFFIX = '.slot.yaml'
│   └── BUDGET_SUFFIX = '_budget.yaml'
│
├── DiffEntry (dataclass)
│   ├── file: str       # ファイル名のみ（パスなし）
│   ├── diff_type: str  # diff_type_rules のいずれか
│   ├── key_path: str   # 'RequirementId.FieldName' 形式。ファイルレベル差分は空文字
│   ├── before: str     # _val_to_str() で変換済み文字列。エントリ追加: ""。エントリ削除: RequirementId/BudgetGroupID。それ以外: 値
│   └── after: str      # _val_to_str() で変換済み文字列。エントリ追加: RequirementId/BudgetGroupID。エントリ削除: ""。それ以外: 値（D-7 参照）
│
├── _val_to_str(v) -> str
│   └── list → json.dumps(v, ensure_ascii=False)
│   └── None → ""
│   └── else → str(v)
│
├── pair_yaml_files(before_dir: Path, after_dir: Path) -> list[tuple[Path | None, Path | None, str]]
│   └── 戻り値: [(before_path_or_None, after_path_or_None, suffix_name), ...]
│   └── suffix_name は '.slot.yaml' または '_budget.yaml'
│   └── ファイルレベルの DiffEntry（ファイル追加/消失）は呼び出し元（main）で生成する
│       ← IT-3 で before=None / after=None の tuple に対して main が DiffEntry を生成
│
├── diff_slot_yaml(before_path: Path, after_path: Path) -> list[DiffEntry]
│   └── RequirementId でペアリング（重複時は先頭のみ: N-05）
│   └── diff_type 分類:
│       - エントリ追加: after のみ存在
│       - エントリ削除: before のみ存在
│       - タイムスロット変化: SequenceStartTimeSlotList/SenderStartTimeSlotList の変化
│       - キー追加（YAML）: 同一エントリ内で after のみ存在するキー
│       - キー削除（YAML）: 同一エントリ内で before のみ存在するキー
│       - 値変化（YAML）: その他の値の変化
│
├── diff_budget_yaml(before_path: Path, after_path: Path) -> list[DiffEntry]
│   └── BudgetGroupID でペアリング
│   └── BudgetGroupID 重複: spec N-05 は RequirementId のみ対象。BudgetGroupID の重複は spec 対象外
│       （実データでも重複なし: m01-before 53件 全て一意）→ 先頭優先の対応は不要
│   └── diff_type 分類と DiffEntry フィールド値:
│       - エントリ追加: key_path=bgid, before="", after=bgid
│       - エントリ削除: key_path=bgid, before=bgid, after=""
│       - BudgetGroup変化: key_path=f'{bgid}.TaskList', before=json.dumps(old_tl), after=json.dumps(new_tl)
│
├── _collect_known_diff_types(spec_path: Path) -> set[str]  # 方式B
│
└── main()
    └── argparse（--before, --after, --out, --check-coverage, --dry-run）
    └── pair_yaml_files → diff_slot_yaml / diff_budget_yaml
    └── JSON レポート書き出し
    └── --check-coverage 指定時: _collect_known_diff_types → 差集合計算 → stdout 出力
    └── --dry-run 指定時: write_report() をスキップし、diff_types と entries 件数を stdout 出力して exit=0
    └── 終了コード: 0/1/2/3
```

### 2-2. DiffEntry フィールド詳細

| フィールド | 型 | 内容 |
|-----------|-----|------|
| `file` | str | ファイル名のみ（`Path(p).name`） |
| `diff_type` | str | diff_type_rules の9種類のいずれか |
| `key_path` | str | `'AhbAhs-01.SequenceStartTimeSlotList'` 形式。ファイルレベル差分は `""`。エントリ追加/削除は RequirementId / BudgetGroupID だけ（フィールド名なし） |
| `before` | str | `_val_to_str()` 適用後の文字列。エントリ削除: RequirementId/BudgetGroupID。エントリ追加: `""` |
| `after` | str | `_val_to_str()` 適用後の文字列。エントリ追加: RequirementId/BudgetGroupID。エントリ削除: `""`。※ spec.entries_schema.afterの「エントリ追加の場合は空文字」は spec 記載誤りと判断。ファイルレベルの convention（ファイル追加: before="", after=filename）に小整合して設計する（D-7 参照） |

### 2-3. diff_slot_yaml アルゴリズム

```
1. yaml.safe_load で before/after を読み込み
2. before_map = {e['RequirementId']: e for e in reversed(before)}  # reversed() で先頭優先 (N-05)
   # ※ {e['RequirementId']: e for e in before} は後勝ちになるため reversed() が必須
3. after_map = {e['RequirementId']: e for e in reversed(after)}
4. for rid in sorted(before_map.keys() - after_map.keys()):  # エントリ削除
   → DiffEntry(file=filename, diff_type='エントリ削除', key_path=rid, before=rid, after="")
   # ※ set 差集合は順序不定 → sorted() でアルファベット順に固定（テストの安定性確保）
5. for rid in sorted(after_map.keys() - before_map.keys()):  # エントリ追加
   → DiffEntry(file=filename, diff_type='エントリ追加', key_path=rid, before="", after=rid)
6. for rid in sorted(before_map.keys() & after_map.keys()):  # 共通エントリの差分
   a. 全キーを Union で取得: `sorted(before_entry.keys() | after_entry.keys())`
      # ※ set Union も順序不定 → sorted() でアルファベット順に固定（R-9）
   b. after のみにあるキー → キー追加（YAML）
   c. before のみにあるキー → キー削除（YAML）
   d. 共通キーで値が異なるとき:
      - キーが SequenceStartTimeSlotList or SenderStartTimeSlotList → タイムスロット変化
      - RequirementId は比較対象外（識別子）
      - それ以外 → 値変化（YAML）
```

### 2-4. JSON レポート形式

```json
{
  "generated_at": "2026-05-17T12:34:56Z",
  "before_dir": "input/requirement_file/m01-before",
  "after_dir": "input/requirement_file/m01-after",
  "diff_types": ["BudgetGroup変化"],
  "entries": [
    {
      "file": "TSS4_1AR2_RC01_m01_budget.yaml",
      "diff_type": "BudgetGroup変化",
      "key_path": "M-CA1-PVM-1.TaskList",
      "before": "[\"ViewMo(m01_m02)\"]",
      "after": "[\"ViewMo\"]"
    }
  ]
}
```

※ `--check-coverage` 指定時のみ `"uncovered_diff_types"` フィールドを追加。

### 2-5. 終了コード

| コード | 条件 |
|--------|------|
| 0 | 正常完了（--dry-run 指定時も 0） |
| 1 | `--check-coverage` で未カバー diff_type あり |
| 2 | 引数エラー（`--before`/`--after`/`--out` 未指定） |
| 3 | 入力ファイル読み込みエラー（ディレクトリ不在・YAML パースエラー） |

---

## フェーズ 3: 実装（イテレーティブ）

各 Iteration の状態: `todo` / `in-progress` / `done`

### IT-1: フレームワーク（状態: `todo`）

**目標**: `scripts/yaml_diff.py` の骨格を作成し、CLI エラー検出が動くこと

**実装内容**:
1. 定数ブロック（`SLOT_SUFFIX`, `BUDGET_SUFFIX`）
2. `DiffEntry` dataclass（frozen=False）
3. `_val_to_str(v) -> str`
4. `main()` — argparse（`--before`/`--after`/`--out`/`--check-coverage`/`--dry-run`）
   - `--before`/`--after`/`--out` 未指定 → `SystemExit(2)`（argparse `required=True`）
   - **実行順序（副作用を含む）**:
     1. argparse 引数検証 → exit=2
     2. `--before`/`--after` パス存在チェック → exit=3
     3. `--out` の親ディレクトリ自動作成（`out_path.parent.mkdir(parents=True, exist_ok=True)`）
        ※ **`--dry-run` 指定時はスキップ**（mkdir を実行しない）
     4. YAML 読み込み・差分計算（パースエラー → exit=3）
     5. `--dry-run` **未指定時**: `write_report()`（JSON 書き出し）→ exit=0 or exit=1
        `--dry-run` **指定時**: stdout に `diff_types: N 種, entries: M 件` を出力して exit=0
   - 副作用注意: 手順 4 で YAML パースエラー時、手順 3 の mkdir により作成した親ディレクトリが残る。
     JSON ファイル未生成のまま空ディレクトリが残るのは許容動作（D-6 参照）
5. `diff_slot_yaml()`/`diff_budget_yaml()`/`pair_yaml_files()` はスタブ（空リスト返却）
6. レポート書き出しスタブ（空 JSON ファイル生成のみ）

**テスト（`test/test_yaml_diff.py` 新規作成）**:
- TC-12a: `--before` 未指定 → `returncode == 2`
- TC-12b: `--after` に存在しないパス → `returncode == 3`
- TC-12c: `--before` に存在しないパス → `returncode == 3`（R-2: --before/--after 両方向を対称にテスト）
- TC-11: `--out` の親ディレクトリが存在しなくても出力ファイルが生成されること（exit=0）
- TC-17: `--dry-run` 指定時 → `--out` ファイルが生成されないこと、stdout に件数が出力されること、exit=0
  - 期待: `returncode == 0` かつ `--out` ファイルが**存在しない**こと かつ stdout に `'diff_types:'` が含まれること

**コミット**: `feat(it-1): yaml_diff フレームワーク実装`

---

### IT-2: slot.yaml 差分抽出（状態: `todo`）

**目標**: slot.yaml の全 diff_type が正しく検出されること

**実装内容**:
1. `diff_slot_yaml(before_path, after_path) -> list[DiffEntry]`
   - `yaml.safe_load` で読み込み
   - RequirementId でペアリング（重複時は先頭のみ: `{e['RequirementId']: e for e in reversed(lst)}`）
     ※ `reversed()` なしの `{...for e in lst}` は後勝ちになるため誤り（NA-1 参照）
   - エントリ追加/削除/タイムスロット変化/キー追加（YAML）/キー削除（YAML）/値変化（YAML）の全6種
2. `main()` の slot.yaml 処理を有効化

**テスト追加**（人工 YAML を `tmp_path` 内に生成してテスト）:
- **アサート方針**: `entries` の diff 内容（diff_type/key_path/before/after）は `any()` で確認する。
  `assert any(e.diff_type == X and e.key_path == Y and e.before == B and e.after == A for e in entries)`
  理由: `DiffEntry` は `file` フィールドを必須に持つため `DiffEntry(diff_type=...) in entries` は TypeError になる（NG-19）。
  `file` フィールドはテストの関心外（テスト YAML ファイル名に依存）。インデックス指定（`entries[0]`）は**禁止**止
- UT-1: `_val_to_str` 単体テスト:
  - `_val_to_str(["a", "b"]) == '["a", "b"]'`
  - `_val_to_str(None) == ""`
  - `_val_to_str(42) == "42"`
- TC-1: エントリ追加（after のみ存在する RequirementId `"R-NEW"`）
  - 期待: `any(e.diff_type == "エントリ追加" and e.key_path == "R-NEW" and e.before == "" and e.after == "R-NEW" for e in entries)`
- TC-2: エントリ削除（before のみ存在する RequirementId `"R-OLD"`）
  - 期待: `any(e.diff_type == "エントリ削除" and e.key_path == "R-OLD" and e.before == "R-OLD" and e.after == "" for e in entries)`
- TC-3a: タイムスロット変化（`SequenceStartTimeSlotList` の値が変化）
  - 期待: `any(e.diff_type == "タイムスロット変化" and e.key_path == "R-1.SequenceStartTimeSlotList" and e.before == '["T1"]' and e.after == '["T2"]' for e in entries)`
- TC-3b: タイムスロット変化（`SenderStartTimeSlotList` の値が変化）← NA-3: spec「または」の両フィールドを各々テスト
  - 期待: `any(e.diff_type == "タイムスロット変化" and e.key_path == "R-1.SenderStartTimeSlotList" and e.before == '["T1"]' and e.after == '["T2"]' for e in entries)`
- TC-4: キー追加（YAML）（after エントリにのみ存在するキー `"NewKey"`）
  - 期待: `any(e.diff_type == "キー追加（YAML）" and e.key_path == "R-1.NewKey" and e.before == "" and e.after == "newval" for e in entries)`
- TC-5: キー削除（YAML）（before エントリにのみ存在するキー `"OldKey"`）
  - 期待: `any(e.diff_type == "キー削除（YAML）" and e.key_path == "R-1.OldKey" and e.before == "oldval" and e.after == "" for e in entries)`
- TC-6: 値変化（YAML）（タイムスロット以外の値変化、キー `"SomeKey"`）
  - 期待: `any(e.diff_type == "値変化（YAML）" and e.key_path == "R-1.SomeKey" and e.before == "old" and e.after == "new" for e in entries)`
- TC-10: 差分なし → `entries=[]`, `diff_types=[]`

**コミット**: `feat(it-2): slot.yaml 差分抽出実装（6種）`

---

### IT-3: budget.yaml 差分抽出 + ファイルペアリング（状態: `todo`）

**目標**: budget.yaml の差分・ファイル追加/消失・ペアリングが動くこと

**実装内容**:
1. `diff_budget_yaml(before_path, after_path) -> list[DiffEntry]`
   - `BudgetGroupID` でペアリング
   - BudgetGroupID 重複は spec 対象外（NA-2 参照）
   - diff_type 分類と DiffEntry フィールド値:
     - エントリ追加: `DiffEntry(diff_type='エントリ追加', key_path=bgid, before="", after=bgid)`
     - エントリ削除: `DiffEntry(diff_type='エントリ削除', key_path=bgid, before=bgid, after="")`
     - BudgetGroup変化: `DiffEntry(diff_type='BudgetGroup変化', key_path=f'{bgid}.TaskList', before=json.dumps(old_tl, ensure_ascii=False), after=json.dumps(new_tl, ensure_ascii=False))`
2. `pair_yaml_files(before_dir, after_dir)` の実装
   - `.slot.yaml` / `_budget.yaml` サフィックスで 1-to-1 ペアリング
   - **戻り値は tuple のみ**（ファイルレベル DiffEntry は生成しない）
     - before のみ存在するファイル: `(Path, None, suffix_name)`
     - after のみ存在するファイル: `(None, Path, suffix_name)`
     - 両方存在: `(before_path, after_path, suffix_name)`
   - `main()` 側で `before=None` / `after=None` の tuple に対して DiffEntry を生成:
     - `(Path, None, _)` → `DiffEntry(diff_type='ファイル消失（YAML）', file=before_path.name, key_path="", before=before_path.name, after="")`
     - `(None, Path, _)` → `DiffEntry(diff_type='ファイル追加（YAML）', file=after_path.name, key_path="", before="", after=after_path.name)`
3. `main()` の budget.yaml + ペアリング処理を有効化

**テスト追加**:
- TC-7: BudgetGroup変化（TaskList が変化; list全体 JSON比較・順序あり）
  - 期待: `any(e.diff_type == "BudgetGroup変化" and e.key_path == "BG-1.TaskList" and e.before == '["a"]' and e.after == '["b"]' for e in entries)`
- TC-8: budget.yaml エントリ追加/削除
  - 追加期待: `any(e.diff_type == "エントリ追加" and e.key_path == "BG-NEW" and e.before == "" and e.after == "BG-NEW" for e in entries)`
  - 削除期待: `any(e.diff_type == "エントリ削除" and e.key_path == "BG-OLD" and e.before == "BG-OLD" and e.after == "" for e in entries)`
- TC-9: ファイル追加（YAML）/ ファイル消失（YAML）（after/before どちらかのみにファイルが存在）
  - 追加期待: `any(e.diff_type == "ファイル追加（YAML）" and e.key_path == "" and e.before == "" and e.after == "x_budget.yaml" for e in entries)`
  - 消失期待: `any(e.diff_type == "ファイル消失（YAML）" and e.key_path == "" and e.before == "y.slot.yaml" and e.after == "" for e in entries)`

**コミット**: `feat(it-3): budget.yaml 差分抽出 + ファイルペアリング実装`

---

### IT-4: レポート JSON 出力（状態: `todo`）

**目標**: 出力 JSON が spec の schema 通りに生成されること

**実装内容**:
1. `write_report(entries, before_dir, after_dir, out_path, *, uncovered=None)` を実装
   - `before_dir`/`after_dir`: `str(before_dir)` / `str(after_dir)`（argparse から受け取った文字列をそのまま使用。`Path.resolve()` しない）
- `diff_types`: `sorted(set(e.diff_type for e in entries))`（entries から内部計算; sorted() でアルファベット順に固定）
   - `generated_at`: `datetime.datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')`
   - `uncovered_diff_types`: `uncovered` が `None` 以外のときのみ JSON に追加（条件付きキー）
   - `entries`: `[dataclasses.asdict(e) for e in entries]`
   - JSON 書き出し後に return する（exit=1 の判定は main 側で行う）
2. `main()` での stdout メッセージ出力: `print(f"  比較完了: {len(entries)} 件 → {out_path}")`
3. **exit=1 の順序**: `write_report()` 完了後（JSON 書き出し後）に `SystemExit(1)` する。
   JSON には `uncovered_diff_types` が含まれた状態で保存される。

**テスト追加**:
- TC-15: 出力 JSON の top_level_fields が spec 通りであること
  - 期待: `assert set(report.keys()) >= {"generated_at", "before_dir", "after_dir", "diff_types", "entries"}`
  - 期待: `--check-coverage` 未指定時 `"uncovered_diff_types"` キーが JSON に**存在しない**こと
- TC-15b: entries の各要素が 5フィールドのみを持つこと
  - 期待: `assert set(entry.keys()) == {"file", "diff_type", "key_path", "before", "after"}` （余分フィールドなし）

**コミット**: `feat(it-4): レポート JSON 出力実装`

---

### IT-5: カバレッジチェック（状態: `todo`）

**目標**: `--check-coverage` が方式 B で動き、exit=0/1 が正しく返ること

**実装内容**:
1. `_collect_known_diff_types(spec_path: Path) -> set[str]` を実装
   - `importlib.util.spec_from_file_location` で `cause_classifier.py` を動的ロード
   - `MATCHER_REGISTRY` を走査
   - `inspect.getsource(match_fn)` + regex で `diff_type == '...'` / `diff_type in (...)` を抽出
   - `spec_path` は `--check-coverage` 引数として受け取る（将来の拡張用: 現時点では未使用）
   - `cause_classifier.py` は固定パス `Path(__file__).parent / 'cause_classifier.py'` から動的ロード
     ← prompt.md と一致。spec_path からスクリプト位置を特定する処理は**実装しない**（NA-4 修正）
2. 差集合計算:  `yaml_diff_types - known_diff_types`
3. 未カバーがあれば stdout に1行1件出力 + `SystemExit(1)`
4. `--check-coverage` 指定時に `uncovered_diff_types` フィールドを JSON に追加

**テスト追加**:
- TC-13: `--check-coverage` で未カバー diff_type がある → exit=1 + stdout に diff_type が出力される
  - テスト方法: yaml_diff の diff_types に cause_classifier が知らない値（例: 'タイムスロット変化'）が含まれるように人工 YAML を作成
  - 期待: `returncode == 1` かつ `stdout` に未カバー diff_type 名（例: `'タイムスロット変化'`）が含まれること
- TC-14: `--check-coverage` で全カバー → exit=0 + `uncovered_diff_types=[]` が JSON に含まれる
  - 期待: `returncode == 0` かつ 出力 JSON の `uncovered_diff_types == []`
  - テスト方法: before == after（差分なし）の YAML を使い entries=[], diff_types=[] の状態を作る
    → diff_types が空集合 ⊆ known_diff_types なので uncovered=[] → exit=0
  - 備考: yaml_diff と cause_classifier の diff_type 名前空間は異なるため（spec N-03）、
    実差分がある状態での全カバーは相互に diff_type 名を統一しない限り達成されない（expected 動作）

**コミット**: `feat(it-5): カバレッジチェック実装（方式B inspect）`

---

### IT-6: セルフレビュー・実データ確認・最終コミット（状態: `todo`）

**目標**: 全 spec 要件充足確認・実データ（m01）での動作確認

**作業手順**:

1. **セルフレビュー表の作成**

   `design/yaml_diff_spec.json` の全 processing_steps と実装を突き合わせる。

   | ステップ | 仕様内容 | 実装箇所 | 判定 |
   |---------|---------|---------|------|
   | step1 | ペアリング（サフィックス） | `pair_yaml_files()` | |
   | step2 | YAML 読み込み + 差分列挙 | `diff_slot_yaml()` / `diff_budget_yaml()` | |
   | step3 | diff_type 分類（9種） | 両差分関数内の条件分岐 | |
   | step4 | レポート生成 | `write_report()` | |
   | step5 | カバレッジチェック | `_collect_known_diff_types()` | |
   | CLI | --before/--after/--out/--check-coverage/--dry-run | `main()` argparse | |
   | exit | 0/1/2/3 | `main()` + `SystemExit()` | |
   | schema | 5フィールド | `write_report()` / `dataclasses.asdict()` | |
   | N-05 | 重複 RequirementId は先頭のみ | `diff_slot_yaml()` dict 構築 | |
   | D-7 | エントリ追加: before="", after=RequirementId/BudgetGroupID | `diff_slot_yaml()` / `diff_budget_yaml()` | |
   | sorted | set 演算（差集合/積集合/Union）全箇所に sorted() | §2-3 step4/5/6a | |
   | before_dir | `str(before_dir)`（resolve() しない） | `write_report()` | |

2. **実データ確認（m01）**:

   ```bash
   cd /home/y-shinohara/adas/work/format-change
   python3 scripts/yaml_diff.py \
     --before input/requirement_file/m01-before \
     --after  input/requirement_file/m01-after \
     --out    output/m01_yaml_diff_report.json
   ```

   確認ポイント:
   - returncode == 0
   - `diff_types` に `BudgetGroup変化` が含まれること（12件）
   - タイムスロット変化・エントリ追加/削除が0件であること

3. **TC-16 追加**（実データ smoke test）:
   - m01 before/after で実行 → returncode=0 + `BudgetGroup変化` 12件

4. **全テスト実行**:
   ```bash
   python3 -m pytest test/test_yaml_diff.py -v
   python3 -m pytest --tb=short -q   # 全体 PASS 確認
   ```

5. **コミット**:
   ```bash
   git add scripts/yaml_diff.py test/test_yaml_diff.py plans/yaml_diff_plan.md \
           design/yaml_diff_spec.json \
           .github/prompts/implement-yaml-diff.prompt.md
   git commit -m "feat: yaml_diff.py 実装完了（IT-1〜IT-6）"
   ```

---

## フェーズ 4: 評価（状態: `todo`）

### 評価 1: m02 実データ確認

```bash
python3 scripts/yaml_diff.py \
  --before input/requirement_file/m02-before \
  --after  input/requirement_file/m02-after \
  --out    output/m02_yaml_diff_report.json
```

### 評価 2: カバレッジチェック実行

```bash
python3 scripts/yaml_diff.py \
  --before input/requirement_file/m01-before \
  --after  input/requirement_file/m01-after \
  --out    output/m01_yaml_diff_report.json \
  --check-coverage design/cause_classifier_spec.json
```

→ 未カバー diff_type が stdout に出た場合は Phase-C C-3（新マッチャー追加）を実施。

---

## フェーズ 4.5: Iteration 状態トラッキング

| Iteration | 状態 |
|-----------|------|
| IT-1: フレームワーク | `todo` |
| IT-2: slot.yaml 差分抽出 | `todo` |
| IT-3: budget.yaml 差分抽出 + ペアリング | `todo` |
| IT-4: レポート JSON 出力 | `todo` |
| IT-5: カバレッジチェック | `todo` |
| IT-6: セルフレビュー・評価 | `todo` |
| フェーズ 4: 評価 | `todo` |

---

## 設計課題と対策

| # | 課題 | 対策 |
|---|------|------|
| D-1 | ファイル名が before/after で異なる | サフィックスで1-to-1 ペアリング（1フォルダあたり各1ファイル想定） |
| D-2 | 重複 RequirementId（N-05）| `{e['RequirementId']: e for e in lst}` で自動的に後勝ちになる → **逆順 iteration** で先頭優先を保証: `{e['RequirementId']: e for e in reversed(lst)}` |
| D-3 | `_collect_known_diff_types` の `spec_path` 引数 | cause_classifier_spec.json のパスを受け取るが、実際は `scripts/cause_classifier.py` を `Path(__file__).parent / 'cause_classifier.py'` で固定ロード。spec_path は将来の拡張用 |
| D-4 | BudgetGroup変化の比較（Q-4: 方式a） | `json.dumps(tasklist, ensure_ascii=False)` で文字列化して比較（順序あり） |
| D-5 | `uncovered_diff_types` フィールドの条件付き追加 | `--check-coverage` 未指定時はキー自体を出力しない（`report` dict に追加しない） |
| D-8 | `--dry-run` 時の副作用ゼロ | mkdir もスキップ。stdout のみ出力して exit=0。`--out` は argparse で必須のまま（構文整合性維持） |
| D-6 | YAML パースエラー時の mkdir 副作用 | `--out` 親ディレクトリの mkdir は引数検証後・ YAML 読み込み前に実行。YAML パースエラー（exit=3）時は JSON 未生成のまま空ディレクトリが残る。許容動作とする（実运用上の実害小） |
| D-7 | spec.entries_schema.after の「エントリ追加の場合は空文字」は誤記載 | ファイルレベルの convention（ファイル追加: before="", after=filename）と整合し、エントリ追加: before="", after=RequirementId/BudgetGroupIDとする。一貫性を優先して spec 記載よりも直感的な設計を選択。 |
