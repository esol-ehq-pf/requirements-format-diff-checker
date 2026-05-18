# cause_classifier マッチャープラグインディレクトリ

このディレクトリに配置した `*.py` ファイルは、`cause_classifier.py` の起動時に
自動でロードされ、MATCHER_REGISTRY / ROUTING_TABLE に追記されます。
`cause_classifier.py` 本体を修正せずに新しい照合ロジックを追加できます。

---

## プラグインファイルの作成方法

各 `.py` ファイルに以下の変数を定義します（どちらか一方だけでも可）。

### MATCHER_ENTRIES

新しいマッチャーを登録します。

```python
# m_22_example.py

def _match_M22(diff_type: str, old_val: str, **_) -> bool:
    """カスタム照合ロジックの例。"""
    return diff_type == "特定の差分タイプ" and old_val.startswith("prefix_")

def _cause_M22(old_val: str, **_) -> str:
    """動的な cause タグを返す例（固定文字列でも可）。"""
    return f"custom_cause({old_val[:10]})"

MATCHER_ENTRIES = [
    # (matcher_id, level, match_fn, cause_tag_or_fn)
    # level: "G-1"（優先）または "G-2"（フォールバック）
    ("M-22", "G-1", _match_M22, _cause_M22),
]
```

### ROUTING_ENTRIES

このマッチャーを適用するファイルパターンを登録します。
（`cause_rules.json` の `routing_table` でも同様に追加可能）

```python
ROUTING_ENTRIES = [
    # (fnmatch形式のファイルパターン, [matcher_id, ...])
    ("*custom_output*.csv", ["M-22"]),
]
```

---

## 利用可能なコンテキストキー（match_fn の引数）

`match_fn(**ctx)` で渡される `ctx` の全キー:

| キー | 型 | 説明 |
|------|----|------|
| `file_name` | str | 差分が発生したファイル名 |
| `diff_type` | str | 差分タイプ（例: "値の変化"） |
| `old_val` | str | 変更前の値 |
| `new_val` | str | 変更後の値 |
| `old` | str | `old_val` の別名 |
| `new` | str | `new_val` の別名 |
| `swc_node_map` | dict | SWC→ノード名マップ（cause_rules.json から） |
| `budget_alias_map` | dict | バジェットエイリアスマップ（cause_rules.json から） |

---

## 注意事項

- ファイル名の辞書順（`sorted()`）でロードされます。
- 既存の matcher_id（M-01〜M-21）と同じ ID を指定すると上書きされます（後勝ち）。
- ロードに失敗したファイルは警告を出力してスキップされます。
- プラグインのテストは `test/test_cause_classifier.py` に追加してください。
