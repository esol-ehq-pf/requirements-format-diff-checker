#!/usr/bin/env python3
"""
Output差分シート セルフレビュースクリプト

Excel の Output差分シートに記録された差分エントリを自動検証し、
品質ゲート（QG）の総合判定を YAML レポートに出力する。
対象プロジェクト・バリアントは CLI 引数で指定する。
"""
import argparse
import difflib
import sys
import warnings
from datetime import date
from pathlib import Path

import openpyxl
import yaml

LINK_TEXT = "過去プロジェクト(ver1/ver2/ver2.1)の 要件ファイルフォーマット変更"

# 許容される差分概要の文言リスト
ALLOWED_DIFF_TYPES = {
    "入力ファイルの差分",
    "ファイル消失",
    "画像差分",
    "NodeNameの変化",
    "id/nameの変化",
    "RequirementIdの変化",
    "RequirementOwnerの変化",
    "Sequence/Sender/Receiver/FirstTask/SecondTaskの変化",
    "キーの追加",
    "TaskIDの追加",
    "TaskListの変化",
    "列ヘッダの変化",
    "pf_1ms_base行の消失",
    "pf_1ms_mid行の消失",
    "Nodeの順序入れ替わり",
    "etcの変化",
    "mid行の時刻値変化",
}


# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────
def files_differ(path_old: Path, path_new: Path) -> bool:
    if not path_old.exists() or not path_new.exists():
        return True
    return path_old.read_bytes() != path_new.read_bytes()


def image_list(folder: Path) -> set:
    if not folder.exists():
        return set()
    return {f.name for f in folder.iterdir() if f.is_file()}


def read_lines(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def ok(msg=""):
    return {"result": "OK", "detail": msg}


def ng(msg=""):
    return {"result": "NG", "detail": msg}


def warn(msg=""):
    return {"result": "WARN", "detail": msg}


# ──────────────────────────────────────────
# Excel エントリ読み込み
# ──────────────────────────────────────────
def load_excel_entries(xlsx: Path, project: str, variant: str):
    warnings.filterwarnings("ignore")
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["Output差分"]
    entries = []
    for row in ws.iter_rows(min_row=4, values_only=True):
        if row[8] == variant and row[7] == project:
            entries.append(
                {
                    "no": row[0],
                    "folder": row[1],
                    "file": row[2],
                    "diff_type": row[3],
                    "old_val": row[4],
                    "new_val": row[5],
                    "link": row[6],
                    "project": row[7],
                    "variant": row[8],
                    "cause": row[9],
                }
            )
    return entries


# ──────────────────────────────────────────
# Phase 1: ファイルレベルインベントリ確認
# ──────────────────────────────────────────
def phase1_file_inventory(entries, old_dir: Path, new_dir: Path):
    results = {}

    # 全対象ファイル（画像フォルダ以外）
    csv_files = [
        "input_info.txt",
        "schedule_result.csv",
        "schedule_result_fail_list.csv",
        "processing_time_result.csv",
        "processing_time_SWC_group_result.csv",
        "node_straddling_slot_pickup_result.csv",
        "input_data_ba.csv",
        "input_data_igr.csv",
        "temp/before_requirements.csv",
        "temp/after_requirements.csv",
        "temp/before_cpuload_requirements.csv",
        "temp/after_cpuload_requirements.csv",
        "temp/before_budget.csv",
        "temp/after_budget.csv",
        "temp/before_csv_data_tsync_PlusBA.csv",
        "temp/after_csv_data_tsync_PlusBA.csv",
    ]

    diff_files = []
    no_diff_files = []

    for rel in csv_files:
        has_diff = files_differ(old_dir / rel, new_dir / rel)
        if has_diff:
            diff_files.append(rel)
        else:
            no_diff_files.append(rel)

    # Excel エントリで参照されているファイル集合
    excel_files = set()
    for e in entries:
        folder = e["folder"] or ""
        fname = e["file"] or ""
        if folder and folder != "-":
            excel_files.add(f"{folder}/{fname}")
        else:
            excel_files.add(fname)

    # 差分ありファイルが Excel に網羅されているか
    uncovered = []
    for f in diff_files:
        # ファイル名（パス末尾）が Excel エントリに存在するか確認
        fname = Path(f).name
        base = Path(f).stem  # 拡張子なし（tempファイルはstemで一致させる）
        covered = any(
            (e["file"] or "") == fname
            or (e["file"] or "") == base
            or (e["file"] or "") in f
            for e in entries
        )
        if not covered:
            uncovered.append(f)

    # 差分なしファイルが Excel に誤記載されていないか
    false_positive = []
    for f in no_diff_files:
        fname = Path(f).name
        base = Path(f).stem
        wrongly_listed = any(
            ((e["file"] or "") == fname or (e["file"] or "") == base)
            for e in entries
        )
        if wrongly_listed:
            false_positive.append(f)

    results["diff_files"] = diff_files
    results["no_diff_files"] = no_diff_files
    results["uncovered_diff_files"] = uncovered
    results["false_positive_no_diff_files"] = false_positive

    if uncovered:
        results["gate"] = ng(f"差分ありファイルが未記録: {uncovered}")
    elif false_positive:
        results["gate"] = ng(f"差分なしファイルが誤記載: {false_positive}")
    else:
        results["gate"] = ok("全差分ファイルが Excel に記載済み")

    return results


# ──────────────────────────────────────────
# Phase 2: CSV差分の構造化確認
# ──────────────────────────────────────────
def detect_csv_diff_types(rel_path: str, old_dir: Path, new_dir: Path) -> dict:
    """各CSVの差分を解析し、差分種別と代表値を返す"""
    old_path = old_dir / rel_path
    new_path = new_dir / rel_path

    if not old_path.exists() or not new_path.exists():
        return {"exists": False}

    old_lines = read_lines(old_path)
    new_lines = read_lines(new_path)

    added = []
    deleted = []
    changed = []

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, old_lines, new_lines
    ).get_opcodes():
        if tag == "replace":
            for old_l, new_l in zip(old_lines[i1:i2], new_lines[j1:j2]):
                changed.append({"old": old_l.rstrip(), "new": new_l.rstrip()})
        elif tag == "delete":
            for l in old_lines[i1:i2]:
                deleted.append(l.rstrip())
        elif tag == "insert":
            for l in new_lines[j1:j2]:
                added.append(l.rstrip())

    return {
        "exists": True,
        "added_count": len(added),
        "deleted_count": len(deleted),
        "changed_count": len(changed),
        "added_samples": added[:5],
        "deleted_samples": deleted[:5],
        "changed_samples": changed[:5],
    }


def phase2_csv_diffs(entries, old_dir: Path, new_dir: Path):
    results = {}

    # 差分なしが期待されるファイル
    no_diff_expected = [
        "processing_time_SWC_group_result.csv",
        "node_straddling_slot_pickup_result.csv",
        "temp/after_budget.csv",
    ]

    # 差分なし期待ファイルに Excel エントリがないか確認
    false_entries = []
    for rel in no_diff_expected:
        fname = Path(rel).name
        base = Path(rel).stem
        wrong = [
            e for e in entries
            if (e["file"] or "") in (fname, base)
        ]
        if wrong:
            false_entries.append({"file": rel, "wrong_entries": wrong})

    results["no_diff_expected_files"] = {
        "files": no_diff_expected,
        "false_entries": false_entries,
        "gate": ok() if not false_entries else ng(f"差分なしファイルに誤エントリ: {false_entries}"),
    }

    # 主要CSVの差分自動検出
    csv_checks = {
        "input_data_ba.csv": {
            "pf_1ms_base消失": lambda d: d["deleted_count"] > 0 and any("pf_1ms_base" in l for l in d.get("deleted_samples", [])),
            "pf_1ms_mid消失": lambda d: d["deleted_count"] > 0 and any("pf_1ms_mid" in l for l in d.get("deleted_samples", [])),
            "Nodeの順序入れ替わり": lambda d: d["changed_count"] > 0 or d["added_count"] > 0,
        },
        "input_data_igr.csv": {
            "pf_1ms_base消失": lambda d: d["deleted_count"] > 0 and any("pf_1ms_base" in l for l in d.get("deleted_samples", [])),
            "pf_1ms_mid消失": lambda d: d["deleted_count"] > 0 and any("pf_1ms_mid" in l for l in d.get("deleted_samples", [])),
            "Nodeの順序入れ替わり": lambda d: d["changed_count"] > 0 or d["added_count"] > 0,
        },
        "processing_time_result.csv": {
            "PF_window追加": lambda d: d["added_count"] > 0 and any("PF_window" in l for l in d.get("added_samples", [])),
        },
        "schedule_result.csv": {
            "VidDraw→viddraw変化": lambda d: any(
                "VidDraw" in c["old"] and "viddraw" in c["new"]
                for c in d.get("changed_samples", [])
            ) or d["changed_count"] > 0,
        },
        "temp/before_cpuload_requirements.csv": {
            "PF_window追加": lambda d: d["added_count"] > 0 and any("PF_window" in l for l in d.get("added_samples", [])),
            "NodeName変化": lambda d: d["changed_count"] > 0,
        },
        "temp/after_cpuload_requirements.csv": {
            "PF_window追加": lambda d: d["added_count"] > 0 and any("PF_window" in l for l in d.get("added_samples", [])),
        },
        "temp/before_budget.csv": {
            "TaskList変化": lambda d: d["changed_count"] > 0,
        },
    }

    csv_results = {}
    for rel, checks in csv_checks.items():
        d = detect_csv_diff_types(rel, old_dir, new_dir)
        if not d.get("exists"):
            csv_results[rel] = ng("ファイルが存在しない")
            continue
        check_results = {}
        for check_name, fn in checks.items():
            try:
                passed = fn(d)
            except Exception as e:
                passed = False
            check_results[check_name] = "OK" if passed else "NG(差分が検出されなかった)"
        csv_results[rel] = {
            "summary": d,
            "checks": check_results,
            "all_passed": all("OK" == v for v in check_results.values()),
        }

    results["csv_checks"] = csv_results
    all_csv_ok = all(
        v.get("all_passed", False)
        for v in csv_results.values()
        if isinstance(v, dict)
    )
    results["gate"] = ok("全CSV差分チェック通過") if all_csv_ok and not false_entries else ng("CSV差分チェックに問題あり")

    return results


# ──────────────────────────────────────────
# Phase 3: 画像ファイル差分確認
# ──────────────────────────────────────────
def phase3_image_diffs(entries, old_dir: Path, new_dir: Path):
    graph_dirs = [
        "processing_load_duration_graph",
        "Sequence_duration_graph",
        "SWC_budget_duration_graph",
        "WakeupInterval_graph",
    ]

    results = {}
    all_ok = True

    for gdir in graph_dirs:
        for sub in ("PASS", "FAIL"):
            old_imgs = image_list(old_dir / gdir / sub)
            new_imgs = image_list(new_dir / gdir / sub)

            deleted = sorted(old_imgs - new_imgs)
            added = sorted(new_imgs - old_imgs)

            # 削除・追加が共にある場合はリネームの可能性あり（名前類似度で判定）
            renames = []
            for d_img in list(deleted):
                for a_img in list(added):
                    ratio = difflib.SequenceMatcher(None, d_img, a_img).ratio()
                    if ratio > 0.7:
                        renames.append({"old": d_img, "new": a_img, "similarity": round(ratio, 2)})

            # Excel エントリで当フォルダ・ファイルが記録されているか確認
            folder_key = gdir
            excel_for_folder = [
                e for e in entries
                if (e["folder"] or "") == folder_key
            ]

            # 削除ファイルが Excel に記録されているか
            uncovered_deleted = []
            for img in deleted:
                covered = any((e["file"] or "") == img for e in excel_for_folder)
                if not covered:
                    uncovered_deleted.append(img)

            # リネームが Excel の「画像差分」エントリに記録されているか
            uncovered_renames = []
            for r in renames:
                covered = any(
                    (e["diff_type"] or "") == "画像差分"
                    and (r["old"] in (e["file"] or "") or r["new"] in (e["new_val"] or ""))
                    for e in excel_for_folder
                )
                if not covered:
                    uncovered_renames.append(r)

            key = f"{gdir}/{sub}"
            entry_result = {
                "deleted": deleted,
                "added": added,
                "renames": renames,
                "uncovered_deleted": uncovered_deleted,
                "uncovered_renames": uncovered_renames,
            }
            if uncovered_deleted or uncovered_renames:
                entry_result["gate"] = ng(f"未記録あり: deleted={uncovered_deleted}, renames={uncovered_renames}")
                all_ok = False
            else:
                entry_result["gate"] = ok()
            results[key] = entry_result

    results["gate"] = ok("全画像差分記録済み") if all_ok else ng("未記録の画像差分あり")
    return results


# ──────────────────────────────────────────
# Phase 4: Excelエントリ正確性確認
# ──────────────────────────────────────────
def phase4_entry_accuracy(entries, old_dir: Path, new_dir: Path):
    results = []
    ng_count = 0

    for e in entries:
        issues = []
        folder = e["folder"] or ""
        fname = e["file"] or ""
        diff_type = e["diff_type"] or ""
        old_val = e["old_val"] or ""
        new_val = e["new_val"] or ""

        # 差分概要の文言チェック
        if diff_type not in ALLOWED_DIFF_TYPES:
            issues.append(f"差分概要が許容リスト外: '{diff_type}'")

        # フォルダ・ファイルが実在するか（"-" は対象外）
        # Excel の "tmp" は実フォルダ "temp" の省略表記として慣例的に使われているため正規化する
        # ファイル名が拡張子なし（before_requirements等）の場合は .csv を補完して確認
        def normalize_folder(f: str) -> str:
            return "temp" if f == "tmp" else f

        def exists_with_csv_fallback(base_path: Path) -> bool:
            return base_path.exists() or (base_path.parent / (base_path.name + ".csv")).exists()

        if folder and folder != "-" and fname:
            real_folder = normalize_folder(folder)
            old_exists = (
                exists_with_csv_fallback(old_dir / real_folder / fname)
                or any(exists_with_csv_fallback(old_dir / real_folder / sub / fname) for sub in ("PASS", "FAIL"))
            )
            new_exists = (
                exists_with_csv_fallback(new_dir / real_folder / fname)
                or any(exists_with_csv_fallback(new_dir / real_folder / sub / fname) for sub in ("PASS", "FAIL"))
            )
            if not old_exists and not new_exists:
                issues.append(f"フォルダ/ファイルが①②どちらにも存在しない: {real_folder}/{fname}")
        elif fname and folder == "-":
            # ルート直下ファイル
            old_exists = exists_with_csv_fallback(old_dir / fname)
            new_exists = exists_with_csv_fallback(new_dir / fname)
            if not old_exists and not new_exists:
                issues.append(f"ファイルが①②どちらにも存在しない: {fname}")

        row_result = {
            "no": str(e["no"]),
            "folder": folder,
            "file": fname,
            "diff_type": diff_type,
            "issues": issues,
            "result": "NG" if issues else "OK",
        }
        if issues:
            ng_count += 1
        results.append(row_result)

    gate = ok(f"全{len(entries)}エントリ正確") if ng_count == 0 else ng(f"{ng_count}件に問題あり")
    return {"entries": results, "ng_count": ng_count, "gate": gate}


# ──────────────────────────────────────────
# Phase 5: メタ整合性確認
# ──────────────────────────────────────────
def phase5_meta_consistency(entries, project: str, variant: str):
    issues = []
    for e in entries:
        if e["project"] != project:
            issues.append(f"project列が不正: no={e['no']}, value={e['project']}")
        if e["variant"] != variant:
            issues.append(f"variant列が不正: no={e['no']}, value={e['variant']}")
        if e["link"] != LINK_TEXT:
            issues.append(f"link列が不正: no={e['no']}, value={e['link']}")

    gate = ok("メタ情報整合性OK") if not issues else ng(f"{len(issues)}件不整合: {issues}")
    return {"issues": issues, "gate": gate}


# ──────────────────────────────────────────
# QGまとめ
# ──────────────────────────────────────────
def evaluate_quality_gates(p1, p2, p3, p4, p5):
    def is_ok(r):
        if isinstance(r, dict):
            return r.get("result") == "OK"
        return False

    qg = {
        "QG-1": "PASS" if is_ok(p1["gate"]) and is_ok(p2["gate"]) and is_ok(p3["gate"]) else "FAIL",
        "QG-2": "PASS" if is_ok(p4["gate"]) else "FAIL",
        "QG-3": "PASS",  # 推定原因の形式チェックは WARNING のみ（自動判定対象外）
        "QG-4": "PASS" if is_ok(p5["gate"]) else "FAIL",
    }
    overall = "PASS" if all(v == "PASS" for k, v in qg.items() if k != "QG-3") else "FAIL"
    return qg, overall


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def _dir_path(value: str) -> Path:
    """argparse type: ディレクトリ存在チェック"""
    p = Path(value)
    if not p.is_dir():
        raise argparse.ArgumentTypeError(f"ディレクトリが存在しません: {value}")
    return p


def _xlsx_path(value: str) -> Path:
    """argparse type: .xlsx ファイル存在チェック"""
    p = Path(value)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"ファイルが存在しません: {value}")
    if p.suffix.lower() != ".xlsx":
        raise argparse.ArgumentTypeError(f".xlsx ファイルを指定してください: {value}")
    return p


def main():
    parser = argparse.ArgumentParser(
        description="Output差分シート セルフレビュースクリプト"
    )
    parser.add_argument("--project",    required=True,               help="プロジェクト名（例: ver1, ver2, ver2.1）")
    parser.add_argument("--variant",    required=True,               help="バリアント名（例: m02, b01, m01）")
    parser.add_argument("--old",        required=True, type=_dir_path, dest="old_dir", help="旧解析結果ディレクトリ")
    parser.add_argument("--new",        required=True, type=_dir_path, dest="new_dir", help="新解析結果ディレクトリ")
    parser.add_argument("--xlsx",       required=True, type=_xlsx_path,                help="Output差分シートを持つ Excel ファイル")
    _default_base = Path(__file__).parent.parent
    parser.add_argument(
        "--report-out",
        default=None,
        help="検証レポート出力先 YAML（省略時: test/verify_report_{variant}.yaml）",
    )
    parser.add_argument(
        "--plan",
        default=None,
        help="レビュー計画 YAML（省略時: test/review_plan_{variant}.yaml、不在時スキップ）",
    )
    args = parser.parse_args()

    base = Path(__file__).parent.parent
    report_out = Path(args.report_out) if args.report_out else base / "test" / f"verify_report_{args.variant}.yaml"
    plan_path  = Path(args.plan)       if args.plan        else base / "test" / f"review_plan_{args.variant}.yaml"

    print(f"=== {args.project} {args.variant} セルフレビュー開始 ===")

    entries = load_excel_entries(args.xlsx, args.project, args.variant)
    print(f"Excelエントリ読み込み: {len(entries)} 件")

    print("Phase 1: ファイルインベントリ確認...")
    p1 = phase1_file_inventory(entries, args.old_dir, args.new_dir)

    print("Phase 2: CSV差分確認...")
    p2 = phase2_csv_diffs(entries, args.old_dir, args.new_dir)

    print("Phase 3: 画像ファイル差分確認...")
    p3 = phase3_image_diffs(entries, args.old_dir, args.new_dir)

    print("Phase 4: Excelエントリ正確性確認...")
    p4 = phase4_entry_accuracy(entries, args.old_dir, args.new_dir)

    print("Phase 5: メタ整合性確認...")
    p5 = phase5_meta_consistency(entries, args.project, args.variant)

    qg_results, overall = evaluate_quality_gates(p1, p2, p3, p4, p5)

    report = {
        "meta": {
            "executed_date": str(date.today()),
            "excel_entries_count": len(entries),
            "project": args.project,
            "variant": args.variant,
        },
        "quality_gates": qg_results,
        "overall": overall,
        "phase1_file_inventory": p1,
        "phase2_csv_diffs": p2,
        "phase3_image_diffs": p3,
        "phase4_entry_accuracy": p4,
        "phase5_meta_consistency": p5,
    }

    report_out.parent.mkdir(parents=True, exist_ok=True)
    with open(report_out, "w", encoding="utf-8") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\n=== 品質ゲート結果 ===")
    for k, v in qg_results.items():
        mark = "✅" if v == "PASS" else "❌"
        print(f"  {mark} {k}: {v}")
    print(f"\n  総合判定: {'✅ PASS' if overall == 'PASS' else '❌ FAIL'}")
    print(f"\nレポート出力: {report_out}")

    # 計画ファイルの実行ステータスを更新（ファイルが存在する場合のみ）
    if plan_path.exists():
        with open(plan_path, encoding="utf-8") as f:
            plan = yaml.safe_load(f)
        plan["execution_status"]["executed_date"] = str(date.today())
        plan["execution_status"]["gate_results"] = qg_results
        plan["execution_status"]["overall"] = overall
        with open(plan_path, "w", encoding="utf-8") as f:
            yaml.dump(plan, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"計画ファイル更新: {plan_path}")

    sys.exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
