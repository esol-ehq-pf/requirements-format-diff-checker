---
mode: agent
description: yaml_diff.py をイテレーティブに実装・テスト・コミットする（フレームワーク→差分抽出→出力→カバレッジチェック）
---

# yaml_diff.py 実装タスク

## 目的

`design/yaml_diff_spec.json`（v0.1.2）の仕様に従い、**フレームワーク先行・段階的機能拡張**のアプローチで `scripts/yaml_diff.py` を実装する。テストを各 Iteration で作成・実行してコミットする。

## 前提情報

- **仕様書**: `design/yaml_diff_spec.json`（v0.1.2）
- **実装計画**: `plans/yaml_diff_plan.md`（設計・アルゴリズム・Iteration 詳細を記載）
- **リポジトリ**: `/home/y-shinohara/adas/work/format-change/`
- **Python バージョン**: 3.13.12（pyenv）
- **外部ライブラリ**: PyYAML 6.0.3（`import yaml`）のみ。それ以外は標準ライブラリ
- **既存スクリプト参考**: `scripts/output_diff.py`（argparse・SystemExit・pathlib の書き方を踏襲）
- **テスト配置**: `test/test_yaml_diff.py`（`test/test_output_diff.py` のスタイルに準拠）

## 開発方針

- **関数単位の責務分離**: slot.yaml 差分 / budget.yaml 差分 / ペアリング / レポート出力 / カバレッジチェック を独立した関数に分離する
- **中間データ構造**: `DiffEntry` dataclass（file/diff_type/key_path/before/after の5フィールド）を出力形式に依存しない形で持つ
- **_val_to_str()**: list→`json.dumps(ensure_ascii=False)`、None→`""`、else→`str()` に統一
- **ペアリング方式**: サフィックス（`.slot.yaml` / `_budget.yaml`）で1フォルダあたり1ファイルずつペア。ファイル名完全一致は**使わない**（before/after でファイル名が異なる）
- **重複 RequirementId**: `{e['RequirementId']: e for e in reversed(lst)}` で先頭エントリ優先（N-05）
- **BudgetGroup変化の比較**: `json.dumps(tasklist, ensure_ascii=False)` で文字列化して比較（順序あり: Q-4=方式a）

## イテレーション計画

計画の詳細は `plans/yaml_diff_plan.md` を参照。各 Iteration で「実装 → pytest → コミット」を完結させること。

| Iteration | 実装内容 | 対応 TC |
|-----------|---------|--------|
| IT-1 | フレームワーク（CLI・DiffEntry・終了コード） | TC-12a, TC-12b, TC-11, TC-17 |
| IT-2 | slot.yaml 差分抽出（6種） | TC-1〜6, TC-10 |
| IT-3 | budget.yaml 差分抽出 + ファイルペアリング | TC-7, TC-8, TC-9 |
| IT-4 | レポート JSON 出力 | TC-15, TC-15b |
| IT-5 | カバレッジチェック（方式B: MATCHER_REGISTRY inspect） | TC-13, TC-14 |
| IT-6 | セルフレビュー・実データ確認・最終コミット | TC-16 |

## 各 Iteration の共通手順

1. `plans/yaml_diff_plan.md` で該当 Iteration の詳細を確認する
2. **実装前に「該当 IT の Exit Criteria」を全項目読み、適用する R-N を把握してから実装を開始する**
3. 実装する
4. pytest を実行して対象 TC が PASS することを確認する（**既存 65 tests も PASS であること**）
5. **Exit Criteria の全項目チェックが完了してからコミットする**（TC PASS だけではコミット条件を満たさない）
6. コミットする（例: `feat(it-1): yaml_diff フレームワーク実装`）
7. `plans/yaml_diff_plan.md` の Iteration 状態を `done` に更新する

## 各 Iteration の入口・出口条件

### 入口条件（全 IT 共通）

- 前 Iteration の状態が `done` であること（IT-1 は例外）

---

### IT-1 Exit Criteria（コミット前に全項目確認）

| # | 確認内容 | 適用観点 |
|---|---------|---------|
| 1 | TC-11, TC-12a, TC-12b, TC-12c, TC-17 が全て PASS | — |
| 2 | 既存 65 tests が全て PASS | — |
| 3 | 副作用の実行順序（argparse → 存在チェック → mkdir → YAML読込 → write_report）がコードと一致している。`--dry-run` 指定時は mkdir と write_report をスキップすることをコードで確認した | R-4 |
| 4 | `DiffEntry` の `before`/`after` フィールドコメントが D-7（追加: `before=""`, `after=id`）と一致している | R-6 |
| 5 | `spec_path` 引数が現時点では未使用と plan に明記されており、固定パスロードであることをコードで確認した | R-5 |

---

### IT-2 Exit Criteria（コミット前に全項目確認）

| # | 確認内容 | 適用観点 |
|---|---------|---------|
| 1 | UT-1, TC-1〜6, TC-10 が全て PASS | — |
| 2 | 既存 65 tests + IT-1 の TC が全て PASS | — |
| 3 | `{e['RequirementId']: e for e in reversed(lst)}` の `reversed()` がコードに存在し、先頭優先になっていることを確認した | R-1 |
| 4 | `_val_to_str` の `list` / `None` / `else` 3パスが全て UT-1 でカバーされている | R-7 |
| 5 | set 差集合・積集合・Union の全箇所に `sorted()` があり、テストに `entries[N]` インデックス依存のアサートがない | R-9 |
| 6 | 全 TC のアサートが `any(e.diff_type == X and e.key_path == Y and e.before == B and e.after == A for e in entries)` 形式であり、`DiffEntry(...) in entries` を使っていない | R-11 |

---

### IT-3 Exit Criteria（コミット前に全項目確認）

| # | 確認内容 | 適用観点 |
|---|---------|---------|
| 1 | TC-7, TC-8, TC-9 が全て PASS | — |
| 2 | 既存 tests + IT-1/IT-2 の TC が全て PASS | — |
| 3 | `pair_yaml_files` が DiffEntry を生成せず tuple のみ返すことをコードで確認した（責務範囲が §2-1 と一致） | R-3 |
| 4 | budget のエントリ追加/削除の `before`/`after` が D-7 と一致している | R-6 |
| 5 | TC-8 のアサートが追加/削除の**両方向**を各々 `any()` でカバーしている | R-10 |
| 6 | TC-9 のアサートがファイル追加/消失の**両方向**を各々 `any()` でカバーしている | R-10 |

---

### IT-4 Exit Criteria（コミット前に全項目確認）

| # | 確認内容 | 適用観点 |
|---|---------|---------|
| 1 | TC-15, TC-15b が全て PASS | — |
| 2 | 既存 tests 全て PASS | — |
| 3 | `write_report()` 完了（JSON 書き出し）後に `SystemExit(1)` する順序がコードと一致している | R-4 |
| 4 | `--check-coverage` 未指定時に `uncovered_diff_types` キーが JSON に**存在しない**ことが TC-15 でアサートされている | R-8 |

---

### IT-5 Exit Criteria（コミット前に全項目確認）

| # | 確認内容 | 適用観点 |
|---|---------|---------|
| 1 | TC-13, TC-14 が全て PASS | — |
| 2 | 既存 tests 全て PASS | — |
| 3 | TC-13（未カバーあり → exit=1）と TC-14（全カバー → exit=0）が**別々の TC** として存在する | R-2 |
| 4 | `spec_path` 引数が現実装で使用されておらず、`cause_classifier.py` は `Path(__file__).parent / 'cause_classifier.py'` で固定ロードされていることをコードで確認した | R-5 |

---

### IT-6 Exit Criteria（コミット前に全項目確認）

| # | 確認内容 | 適用観点 |
|---|---------|---------|
| 1 | TC-16 が PASS | — |
| 2 | 全 tests が PASS（65 + 新規 TC 全件） | — |
| 3 | セルフレビュー表（§IT-6 の全行）が全て OK で埋まっており、空セルがない | R-8 |
| 4 | `plans/yaml_diff_plan.md` / `design/yaml_diff_spec.json` / 本プロンプトが最新状態であることを確認した | R-8 |

---

## テストケース一覧

| TC | 内容 | Iteration |
|----|------|-----------|
| TC-1 | after のみに存在する RequirementId が `diff_type='エントリ追加'` で記録されること | IT-2 |
| TC-2 | before のみに存在する RequirementId が `diff_type='エントリ削除'` で記録されること | IT-2 |
| TC-3a | `SequenceStartTimeSlotList` が変化したとき `diff_type='タイムスロット変化'` になること | IT-2 |
| TC-3b | `SenderStartTimeSlotList` が変化したとき `diff_type='タイムスロット変化'` になること（spec: 「または」の両フィールド） | IT-2 |
| TC-4 | after エントリにのみ存在するキーが `diff_type='キー追加（YAML）'` になること | IT-2 |
| TC-5 | before エントリにのみ存在するキーが `diff_type='キー削除（YAML）'` になること | IT-2 |
| TC-6 | タイムスロット以外の値変化が `diff_type='値変化（YAML）'` になること | IT-2 |
| TC-7 | TaskList が変化した BudgetGroupID が `diff_type='BudgetGroup変化'` になること（json.dumps 順序あり比較） | IT-3 |
| TC-8 | budget.yaml のエントリ追加/削除が正しく分類されること | IT-3 |
| TC-9 | ファイル追加（YAML）/ ファイル消失（YAML）が正しく記録されること | IT-3 |
| TC-10 | 差分なし → `entries=[], diff_types=[]` で出力されること（zero case） | IT-2 |
| TC-11 | `--out` の親ディレクトリが存在しなくても出力ファイルが生成されること | IT-1 |
| TC-12a | `--before` 未指定 → exit=2 | IT-1 |
| TC-12b | `--after` に存在しないパス → exit=3 | IT-1 |
| TC-12c | `--before` に存在しないパス → exit=3（R-2: --before/--after 両方向を対称にテスト） | IT-1 |
| TC-13 | `--check-coverage` で未カバー diff_type がある → exit=1 + stdout に diff_type 名が含まれること | IT-5 |
| TC-14 | `--check-coverage` で全カバー → exit=0 + `uncovered_diff_types=[]` が JSON に含まれること | IT-5 |
| TC-15 | 出力 JSON が `{"generated_at","before_dir","after_dir","diff_types","entries"}` を含み、`--check-coverage` 未指定時 `uncovered_diff_types` キーが**存在しない**こと | IT-4 |
| TC-15b | entries 各要素が `{"file","diff_type","key_path","before","after"}` の**5フィールドのみ**（余分フィールドなし） | IT-4 |
| TC-16 | 実データ（m01 before/after）で `returncode=0` かつ `BudgetGroup変化` 12件が含まれること | IT-6 |
| TC-17 | `--dry-run` 指定時 → `--out` ファイルが生成されない・stdout に件数が出力される・exit=0 | IT-1 |

## セルフレビュー（IT-6 で必須）

`design/yaml_diff_spec.json` の全 processing_steps（step1〜step5）・CLI・schema と実装を突き合わせた表を作成し、
全て OK であることを確認してからコミットする。

## 制約

- 外部ライブラリは PyYAML のみ（`import yaml`）。それ以外は標準ライブラリ（`json`, `pathlib`, `argparse`, `datetime`, `dataclasses`, `importlib.util`, `inspect`, `re`）
- `subprocess` は使わない（実行コストが高い）
- `yaml.safe_load` を使う（`yaml.load` は使わない）

## カバレッジチェック実装詳細（IT-5 参照）

`_collect_known_diff_types(spec_path: Path) -> set[str]` の実装方針（方式B）:

```python
import importlib.util, inspect, re
from pathlib import Path

def _collect_known_diff_types(spec_path: Path) -> set[str]:
    """cause_classifier.py の MATCHER_REGISTRY を inspect して既知 diff_type を収集する。"""
    cc_path = Path(__file__).parent / 'cause_classifier.py'
    spec = importlib.util.spec_from_file_location('cause_classifier', cc_path)
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)

    known: set[str] = set()
    for _mid, _grp, match_fn, _cause in cc.MATCHER_REGISTRY:
        src = inspect.getsource(match_fn)
        known.update(re.findall(r"diff_type\s*==\s*'([^']+)'", src))
        for tup in re.findall(r"diff_type\s+in\s+\(([^)]+)\)", src):
            known.update(re.findall(r"'([^']+)'", tup))
    return known
```

`spec_path` 引数は将来 diff_type_list.json 等を参照する拡張性のために残す（現時点では使用しない）。

---

## 計画・設計レビュー観点（実装前チェックリスト）

実装前に以下の観点でコードと計画を確認し、全て OK であることを証明してから IT-N を完了とすること。

| # | 観点 | チェック内容 |
|---|------|------------|
| R-1 | **Python dict 内包の先勝ち/後勝ち** | `{e[key]: e for e in lst}` は後勝ち。「先頭優先」が必要な場所では必ず `reversed(lst)` を使っているか確認する |
| R-2 | **`or`/`and` 条件のテスト網羅** | spec に「A または B」と書かれた条件（例: SequenceStartTimeSlotList または SenderStartTimeSlotList）は A と B を**別々の TC** でカバーしているか |
| R-3 | **責務が2箇所に分散する関数の整合** | 設計セクション（§2-x）と IT-x 実装内容が同じ責務範囲を記述しているか。矛盾があれば IT-x を修正する |
| R-4 | **副作用の順序** | ファイル書き出し → exit / mkdir → 書き出し → エラー時残骸など、複数副作用の順序を plan に明記し、実装がその順序に従っているか |
| R-5 | **「将来の拡張用」引数の現行動作** | 拡張用と明記した引数が現実装でどう扱われるか（無視か検証か）を plan に明記し、テストで確認しているか |
| R-6 | **DiffEntry before/after の非対称性** | エントリ追加/削除で `before` と `after` の役割は**非対称**。追加: `before=""`, `after=id`。削除: `before=id`, `after=""`。コメントと実装が D-7 設計決定と一致しているか確認する |
| R-7 | **ユーティリティ関数の全パス TC** | `_val_to_str` のような変換ヘルパーは `list`/`None`/`else` の全パスを**単体 TC（UT-1）** で確認する。実データに特定の型の値がなくてもテストを省略しない |
| R-8 | **設計変更の波及先を全ファイルで確認** | D-N のような設計決定・変更が発生したとき、影響する全ドキュメント（plan の各§・IT-N・spec.json・prompt.md）を一覧にして**同じラウンドで全て修正**する。1ファイルで修正したら他のファイルへの横展開を省略しない |
| R-9 | **set 演算の順序不定 → テストは `any()` で確認** | `set` 差集合・積集合（`keys() - keys()` / `keys() & keys()`）は順序不定。実装は `sorted()` で固定し、テストは `entries[0]` 等のインデックス依存アサートを**禁止**。`any()` で diff 内容（diff_type/key_path/before/after）を確認する（R-11 参照） |
| R-10 | **TC 間の横展開（TC-N に加えた修正は全 TC に適用）** | TC-1/2 に期待値を追記したなら TC-3〜10 にも同じ粒度で追記する。TC-12b を追加したなら対称となる TC-12c も同時に追加する。**1つの TC を修正・追加したら同種の全 TC を確認する** |
| R-11 | **dataclass の全フィールド一致アサートは `file` 等の付随フィールドで TypeError になる** | `DiffEntry` のような複数フィールド dataclass を `in entries` でアサートするとき、`file` 等の関心外フィールドが必須の場合は TypeError。テストは `any(e.diff_type == X and e.key_path == Y and e.before == B and e.after == A for e in entries)` 形式を使い `file` を省略する |
