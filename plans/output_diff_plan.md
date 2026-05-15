# output_diff.py 実装計画

作成日: 2026-05-15  
仕様書: `design/output_diff_spec.json`  
プロンプト: `.github/prompts/implement-output-diff.prompt.md`

---

## フェーズ 1: 調査（完了）

### 1-1. 実データ構造の確認

| 項目 | 内容 |
|------|------|
| 旧フォルダ | `input/scheduling_requirement_check_analysis_result/` |
| 新フォルダ | `input/ver1_m02_AP_再解析結果/output/` |
| 旧ファイル総数 | **287 件**（再帰含む） |
| ファイル種別 | CSV（`.csv`）、テキスト（`.txt`）、PNG 画像（`.png`） |
| サブフォルダ | `processing_load_duration_graph/PASS/` など複数階層あり |

### 1-2. 既存スクリプトの確認（コーディング規約）

`scripts/extract_and_write_diff.py` から以下の規約を採用する：

- `#!/usr/bin/env python3` + docstring ヘッダー
- `argparse.ArgumentParser` に `description` を設定
- `pathlib.Path` でパス操作
- エラー時は `raise SystemExit(N)` で終了
- 標準出力メッセージは `print(f"  ...")` 形式（先頭 2 スペース）

### 1-3. テストスタイルの確認（`test/test_csv_out.py`）

- `subprocess.run([sys.executable, SCRIPT, ...], capture_output=True, text=True)` で実行
- `tmp_path` (pytest fixture) で一時ディレクトリ管理
- `assert result.returncode == 0` でリターンコード確認

### 1-4. 確認された設計課題

| # | 課題 | 対策 |
|---|------|------|
| C-1 | PNG等バイナリとテキストの混在（287件中 PNG 多数） | `binary_extensions` リストでフィルタ、デコードエラー時フォールバック |
| C-2 | サブフォルダ名が日本語（`ver1_m02_AP_再解析結果`） | `pathlib.Path` を使用（マルチバイト対応） |
| C-3 | テキストエンコードが混在（CSV=UTF-8, 一部=Shift-JIS） | `decode_text()` 共通関数で UTF-8 → Shift-JIS → latin-1 フォールバック |
| C-4 | HTML での日本語ファイル名表示 | `<meta charset="utf-8">` + Python の `html.escape()` |

---

## フェーズ 2: 設計

### 2-1. モジュール構成（`scripts/output_diff.py`）

```
scripts/output_diff.py
├── 定数ブロック
│   ├── BINARY_EXTENSIONS: set[str]      # バイナリ拡張子
│   ├── ROW_COLORS: dict[str, str]        # 比較結果 → 背景色（W-2 で値を明示）
│   │     "Different": "#fff3cd"  "Left only": "#f8d7da"
│   │     "Right only": "#d4edda"  "Identical": "#ffffff"
│   ├── CSV_COLUMNS: list[str]            # 出力列名
│   └── DIFF_CONTEXT_LINES: int = 3       # unified diff のコンテキスト行数（W-1: 定数化）
│
├── DiffEntry (dataclass)                 # 中間データ構造
│   ├── name: str                        # ファイル名
│   ├── folder: str                      # 相対フォルダパス
│   ├── result: str                      # Identical/Different/Left only/Right only
│   ├── old_mtime: str                   # 旧更新日時（ISO形式、なければ空）
│   ├── new_mtime: str                   # 新更新日時（ISO形式、なければ空）
│   ├── ext: str                         # 拡張子
│   └── diff_lines: list[str]            # unified diff 行（Different テキストのみ）
│
├── decode_text(data: bytes) -> str       # エンコード検出共通関数
├── is_binary(path: Path) -> bool        # バイナリ判定
├── get_mtime(path: Path) -> str          # 更新日時取得（YYYY-MM-DD HH:MM:SS）
│
├── compare_folders(old: Path, new: Path) -> list[DiffEntry]
│   ├── _collect_relpaths(root: Path) -> set[str]   # 再帰的パス収集
│   └── _compare_file(rel: str, old_root, new_root) -> DiffEntry
│
├── write_csv(entries, out_path)          # CSV 出力
├── write_html(entries, old, new, out)   # HTML 出力
│
└── main()                               # CLI エントリポイント
```

### 2-2. DiffEntry フィールド詳細

```python
@dataclass
class DiffEntry:
    name: str           # Path(rel).name
    folder: str         # str(Path(rel).parent) if parent != "." else ""
    result: str         # "Identical" | "Different" | "Left only" | "Right only"
    old_mtime: str      # "" if Right only
    new_mtime: str      # "" if Left only
    ext: str            # Path(rel).suffix  ("" for folders)
    diff_lines: list[str] = field(default_factory=list)  # W-4: mutable default には field() が必須
                           # unified diff 行（result != "Different" or binary は空リスト）
```

### 2-3. compare_folders アルゴリズム

```
0. [NG-3 対応] _collect_relpaths はファイルのみを返す（ディレクトリは含めない）
   → os.walk の files リストのみを使い、ディレクトリパス自体は収集しない
   → 片方のみに存在するサブフォルダ内のファイルは全て Left only / Right only として記録されるため
     フォルダエントリを別途追加する必要はない
   ※ 仕様書 notes の「フォルダ自体は記録する」はこの実装方針で代替とし、
     設計判断として計画に明記する

1. old_paths = _collect_relpaths(old_root)   # ファイルの相対パス文字列集合（ディレクトリ除く）
2. new_paths = _collect_relpaths(new_root)
3. for rel in old_paths - new_paths  →  Left only
4. for rel in new_paths - old_paths  →  Right only
5. for rel in old_paths & new_paths  →  _compare_file(rel, old_root, new_root)
   5a. is_binary(old) or is_binary(new)  → バイト比較 → Identical / Different
   5b. テキスト: decode_text → 行比較 → Identical / Different
         → diff_lines = list(difflib.unified_diff(..., n=DIFF_CONTEXT_LINES))  # W-1: 定数使用
6. ソート: Different → Left only → Right only → Identical
```

### 2-4. HTML 構造

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>output diff: {old} → {new}</title>
  <style>/* 行色定義 */</style>
</head>
<body>
  <h1>output diff</h1>
  <p>生成日時: {datetime}</p>
  <p>旧: {old} / 新: {new}</p>

  <!-- サマリテーブル -->
  <table>
    <tr><th>比較結果</th><th>件数</th></tr>
    <tr><td>Different</td><td>N</td></tr>
    ...
  </table>

  <!-- 全ファイル一覧 -->
  <table>
    <thead><tr><th>ファイル名</th><th>フォルダ</th>...</tr></thead>
    <tbody>
      <tr style="background:...">
        <td>file.csv</td>
        <td>subdir/</td>
        <td>Different</td>
        <td>2026-05-01 12:00:00</td>
        <td>2026-05-10 15:30:00</td>
        <td>.csv</td>
        <td>                               <!-- Different テキストのみ -->
          <details>
            <summary>差分を表示</summary>
            <pre><span style="background:#fdd">-旧行</span>
<span style="background:#dfd">+新行</span></pre>
          </details>
        </td>
      </tr>
    </tbody>
  </table>
</body>
</html>
```

### 2-5. CLI 設計

```
python3 scripts/output_diff.py
  --old PATH   (required)  旧フォルダ
  --new PATH   (required)  新フォルダ
  --html       (flag)      HTML 出力（デフォルト）
  --csv        (flag)      CSV 出力（--html と排他）
  --out PATH   (optional)  出力先（省略時: output_diff.html / output_diff.csv）
```

**終了コード**:
- 0: 正常終了
- 1: `--old` / `--new` が存在しない、または `--html` と `--csv` を同時指定

**stdout メッセージ**:
```
  比較完了: N 件 → {out_path}
```

---

## フェーズ 3: 実装（イテレーティブ）

各 Iteration の状態: `todo` / `in-progress` / `done`

### IT-1: フレームワーク（状態: `todo`）

**目標**: `scripts/output_diff.py` の骨格を作成し、CLI エラー検出が動くこと

**実装内容**:
1. 定数ブロック（`BINARY_EXTENSIONS`, `ROW_COLORS`＋色コード値, `CSV_COLUMNS`, `DIFF_CONTEXT_LINES`）
2. `DiffEntry` dataclass（`diff_lines: list[str] = field(default_factory=list)`）
3. `main()` — argparse、--html/--csv 排他チェック、フォルダ存在チェック、 `SystemExit(1)`
4. `compare_folders()` はスタブ（空リストを返す）
5. `write_csv()` / `write_html()` はスタブ（ファイルを作るだけ）

**テスト（`test/test_output_diff.py` 新規作成）**:
- TC-7a: `--old` 不在 → `returncode == 1`
- TC-7b: `--new` 不在 → `returncode == 1`  ← **NG-1 対応追加**
- TC-8: `--html --csv` 同時指定 → `returncode == 1`

**コミット**: `feat(it-1): output_diff フレームワーク実装`

---

### IT-2: 比較ロジック（状態: `todo`）

**目標**: フォルダ再帰比較・4分類・テキスト/バイナリ判定が正しく動くこと

**実装内容**:
1. `decode_text(data: bytes) -> str`
2. `is_binary(path: Path) -> bool`
3. `get_mtime(path: Path) -> str`
4. `_collect_relpaths(root: Path) -> set[str]`
5. `_compare_file(rel, old_root, new_root) -> DiffEntry`
6. `compare_folders()` — 4分類・ソート

**テスト追加**:
- TC-1: Identical テキストファイル → `result == "Identical"`
- TC-2: Different テキストファイル → `result == "Different"`
- TC-3: 旧フォルダのみ存在 → `result == "Left only"`
- TC-4: 新フォルダのみ存在 → `result == "Right only"`
- TC-10: バイナリ（PNG 相当）が Identical / Different に正しく分類されること

**コミット**: `feat(it-2): フォルダ比較ロジック実装（4分類）`

---

### IT-3: CSV 出力（状態: `todo`）

**目標**: `--csv` で CSV ファイルが正しく生成されること

**実装内容**:
1. `write_csv(entries: list[DiffEntry], out_path: Path) -> int`
   - BOM 付き utf-8-sig
   - ヘッダ: `CSV_COLUMNS`
   - diff_lines は含めない
2. `main()` の CSV 分岐を有効化
3. stdout メッセージ出力

**テスト追加**:
- TC-6: CSV 生成 → ヘッダ一致・BOM 確認・列数確認
- TC-12: stdout に `比較完了:` と出力パスが含まれること  ← **NG-2 対応追加**

**コミット**: `feat(it-3): CSV 出力実装`

---

### IT-4: HTML 出力（テーブル・行色・サマリ）（状態: `todo`）

**目標**: `--html` でサマリ・全ファイルテーブルを含む HTML が生成されること

**実装内容**:
1. `write_html(entries, old_root, new_root, out_path) -> int`
   - DOCTYPE・meta charset・style（行色）
   - サマリテーブル（比較結果種別ごとの件数）
   - ファイル一覧テーブル（6列 + diff 列プレースホルダー）
   - 行背景色（`ROW_COLORS`）
2. `main()` の HTML 分岐を有効化

**テスト追加**:
- TC-5: HTML 生成 → ファイル存在・`<table>` 含む・行数確認・行色確認・**ソート順（Different が最初）確認**  ← **W-3 対応**

**コミット**: `feat(it-4): HTML 出力実装（テーブル・行色・サマリ）`

---

### IT-5: unified diff 展開（状態: `todo`）

**目標**: Different テキストファイルの行に `<details>` で unified diff が展開されること

**実装内容**:
1. `_compare_file` に `difflib.unified_diff()` 生成追加（`n=DIFF_CONTEXT_LINES`）  ← **W-1: 定数使用**
2. `DiffEntry.diff_lines` への格納
3. `write_html()` の diff セル: `<details><summary>...</summary><pre>...</pre></details>`
   - 追加行（`+` 始まり）: `background:#dfd`
   - 削除行（`-` 始まり）: `background:#fdd`
   - `html.escape()` でエスケープ

**テスト追加**:
- TC-9: Different テキストの HTML → `<details>` タグ含む・`+` / `-` 行を含む

**コミット**: `feat(it-5): unified diff 展開（<details>）実装`

---

### IT-6: セルフレビュー・実データ確認・最終コミット（状態: `todo`）

**目標**: RQ-1〜RQ-9 全充足確認・実データでの動作確認

**作業手順**:

1. **セルフレビュー表の作成**

   | RQ | 要件内容 | 実装箇所 | 判定 |
   |----|----------|----------|------|
   | RQ-1 | --old / --new CLI 引数 | `main()` argparse | |
   | RQ-2 | 再帰比較 | `_collect_relpaths()` | |
   | RQ-3 | 4分類 | `compare_folders()` / `_compare_file()` | |
   | RQ-4 | テキスト行単位比較 | `_compare_file()` + `decode_text()` | |
   | RQ-5 | バイナリバイト比較 | `is_binary()` + バイト読み込み | |
   | RQ-6 | --html / --csv 切り替え | `main()` + `write_html()` / `write_csv()` | |
   | RQ-7 | --out 指定 | `main()` argparse | |
   | RQ-8 | フォルダ不在 → exit=1 | `main()` 存在チェック | |
   | RQ-9 | unified diff 展開 | `write_html()` `<details>` | |

2. **実データでの動作確認**

   ```bash
   cd /home/y-shinohara/adas/work/format-change
   python3 scripts/output_diff.py \
     --old input/scheduling_requirement_check_analysis_result \
     --new input/ver1_m02_AP_再解析結果/output \
     --out output/ver1_m02_output_diff.html
   ```

   確認ポイント:
   - stdout に `比較完了: N 件 → ...` が表示されること
   - HTML を開いてサマリ・行色・diff 展開が正しく表示されること
   - `N` が期待値（旧 287 件 + 新側のみ存在 + 差分）の範囲に収まること

3. **TC-11 追加**（実データ smoke test）:
   - `--old input/... --new input/...` で実行 → `returncode == 0` + HTML ファイル生成

4. **全テスト実行**:
   ```bash
   python3 -m pytest test/test_output_diff.py -v
   ```

5. **コミット**:
   ```bash
   git add scripts/output_diff.py test/test_output_diff.py plans/output_diff_plan.md \
           design/output_diff_spec.json design/infsimyml_diff_spec.json \
           .github/prompts/implement-output-diff.prompt.md
   git commit -m "feat: output_diff.py 実装完了（IT-1〜IT-6）"
   git push
   ```

---

## フェーズ 3.5: extract_and_write_diff との連携懸案（レビュー追加）

`output_diff.py` は `extract_and_write_diff.py` と同じ `--old` / `--new` フォルダを対象に使われる補完ツールである。
以下の連携上の懸案を実装・運用時に考慮すること。

### 懸案 NG-A: フォルダ名の齟齬（表示上の不一致）

| ツール | 表示フォルダ名 | 実フォルダ名 |
|--------|--------------|------------|
| `extract_and_write_diff.py` の Excel 出力 | **`tmp`** (`excel_folder: "tmp"`) | `temp/` |
| `output_diff.py` の HTML/CSV 出力 | **`temp/`**（実パスをそのまま表示） | `temp/` |

**影響**: 両ツールの出力を突き合わせると `tmp` ↔ `temp/` でフォルダ名が一致しない。  
**対応方針（output_diff 側）**: `output_diff.py` は実フォルダ名を表示する（変更しない）。  
ユーザーへの注記として IT-6 の HTML 内タイトルコメントに記載する。  
→ `design/output_diff_spec.json` の `notes` に追記する（IT-6 で実施）。

### 懸案 NG-B: 「差分なし期待ファイル」が output_diff では Different と表示される

`extract_and_write_diff_spec.json` で「差分なし期待」と定義されているファイル：

| ファイル | extract 側の扱い | output_diff 側の表示 |
|---------|-----------------|---------------------|
| `processing_time_SWC_group_result.csv` | エントリ生成なし・FATAL にもならない | 内容が異なれば **Different** |
| `node_straddling_slot_pickup_result.csv` | 同上 | 同上 |
| `temp/after_budget.csv` | 同上 | 同上 |

**影響**: output_diff が Different と報告しても Excel に記録がない → ユーザーが混乱する可能性。  
**対応方針（output_diff 側）**: output_diff.py 本体は変更しない。  
HTML の凡例（フッタ）に「extract_and_write_diff.py の差分なし期待ファイルは Excel 非記録」旨の注記を追加する（IT-6 で実施）。

### 懸案 NG-C: schedule_result.csv の PASS/FAIL 変化が extract 側未実装（TODO）

`extract_and_write_diff_spec.json` 内 `schedule_result_pass_fail` の `"status": "TODO"`。

**現状**: `schedule_result.csv` の PASS/FAIL 判定列変化は Excel に記録されない。  
**output_diff 側での表示**: `schedule_result.csv` が Different の場合は HTML/CSV に表示される。  
**対応方針**: output_diff の HTML で `schedule_result.csv` が Different のとき、  
diff 展開で実際の変化内容を確認できる（IT-5 の unified diff で対応済み）。  
TODO 実装時まではこの HTML diff が一時的な代替手段となる。  
→ IT-6 のセルフレビュー表に RQ 対応として明記する。

### 懸案 W-A: 推奨運用フロー（ツール間の補完関係）

```
Step 1: python3 scripts/output_diff.py --old <旧> --new <新> --out <HTML>
        → ファイルレベルの概観を確認（どのファイルが変わったか）

Step 2: python3 scripts/extract_and_write_diff.py --old <旧> --new <新> --xlsx <Excel>
        → 意味的差分をExcelに記録（フォーマット変更の根拠整理）

Step 3: output_diff の Different 一覧と Excel を突き合わせ、
        extract 側で「差分なし期待」「TODO」「対象外」として未記録のファイルを確認する
```

**IT-6 の実データ確認**にこの Step 3 確認を追加する。

### 懸案 W-B: 画像ファイルの意味付け差異（設計上の合意）

- `extract_and_write_diff.py`: 画像名の類似度（0.7）でリネーム検出 → `画像差分` or `ファイル消失`
- `output_diff.py`: `Left only` / `Right only` として表示（意味付けなし）

**対応方針**: `output_diff.py` は意味付けを行わない（スコープ外）。  
ユーザーは output_diff の `Left only` / `Right only` PNG を extract 側の出力と照合すること。  
この合意を `design/output_diff_spec.json` の `notes` に追記する（IT-6 で実施）。

---

## フェーズ 4: 評価

### 4-1. テストカバレッジ確認

```bash
cd /home/y-shinohara/adas/work/format-change
python3 -m pytest test/test_output_diff.py -v --tb=short
```

全 11 テスト PASS を確認する。

### 4-2. 実データ評価（手動確認）

| 確認項目 | 期待 | 確認結果 |
|---------|------|---------|
| 旧フォルダの全287件が一覧に含まれる | ✓ | |
| PNG ファイルが Identical / Different に正しく分類される | ✓ | |
| CSV ファイルの diff が unified diff で展開される | ✓ | |
| 日本語フォルダ名がHTML上で文字化けしない | ✓ | |
| サマリの合計件数 = 全エントリ数 | ✓ | |

### 4-3. 将来の拡張可能性（保守性確認）

以下の変更が局所的な修正で対応できることを確認する：

| 変更シナリオ | 影響箇所 |
|-------------|---------|
| 新しい出力形式（例: Markdown）を追加 | `write_markdown()` を追加するだけ、`compare_folders()` は無変更 |
| バイナリ拡張子を追加（例: `.pdf`） | `BINARY_EXTENSIONS` 定数のみ変更 |
| 行色テーマを変更 | `ROW_COLORS` 定数のみ変更 |
| context_lines を変更 | `_compare_file()` の定数 1 箇所のみ変更 |

---

## 進捗サマリ

| フェーズ | 状態 |
|---------|------|
| フェーズ 1: 調査 | ✅ 完了 |
| フェーズ 2: 設計 | ✅ レビュー済み（NG-1〜3・W-1〜4 反映済み） |
| フェーズ 3.5: 連携懸案（NG-A〜C・W-A〜B） | ✅ 計画に記録済み |
| IT-1: フレームワーク | `todo` |
| IT-2: 比較ロジック | `todo` |
| IT-3: CSV 出力 | `todo` |
| IT-4: HTML 出力 | `todo` |
| IT-5: unified diff 展開 | `todo` |
| IT-6: セルフレビュー・評価 | `todo` |
| フェーズ 4: 評価 | `todo` |
