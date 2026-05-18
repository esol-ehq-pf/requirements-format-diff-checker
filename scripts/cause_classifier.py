#!/usr/bin/env python3
"""cause_classifier.py

annotations.json の details エントリに cause タグを自動付与し、
summary / detail の 2 CSV を出力するとともに annotations.json を上書きする。

使い方:
    python3 scripts/cause_classifier.py \\
        --annotations output/ver1_m02_output_diff_annotations.json \\
        [--rules design/cause_rules.json] \\
        [--out-prefix output/ver1_m02]
"""

import argparse
import csv
import fnmatch
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ─────────────────────────────── routing ──────────────────────────────────

# file_pattern (fnmatch) → applicable matcher IDs
# 複数パターンに同じファイルが一致する場合は全 matchers のユニオンを使用する
ROUTING_TABLE = [
    ("*cpuload_requirements.csv", ["M-01", "M-04", "M-11"]),
    ("before_requirements.csv",   ["M-01", "M-02", "M-03", "M-05", "M-12", "M-13", "M-20"]),
    ("after_requirements.csv",    ["M-01", "M-02", "M-03", "M-05", "M-12", "M-13", "M-20"]),
    ("before_budget.csv",         ["M-08", "M-09", "M-14"]),
    ("input_data_ba.csv",         ["M-10", "M-16"]),
    ("input_data_igr.csv",        ["M-10", "M-16"]),
    ("input_info.txt",            ["M-06", "M-07"]),
    ("processing_time_result.csv",["M-01", "M-04", "M-11"]),
    ("schedule_result.csv",       ["M-01", "M-13", "M-20", "M-21"]),
    ("schedule_result_fail_list.csv", ["M-13", "M-20"]),
    ("before_csv_data_tsync_PlusBA.csv", ["M-15", "M-17"]),
    ("after_csv_data_tsync_PlusBA.csv",  ["M-15", "M-17"]),
    ("*.png",                     ["M-18", "M-19"]),
]


def get_applicable_matchers(file_path: str) -> list[str]:
    """ファイルパスの basename を routing table と照合して matcher ID リストを返す。"""
    basename = os.path.basename(file_path)
    result: list[str] = []
    for pattern, matchers in ROUTING_TABLE:
        if fnmatch.fnmatch(basename, pattern):
            for m in matchers:
                if m not in result:
                    result.append(m)
    return result


# ─────────────────────────────── helpers ──────────────────────────────────

def _remove_brackets(s: str) -> str:
    """括弧とその内容を全て除去する（最外括弧のみ対応）。"""
    return re.sub(r'\(.*\)', '', s).strip()


def _normalize(s: str) -> str:
    """括弧除去 + 小文字化。"""
    return _remove_brackets(s).lower()


def _budget_key(old: str) -> str:
    """M-14 用: SplAd(X) なら X、それ以外は括弧除去した文字列を返す。"""
    m = re.match(r'^SplAd\((.+)\)$', old)
    return m.group(1) if m else _remove_brackets(old)


# ────────────────────────── matcher conditions ────────────────────────────

def _match_M01(old: str, new: str, **_) -> bool:
    return _normalize(old) == new


def _cause_M01(old: str, **_) -> str:
    return 'infsimyml(1-①)' if '(' in old else 'chksimyml(2-③)'


def _match_M02(old: str, new: str, **_) -> bool:
    # (a) X → X/X（括弧なし自己参照）
    if new == f'{old}/{old}':
        return True
    # (b) X(sfx) → normalize(X)/X(sfx)
    if '/' in new:
        lhs, rhs = new.split('/', 1)
        if rhs == old and _normalize(lhs) == _normalize(old):
            return True
    return False


def _match_M03(old: str, new: str, **_) -> bool:
    return new == f'Preempt/{old}'


def _match_M04(diff_type: str, **_) -> bool:
    return diff_type == 'TaskIDの追加'


def _match_M05(diff_type: str, new_val: str, **_) -> bool:
    return diff_type == 'キーの追加' and 'Target' in new_val


def _match_M06(old: str, new: str, **_) -> bool:
    return old.startswith('Tool Tag:') and new.startswith('Tool Branch:')


def _match_M07(old: str, new: str, **_) -> bool:
    return 'TSS4_1AR2_RC01/' in old and ('TSS4_V3_1A_RC01/' in new or 'TSS4_V1' in new)


def _match_M08(old: str, new: str, **_) -> bool:
    return _remove_brackets(old) == new and not old.startswith('SplAd(')


def _match_M09(old: str, new: str, **_) -> bool:
    m = re.match(r'^SplAd\((.+)\)$', old)
    return bool(m) and m.group(1) == new


def _match_M10(diff_type: str, **_) -> bool:
    return diff_type in ('pf_1ms_base行の消失', 'pf_1ms_mid行の消失')


def _match_M11(diff_type: str, old_val: str, **_) -> bool:
    return diff_type == 'NodeNameの変化' and bool(re.match(r'^pf_1ms_', old_val))


def _match_M12(old: str, new: str, swc_node_map: dict, **_) -> bool:
    if '/' not in new:
        return False
    swc, node = new.split('/', 1)
    if swc != old or old not in swc_node_map:
        return False
    expected = swc_node_map[old]
    if isinstance(expected, str):
        expected = [expected]
    return node in expected


def _match_M13(old: str, new: str, **_) -> bool:
    return '/' in old and new == old.split('/')[0]


def _cause_M13(file_name: str, **_) -> str:
    basename = os.path.basename(file_name)
    table = {
        'schedule_result.csv':        'chksimyml(2-③)',
        'after_requirements.csv':     'ツール起因(18/30)(要確認)',
        'before_requirements.csv':    'ツール起因(19/31)(要確認)',
    }
    return table.get(basename, 'ツール起因(18/19/30/31)(要確認)')


def _match_M14(old: str, new: str, budget_alias_map: dict, **_) -> bool:
    return budget_alias_map.get(_budget_key(old)) == new


def _match_M15(diff_type: str, **_) -> bool:
    return diff_type == 'mid行の時刻値変化'


def _match_M16(diff_type: str, **_) -> bool:
    return diff_type == 'Nodeの順序入れ替わり'


def _match_M17(diff_type: str, **_) -> bool:
    return diff_type in ('pf_1ms_base行の消失', 'pf_1ms_mid行の消失')


def _match_M18(diff_type: str, file_name: str, **_) -> bool:
    name = os.path.basename(file_name)
    return diff_type == 'ファイル消失' and bool(re.match(r'duration_of_PF_1msTask', name))


def _match_M19(diff_type: str, new_val: str, **_) -> bool:
    return diff_type == '画像差分' and 'viddraw' in new_val


def _match_M20(diff_type: str, old_val: str, new_val: str, **_) -> bool:
    if diff_type == 'IsAnteroposteriorRelationFixedの変化':
        return True
    return ('IsAnteroposteriorRelationFixed: false' in old_val
            and 'IsAnteroposteriorRelationFixed: true' in new_val)


def _match_M21(diff_type: str, **_) -> bool:
    return diff_type == 'etcの変化'


# ──────────────────────── matcher registry ────────────────────────────────

# (matcher_id, level, match_fn, cause_tag_or_fn)
# cause_tag_or_fn: str（固定文字列）または callable（動的取得）
MATCHER_REGISTRY: list[tuple[str, str, object, object]] = [
    ("M-01", "G-1", _match_M01, _cause_M01),
    ("M-02", "G-1", _match_M02, "chksimyml(2-①)"),
    ("M-03", "G-1", _match_M03, "chksimyml(2-①)"),
    ("M-04", "G-1", _match_M04, "infsimyml(1-③)"),
    ("M-05", "G-1", _match_M05, "chksimyml(2-②)"),
    ("M-06", "G-1", _match_M06, "slot.yaml(3-①) / ver3ツール使用(25)"),
    ("M-07", "G-1", _match_M07, "ver3 req path(26)"),
    ("M-08", "G-1", _match_M08, "budget.yaml(4-②A)"),
    ("M-09", "G-1", _match_M09, "budget.yaml(4-②B)"),
    ("M-10", "G-1", _match_M10, "ツール起因(21/23)"),
    ("M-11", "G-1", _match_M11, "ツール起因(9/28)"),
    ("M-15", "G-1", _match_M15, "infsimyml(1-③)"),
    ("M-16", "G-1", _match_M16, "ツール起因(22/24)"),
    ("M-17", "G-1", _match_M17, "ツール起因(パターン9/28の連鎖)"),
    ("M-18", "G-1", _match_M18, "ツール起因(パターン9/28の連鎖)"),
    ("M-19", "G-1", _match_M19, "chksimyml(2-③)"),
    ("M-20", "G-1", _match_M20, "chksimyml(2-①)"),
    ("M-21", "G-1", _match_M21, "chksimyml(2-①)"),
    # G-2 matchers（G-1 未マッチ時に試行）
    ("M-12", "G-2", _match_M12, "chksimyml(2-①)"),
    ("M-13", "G-2", _match_M13, _cause_M13),
    ("M-14", "G-2", _match_M14, "budget.yaml(4-②C)"),
]

_MATCHER_MAP: dict[str, tuple] = {mid: (level, fn, cause) for mid, level, fn, cause in MATCHER_REGISTRY}


# ──────────────────────────── plugin loader ───────────────────────────────

def load_plugin_matchers(matchers_dir: Path) -> None:
    """matchers_dir 内の Python プラグインを動的ロードして MATCHER_REGISTRY /
    _MATCHER_MAP / ROUTING_TABLE に追加する。

    各プラグインファイルは以下の変数を定義できる:

    MATCHER_ENTRIES: list[tuple[str, str, callable, str | callable]]
        (matcher_id, level, match_fn, cause_tag_or_fn)
        matcher_id : 重複する ID は後勝ちで上書きされる。
        level      : "G-1" または "G-2"。
        match_fn   : match_fn(**ctx) -> bool。ctx キーは classify_detail 参照。
        cause_tag_or_fn: str 固定値または callable(**ctx) -> str。

    ROUTING_ENTRIES: list[tuple[str, list[str]]]
        (file_pattern, [matcher_id, ...])  ← fnmatch 形式。
    """
    import importlib.util
    for path in sorted(matchers_dir.glob("*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as e:
            print(f"[warn] plugin load failed: {path.name}: {e}", file=sys.stderr)
            continue
        for entry in getattr(mod, "MATCHER_ENTRIES", []):
            mid, level, match_fn, cause = entry
            MATCHER_REGISTRY.append(entry)
            _MATCHER_MAP[mid] = (level, match_fn, cause)
        for entry in getattr(mod, "ROUTING_ENTRIES", []):
            ROUTING_TABLE.append(entry)


# auto-load plugins from scripts/matchers/ if the directory exists
_PLUGIN_DIR = Path(__file__).parent / "matchers"
if _PLUGIN_DIR.is_dir():
    load_plugin_matchers(_PLUGIN_DIR)


# ──────────────────────────── classification ──────────────────────────────

def classify_detail(
    file_name: str,
    diff_type: str,
    old_val: str,
    new_val: str,
    applicable_matchers: list[str],
    swc_node_map: dict,
    budget_alias_map: dict,
) -> tuple[str, str, str]:
    """(cause_tag, level, pattern_no) を返す。マッチなし時は ('Unknown', 'Unknown', '')。"""
    ctx = dict(
        file_name=file_name,
        diff_type=diff_type,
        old=old_val,
        new=new_val,
        old_val=old_val,
        new_val=new_val,
        swc_node_map=swc_node_map,
        budget_alias_map=budget_alias_map,
    )

    # G-1 を先に試行
    for mid in applicable_matchers:
        if mid not in _MATCHER_MAP:
            continue
        level, match_fn, cause_fn = _MATCHER_MAP[mid]
        if level != "G-1":
            continue
        try:
            if match_fn(**ctx):
                cause = cause_fn(**ctx) if callable(cause_fn) else cause_fn
                return cause, "G-1", mid
        except Exception:
            pass

    # G-2 を試行
    for mid in applicable_matchers:
        if mid not in _MATCHER_MAP:
            continue
        level, match_fn, cause_fn = _MATCHER_MAP[mid]
        if level != "G-2":
            continue
        try:
            if match_fn(**ctx):
                cause = cause_fn(**ctx) if callable(cause_fn) else cause_fn
                return cause, "G-2", mid
        except Exception:
            pass

    return "Unknown", "Unknown", ""


# ──────────────────────────────── main ────────────────────────────────────

def load_rules(rules_path: str) -> tuple[dict, dict]:
    """cause_rules.json から SWC_NODE_MAP と BUDGET_ALIAS_MAP を取得する。

    cause_rules.json に "routing_table" キーが存在する場合、そのエントリを
    ROUTING_TABLE に追記する（既存パターンと重複するものはスキップ）。
    各エントリの形式: {"pattern": "<fnmatch>", "matchers": ["M-XX", ...]}
    """
    with open(rules_path, encoding="utf-8") as f:
        rules = json.load(f)
    swc_node_map = {k: v for k, v in rules.get("SWC_NODE_MAP", {}).items() if not k.startswith("_")}
    budget_alias_map = {k: v for k, v in rules.get("BUDGET_ALIAS_MAP", {}).items() if not k.startswith("_")}
    existing_patterns = {p for p, _ in ROUTING_TABLE}
    for entry in rules.get("routing_table", []):
        pattern = entry.get("pattern", "")
        matchers = entry.get("matchers", [])
        if pattern and pattern not in existing_patterns:
            ROUTING_TABLE.append((pattern, matchers))
            existing_patterns.add(pattern)
    return swc_node_map, budget_alias_map


def run(annotations_path: str, rules_path: str, out_prefix: str) -> None:
    # 入力読み込み
    with open(annotations_path, encoding="utf-8") as f:
        annotations = json.load(f)
    swc_node_map, budget_alias_map = load_rules(rules_path)

    entries: dict = annotations.get("entries", {})

    detail_rows: list[dict] = []
    summary_acc: dict[str, dict] = defaultdict(lambda: {"count": 0, "files": set()})

    for file_key, entry in entries.items():
        file_name: str = entry.get("file", file_key)
        details: list[dict] = entry.get("details", [])
        applicable = get_applicable_matchers(file_name)

        for detail in details:
            diff_type = detail.get("diff_type", "")
            old_val   = detail.get("old_val", "")
            new_val   = detail.get("new_val", "")

            # 既に cause が記入済みの場合はスキップ（手動入力を尊重）
            if detail.get("cause", ""):
                cause    = detail["cause"]
                level    = ""
                pattern_no = ""
            else:
                cause, level, pattern_no = classify_detail(
                    file_name=file_name,
                    diff_type=diff_type,
                    old_val=old_val,
                    new_val=new_val,
                    applicable_matchers=applicable,
                    swc_node_map=swc_node_map,
                    budget_alias_map=budget_alias_map,
                )
                # annotations.json を更新
                detail["cause"] = cause

            detail_rows.append({
                "file":       file_name,
                "diff_type":  diff_type,
                "old_val":    old_val,
                "new_val":    new_val,
                "cause_tag":  cause,
                "level":      level,
                "note":       pattern_no,
            })

            key = (cause, pattern_no, level)
            summary_acc[key]["count"] += 1
            summary_acc[key]["files"].add(os.path.basename(file_name))

    # cause_detail.csv
    detail_path = f"{out_prefix}_cause_detail.csv"
    os.makedirs(os.path.dirname(detail_path) if os.path.dirname(detail_path) else ".", exist_ok=True)
    with open(detail_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "diff_type", "old_val", "new_val", "cause_tag", "level", "note"])
        writer.writeheader()
        writer.writerows(detail_rows)

    # cause_summary.csv
    summary_path = f"{out_prefix}_cause_summary.csv"
    with open(summary_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["cause_tag", "pattern_no", "level", "count", "files_affected"])
        writer.writeheader()
        for (cause, pattern_no, level), data in sorted(summary_acc.items(), key=lambda x: (x[1]["count"]*-1, x[0][0])):
            writer.writerow({
                "cause_tag":      cause,
                "pattern_no":     pattern_no,
                "level":          level,
                "count":          data["count"],
                "files_affected": "; ".join(sorted(data["files"])),
            })

    # annotations.json 上書き
    with open(annotations_path, "w", encoding="utf-8") as f:
        json.dump(annotations, f, ensure_ascii=False, indent=2)

    print(f"[cause_classifier] detail  -> {detail_path}")
    print(f"[cause_classifier] summary -> {summary_path}")
    print(f"[cause_classifier] updated -> {annotations_path}")

    # 統計
    total = len(detail_rows)
    unknown = sum(1 for r in detail_rows if r["cause_tag"] == "Unknown")
    print(f"[cause_classifier] total={total}  matched={total - unknown}  Unknown={unknown}")


def main() -> None:
    parser = argparse.ArgumentParser(description="annotations.json に cause タグを自動付与する")
    parser.add_argument("--annotations", required=True,
                        help="output_diff.py が生成した annotations.json のパス")
    parser.add_argument("--rules", default=None,
                        help="cause_rules.json のパス（省略時は本スクリプトと同階層の ../design/cause_rules.json）")
    parser.add_argument("--out-prefix", default=None,
                        help="出力ファイルのプレフィックス（省略時は annotations のパスベース）")
    args = parser.parse_args()

    # rules のデフォルトパス解決
    if args.rules is None:
        script_dir = Path(__file__).parent
        args.rules = str(script_dir.parent / "design" / "cause_rules.json")

    # out-prefix のデフォルト解決
    if args.out_prefix is None:
        ann_path = Path(args.annotations)
        args.out_prefix = str(ann_path.parent / ann_path.stem.replace("_annotations", ""))

    run(
        annotations_path=args.annotations,
        rules_path=args.rules,
        out_prefix=args.out_prefix,
    )


if __name__ == "__main__":
    main()
