#!/usr/bin/env python3
"""
OUTPUT フォルダ比較スクリプト
usage:
  python3 scripts/output_diff.py --old <旧フォルダ> --new <新フォルダ> [--html | --csv] [--out <出力パス>]

2つのフォルダを再帰的に比較し、WinMerge のフォルダ比較結果に相当する一覧を
HTML または CSV で出力する。
"""
import argparse
import csv
import datetime
import difflib
import html
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────

BINARY_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg",
    ".xlsx", ".zip", ".bin",
}

IMAGE_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
}

ROW_COLORS: dict[str, str] = {
    "Different":  "#fff3cd",
    "Left only":  "#f8d7da",
    "Right only": "#d4edda",
    "Identical":  "#ffffff",
}

CSV_COLUMNS: list[str] = [
    "ファイル名", "フォルダ", "比較結果", "旧更新日時", "新更新日時", "拡張子",
]

DIFF_CONTEXT_LINES: int = 3
DIFF_MAX_LINES: int = 1000  # これを超えた場合は先頭 N 行のみ表示し Warning を付与する

SORT_ORDER: dict[str, int] = {
    "Different":  0,
    "Left only":  1,
    "Right only": 2,
    "Identical":  3,
}


# ──────────────────────────────────────────
# データ構造
# ──────────────────────────────────────────

@dataclass
class DiffEntry:
    name: str          # ファイル名
    folder: str        # 比較ルートからの相対フォルダパス（ルート直下は空文字）
    result: str        # "Identical" | "Different" | "Left only" | "Right only"
    old_mtime: str     # 旧更新日時（Right only の場合は空文字）
    new_mtime: str     # 新更新日時（Left only の場合は空文字）
    ext: str           # 拡張子（フォルダの場合は空文字）
    diff_lines: list[str] = field(default_factory=list)  # unified diff 行


# ──────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────

def decode_text(data: bytes) -> str:
    """バイト列を UTF-8 → Shift-JIS → latin-1 の順でデコードする。"""
    for enc in ("utf-8", "shift-jis", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("latin-1", errors="replace")


def is_binary(path: Path) -> bool:
    """拡張子が BINARY_EXTENSIONS に含まれる場合はバイナリと判定する。
    含まれない場合はファイルの先頭をデコード試行し、失敗した場合もバイナリと判定する。"""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        head = path.read_bytes()[:4096]
        decode_text(head)
        # latin-1 は常に成功するが、NUL バイトがあればバイナリとみなす
        if b"\x00" in head:
            return True
        return False
    except OSError:
        return True


def get_mtime(path: Path) -> str:
    """ファイルの更新日時を 'YYYY-MM-DD HH:MM:SS' 形式で返す。"""
    try:
        ts = path.stat().st_mtime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return ""


def _extract_png_idat(data: bytes) -> bytes:
    """PNG バイト列から IDAT チャンク（画像本体）を連結して返す。
    PNG シグネチャが不正な場合やパース失敗時は空バイト列を返す。"""
    if len(data) < 8 or data[:8] != b'\x89PNG\r\n\x1a\n':
        return b""
    import struct
    pos = 8
    idat: list[bytes] = []
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        if chunk_type == b"IDAT":
            idat.append(data[pos + 8:pos + 8 + length])
        elif chunk_type == b"IEND":
            break
        pos += 4 + 4 + length + 4  # length + type + data + CRC
    return b"".join(idat)


# ──────────────────────────────────────────
# 比較ロジック（IT-2 で実装予定）
# ──────────────────────────────────────────

def _collect_relpaths(root: Path) -> set[str]:
    """root 以下のファイルの相対パス（文字列）を再帰的に収集する。
    ディレクトリ自体は含めない。"""
    result: set[str] = set()
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            abs_path = Path(dirpath) / f
            result.add(str(abs_path.relative_to(root)))
    return result


def _compare_file(rel: str, old_root: Path, new_root: Path) -> DiffEntry:
    """共通ファイル 1 件を比較して DiffEntry を返す。（IT-2 で完全実装）"""
    p = Path(rel)
    name = p.name
    folder = str(p.parent) if str(p.parent) != "." else ""
    ext = p.suffix

    old_path = old_root / rel
    new_path = new_root / rel
    old_mtime = get_mtime(old_path)
    new_mtime = get_mtime(new_path)

    # バイナリ判定
    if is_binary(old_path) or is_binary(new_path):
        old_bytes = old_path.read_bytes()
        new_bytes = new_path.read_bytes()
        if old_bytes == new_bytes:
            result = "Identical"
        elif ext.lower() == ".png":
            # PNG は IDAT チャンク（画像本体）のみ比較する
            # メタデータ（tEXt に含まれる Matplotlib バージョン等）の差異は無視する
            old_idat = _extract_png_idat(old_bytes)
            new_idat = _extract_png_idat(new_bytes)
            result = "Identical" if (old_idat and old_idat == new_idat) else "Different"
        else:
            result = "Different"
        return DiffEntry(name=name, folder=folder, result=result,
                         old_mtime=old_mtime, new_mtime=new_mtime, ext=ext)

    # テキスト比較
    old_text = decode_text(old_path.read_bytes())
    new_text = decode_text(new_path.read_bytes())
    if old_text == new_text:
        return DiffEntry(name=name, folder=folder, result="Identical",
                         old_mtime=old_mtime, new_mtime=new_mtime, ext=ext)

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    old_total = len(old_lines)
    new_total = len(new_lines)

    # 巨大ファイルは先頭 DIFF_MAX_LINES 行のみ diff にかけて高速化
    truncated = old_total > DIFF_MAX_LINES or new_total > DIFF_MAX_LINES
    if truncated:
        old_lines = old_lines[:DIFF_MAX_LINES]
        new_lines = new_lines[:DIFF_MAX_LINES]

    diff_lines = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"旧/{rel}",
        tofile=f"新/{rel}",
        n=DIFF_CONTEXT_LINES,
    ))
    if truncated:
        diff_lines += [
            f"\n⚠ WARNING: ファイルが大きすぎるため先頭 {DIFF_MAX_LINES:,} 行のみ比較しました。"
            f"（旧: {old_total:,} 行 / 新: {new_total:,} 行）\n",
        ]
    return DiffEntry(name=name, folder=folder, result="Different",
                     old_mtime=old_mtime, new_mtime=new_mtime, ext=ext,
                     diff_lines=diff_lines)


def compare_folders(old_root: Path, new_root: Path) -> list[DiffEntry]:
    """2つのフォルダを再帰的に比較し、DiffEntry のリストを返す。
    ソート順: Different → Left only → Right only → Identical"""
    old_paths = _collect_relpaths(old_root)
    new_paths = _collect_relpaths(new_root)

    entries: list[DiffEntry] = []

    for rel in sorted(old_paths - new_paths):
        p = Path(rel)
        entries.append(DiffEntry(
            name=p.name,
            folder=str(p.parent) if str(p.parent) != "." else "",
            result="Left only",
            old_mtime=get_mtime(old_root / rel),
            new_mtime="",
            ext=p.suffix,
        ))

    for rel in sorted(new_paths - old_paths):
        p = Path(rel)
        entries.append(DiffEntry(
            name=p.name,
            folder=str(p.parent) if str(p.parent) != "." else "",
            result="Right only",
            old_mtime="",
            new_mtime=get_mtime(new_root / rel),
            ext=p.suffix,
        ))

    for rel in sorted(old_paths & new_paths):
        entries.append(_compare_file(rel, old_root, new_root))

    entries.sort(key=lambda e: SORT_ORDER.get(e.result, 99))
    return entries


# ──────────────────────────────────────────
# CSV 出力（IT-3 で実装予定）
# ──────────────────────────────────────────

def write_csv(entries: list[DiffEntry], out_path: Path) -> int:
    """エントリを CSV（utf-8-sig）に出力する。戻り値は書き込み件数。"""
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for e in entries:
            writer.writerow([
                e.name, e.folder, e.result, e.old_mtime, e.new_mtime, e.ext,
            ])
    return len(entries)


# ──────────────────────────────────────────
# HTML 出力（IT-4/IT-5 で実装予定）
# ──────────────────────────────────────────

def load_annotations(path: Path) -> dict[str, dict]:
    """アノテーション JSON を読み込んで {key: entry_dict} を返す。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("entries", {})
    except (OSError, json.JSONDecodeError):
        return {}


def write_annotations_skeleton(entries: list[DiffEntry], out_path: Path) -> None:
    """Different ファイルのアノテーション JSON スケルトンを書き出す。
    既存ファイルがある場合は新規エントリのみ追加し、既存エントリ（reason 等）は保持する。"""
    data: dict = {}
    if out_path.exists():
        try:
            data = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    if "_comment" not in data:
        data["_comment"] = (
            "output_diff アノテーション。"
            "reason フィールドを手動編集可能。"
            "details は extract_and_write_diff.py --annotations-out で自動補完。"
        )
    if "entries" not in data:
        data["entries"] = {}

    changed = False
    for e in entries:
        if e.result != "Different":
            continue
        key = e.name if not e.folder else f"{e.folder}/{e.name}"
        if key not in data["entries"]:
            data["entries"][key] = {
                "folder": e.folder,
                "file": e.name,
                "reason": "",
                "details": [],
            }
            changed = True

    if changed or not out_path.exists():
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"  アノテーション JSON: {out_path}")


def _write_diff_js(entry: DiffEntry, key: str, diffs_dir: Path,
                   annot_details: list[dict] | None = None) -> str:
    """unified diff 内容を外部 JS ファイルに書き出し、プレースホルダ <details> HTML を返す。
    呼び出し側が diffs_dir を事前に作成しておくこと。
    unified diff と左右並列（split）の両ビューをトグルボタンで切り替え可能。
    hunk_pattern にマッチした hunk 直前にバッジを表示。"""

    # パターン→詳細のマッピング構築
    pattern_details: list[tuple] = []
    if annot_details:
        for d in annot_details:
            p = (d.get("hunk_pattern") or "").strip()
            if p:
                try:
                    pattern_details.append((re.compile(p), d))
                except re.error:
                    pattern_details.append((re.compile(re.escape(p)), d))

    # hunk インデックス → マッチした details のマッピング
    hunk_idx = -1
    hunk_matches: dict[int, list[dict]] = {}
    for line in entry.diff_lines:
        if line.startswith("@@"):
            hunk_idx += 1
            hunk_matches[hunk_idx] = []
        elif hunk_idx >= 0 \
                and (line.startswith("+") or line.startswith("-")) \
                and not line.startswith(("---", "+++")):
            for pat, d in pattern_details:
                if pat.search(line[1:]) and d not in hunk_matches[hunk_idx]:
                    hunk_matches[hunk_idx].append(d)

    def _badge_bar(matched: list[dict]) -> str:
        if not matched:
            return ""
        parts = []
        for d in matched:
            dt = html.escape(d.get("diff_type", ""))
            cause = html.escape(d.get("cause", "") or "")
            tip = f' title="{cause}"' if cause else ""
            parts.append(
                f'<span{tip} style="background:#cfe2ff;border:1px solid #9ec5fe;'
                f'padding:1px 6px;border-radius:3px;font-size:0.82em;'
                f'white-space:nowrap;cursor:default">&#128203; {dt}</span>'
            )
        return (
            '<div style="background:#e8f0fe;padding:3px 8px;'
            'border-left:3px solid #4a90d9;font-family:sans-serif;'
            'font-size:0.82em;display:flex;flex-wrap:wrap;gap:4px;align-items:center">'
            + "".join(parts) + "</div>"
        )

    def _render_line(line: str) -> str:
        escaped = html.escape(line)
        if line.startswith("⚠"):
            return (f'<span style="background:#fff3cd;color:#856404;font-weight:bold">'
                    f'{escaped}</span>')
        elif line.startswith("+") and not line.startswith("+++"):
            return f'<span style="background:#dfd">{escaped}</span>'
        elif line.startswith("-") and not line.startswith("---"):
            return f'<span style="background:#fdd">{escaped}</span>'
        return escaped

    # ── unified ビュー ──
    def _build_unified() -> str:
        blocks: list[str] = []
        cur_hunk_idx = -1
        cur_hunk_lines: list[str] = []
        pre_lines: list[str] = []
        in_hunk = False
        for line in entry.diff_lines:
            if re.match(r"^@@", line):
                if in_hunk and cur_hunk_lines:
                    blocks.append(
                        '<pre style="font-size:0.85em;overflow-x:auto;margin:0;width:100%;box-sizing:border-box">'
                        + "".join(_render_line(l) for l in cur_hunk_lines)
                        + "</pre>"
                    )
                    cur_hunk_lines = []
                else:
                    if pre_lines:
                        blocks.append(
                            '<pre style="font-size:0.85em;overflow-x:auto;margin:0;width:100%;box-sizing:border-box">'
                            + "".join(_render_line(l) for l in pre_lines)
                            + "</pre>"
                        )
                        pre_lines = []
                cur_hunk_idx += 1
                in_hunk = True
                badge = _badge_bar(hunk_matches.get(cur_hunk_idx, []))
                if badge:
                    blocks.append(badge)
                cur_hunk_lines.append(line)
            else:
                if in_hunk:
                    cur_hunk_lines.append(line)
                else:
                    pre_lines.append(line)
        if in_hunk and cur_hunk_lines:
            blocks.append(
                '<pre style="font-size:0.85em;overflow-x:auto;margin:0;width:100%;box-sizing:border-box">'
                + "".join(_render_line(l) for l in cur_hunk_lines)
                + "</pre>"
            )
        elif pre_lines:
            blocks.append(
                '<pre style="font-size:0.85em;overflow-x:auto;margin:0;width:100%;box-sizing:border-box">'
                + "".join(_render_line(l) for l in pre_lines)
                + "</pre>"
            )
        return (
            '<div style="border:1px solid #e0e0e0;border-radius:3px;overflow-x:auto">'
            + "".join(b for b in blocks if b)
            + "</div>"
        )

    # ── split ビュー（2ペイン独立横スクロール・バッジは全幅div・縦ずれなし） ──
    def _build_split() -> str:
        LNUM = (
            "font-family:monospace;text-align:right;padding:1px 4px;"
            "color:#aaa;user-select:none;border-right:1px solid #e0e0e0;"
            "width:3em;font-size:0.85em;white-space:nowrap;vertical-align:top"
        )
        CODE = "font-family:monospace;white-space:pre;padding:1px 6px;vertical-align:top"
        SEP = "border-left:2px solid #aaa"
        FHDR = "font-family:monospace;font-size:0.85em;padding:2px 6px;background:#f0f0f0;color:#555"
        HHDR = "font-family:monospace;font-size:0.85em;padding:2px 6px;background:#e8e8e8;font-weight:bold;color:#555"
        WARN = "font-family:monospace;font-size:0.85em;padding:2px 6px;background:#fff3cd;color:#856404;font-weight:bold"

        def _char_diff(old: str, new: str) -> tuple[str, str]:
            """文字レベルの差分を取り、差分箇所を濃い背景色でハイライトした HTML を返す"""
            sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
            oh: list[str] = []
            nh: list[str] = []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    oh.append(html.escape(old[i1:i2]))
                    nh.append(html.escape(new[j1:j2]))
                elif tag == "replace":
                    oh.append(f'<span style="background:#f77">{html.escape(old[i1:i2])}</span>')
                    nh.append(f'<span style="background:#4d4">{html.escape(new[j1:j2])}</span>')
                elif tag == "delete":
                    oh.append(f'<span style="background:#f77">{html.escape(old[i1:i2])}</span>')
                elif tag == "insert":
                    nh.append(f'<span style="background:#4d4">{html.escape(new[j1:j2])}</span>')
            return "".join(oh), "".join(nh)

        # セグメントリスト: 各要素は dict
        segments: list[dict] = []
        cur_left: list[str] = []
        cur_right: list[str] = []
        old_lno = 0
        new_lno = 0
        cur_hunk_idx = -1
        idx = 0
        lines = entry.diff_lines
        seg_idx = 0  # コードセグメントのID連番

        def flush_code() -> None:
            nonlocal seg_idx
            if not cur_left and not cur_right:
                return
            n = max(len(cur_left), len(cur_right))
            while len(cur_left) < n:
                cur_left.append(
                    f'<tr><td style="{LNUM}">&nbsp;</td>'
                    f'<td style="{CODE};background:#f5f5f5">&nbsp;</td></tr>'
                )
            while len(cur_right) < n:
                cur_right.append(
                    f'<tr><td style="{LNUM}">&nbsp;</td>'
                    f'<td style="{CODE};background:#f5f5f5">&nbsp;</td></tr>'
                )
            segments.append({
                "type": "code", "id": seg_idx,
                "left": list(cur_left), "right": list(cur_right),
            })
            cur_left.clear()
            cur_right.clear()
            seg_idx += 1

        while idx < len(lines):
            line = lines[idx].rstrip("\n")

            if line.startswith("---") or line.startswith("+++"):
                flush_code()
                segments.append({"type": "fhdr", "line": line})
                idx += 1
                continue

            m = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if m:
                flush_code()
                old_lno = int(m.group(1))
                new_lno = int(m.group(2))
                cur_hunk_idx += 1
                matched = hunk_matches.get(cur_hunk_idx, [])
                if matched:
                    segments.append({"type": "badge", "html": _badge_bar(matched)})
                segments.append({"type": "hhdr", "line": line})
                idx += 1
                continue

            if line.startswith("\u26a0"):
                flush_code()
                segments.append({"type": "warn", "line": line})
                idx += 1
                continue

            del_lines: list[str] = []
            add_lines: list[str] = []
            while idx < len(lines):
                ln = lines[idx].rstrip("\n")
                if ln.startswith("-") and not ln.startswith("---"):
                    del_lines.append(ln[1:])
                    idx += 1
                elif ln.startswith("+") and not ln.startswith("+++"):
                    add_lines.append(ln[1:])
                    idx += 1
                else:
                    break

            if del_lines or add_lines:
                n = max(len(del_lines), len(add_lines))
                for j in range(n):
                    has_del = j < len(del_lines)
                    has_add = j < len(add_lines)
                    lt = del_lines[j] if has_del else ""
                    rt = add_lines[j] if has_add else ""
                    ll = str(old_lno + j) if has_del else ""
                    rl = str(new_lno + j) if has_add else ""
                    lb = "#fdd" if has_del else "#f5f5f5"
                    rb = "#dfd" if has_add else "#f5f5f5"
                    # 対応行がある場合のみ文字レベル diff でbold
                    if has_del and has_add:
                        lt_html, rt_html = _char_diff(lt, rt)
                    else:
                        lt_html = html.escape(lt) or "&nbsp;"
                        rt_html = html.escape(rt) or "&nbsp;"
                    cur_left.append(
                        f'<tr><td style="{LNUM}">{html.escape(ll) or "&nbsp;"}</td>'
                        f'<td style="{CODE};background:{lb}">{lt_html or "&nbsp;"}</td></tr>'
                    )
                    cur_right.append(
                        f'<tr><td style="{LNUM}">{html.escape(rl) or "&nbsp;"}</td>'
                        f'<td style="{CODE};background:{rb}">{rt_html or "&nbsp;"}</td></tr>'
                    )
                old_lno += len(del_lines)
                new_lno += len(add_lines)
                continue

            text = line[1:] if line.startswith(" ") else line
            row = (
                f'<tr><td style="{LNUM}">{{}}</td>'
                f'<td style="{CODE};background:#fff">{html.escape(text)}</td></tr>'
            )
            cur_left.append(row.format(html.escape(str(old_lno))))
            cur_right.append(row.format(html.escape(str(new_lno))))
            old_lno += 1
            new_lno += 1
            idx += 1

        flush_code()

        # ── セグメントをHTMLに変換 ──
        parts: list[str] = []
        # 固定ヘッダ行（スクロールしても常に表示）
        parts.append(
            f'<div style="display:flex;position:sticky;top:0;z-index:2;background:#f0f0f0;border-bottom:1px solid #ccc">'
            f'<div style="flex:1;text-align:center;padding:3px;font-weight:bold;font-size:0.85em">旧</div>'
            f'<div style="flex:1;text-align:center;padding:3px;font-weight:bold;font-size:0.85em;{SEP}">新</div>'
            f'</div>'
        )
        for seg in segments:
            t = seg["type"]
            if t == "fhdr":
                pass  # --- 旧/xxx / +++ 新/xxx は split では不要
            elif t == "hhdr":
                parts.append(f'<div style="{HHDR}">{html.escape(seg["line"])}</div>')
            elif t == "warn":
                parts.append(f'<div style="{WARN}">{html.escape(seg["line"])}</div>')
            elif t == "badge":
                parts.append(seg["html"])
            elif t == "code":
                sid = seg["id"]
                lid = f"lp-{key}-{sid}"
                rid = f"rp-{key}-{sid}"
                tbl_style = 'style="border-collapse:collapse"'
                col = '<colgroup><col style="width:3em"><col></colgroup>'
                ltbl = f'<table {tbl_style}>{col}<tbody>{"".join(seg["left"])}</tbody></table>'
                rtbl = f'<table {tbl_style}>{col}<tbody>{"".join(seg["right"])}</tbody></table>'
                parts.append(
                    f'<div style="display:flex">'
                    f'<div id="{lid}" style="flex:1;min-width:0;overflow-x:auto"'
                    f' onscroll="syncScrollX(this,\'{rid}\')">{ltbl}</div>'
                    f'<div id="{rid}" style="flex:1;min-width:0;overflow-x:auto;{SEP}"'
                    f' onscroll="syncScrollX(this,\'{lid}\')">{rtbl}</div>'
                    f'</div>'
                )

        return (
            '<div style="border:1px solid #e0e0e0;border-radius:3px;font-size:0.85em;'
            'max-height:480px;overflow-y:auto">'
            + "".join(parts)
            + "</div>"
        )
    unified_html = _build_unified()
    split_html = _build_split()

    pre_html = (
        "<div>"
        '<div style="text-align:right;margin-bottom:2px">'
        '<button onclick="toggleSplit(this)" data-mode="unified" '
        'style="font-size:0.78em;padding:2px 8px;cursor:pointer;'
        'border:1px solid #aaa;background:#f8f8f8;border-radius:3px">'
        "⇔ 左右表示</button>"
        "</div>"
        f'<div data-view="unified">{unified_html}</div>'
        f'<div data-view="split" style="display:none">{split_html}</div>'
        "</div>"
    )
    js_content = (
        f"(window.DIFF_CACHE=window.DIFF_CACHE||{{}})"
        f"[{json.dumps(key)}]={json.dumps(pre_html)};\n"
    )
    (diffs_dir / f"{key}.js").write_text(js_content, encoding="utf-8")

    js_src_rel = f"{diffs_dir.name}/{key}.js"
    return (
        f'<details ontoggle="loadDiff(this)" '
        f'data-diff-key="{html.escape(key)}" '
        f'data-diff-src="{html.escape(js_src_rel)}">'
        f"<summary>差分を表示</summary>"
        f'<div class="diff-ph" style="color:#888;font-size:0.85em">'
        f"（展開すると差分を読み込みます）</div>"
        f"</details>"
    )


def _image_compare_cell(entry: DiffEntry, old_root: Path, new_root: Path,
                        html_out: Path) -> str:
    """画像ファイルの左右比較セル（<details>）を生成する。
    ファイルが存在しない場合は Empty プレースホルダーを表示する。"""
    html_dir = html_out.resolve().parent
    old_path = old_root / entry.folder / entry.name
    new_path = new_root / entry.folder / entry.name

    empty_div = (
        '<div style="background:#f0f0f0;padding:40px 10px;text-align:center;'
        'color:#aaa;border:1px solid #ccc;font-size:1.1em">Empty</div>'
    )

    def img_tag(path: Path) -> str:
        if path.exists():
            rel = os.path.relpath(path.resolve(), html_dir)
            # Windows パス区切りをスラッシュに統一
            rel_url = rel.replace(os.sep, "/")
            return (
                f'<img src="{html.escape(rel_url)}" '
                f'style="max-width:100%;border:1px solid #ccc">'
            )
        return empty_div

    return (
        '<details>'
        '<summary style="cursor:pointer">画像を表示</summary>'
        '<table style="width:100%;table-layout:fixed;margin-top:4px"><tr>'
        '<th style="width:50%">旧</th><th style="width:50%">新</th></tr><tr>'
        f'<td style="vertical-align:top;padding:4px">{img_tag(old_path)}</td>'
        f'<td style="vertical-align:top;padding:4px">{img_tag(new_path)}</td>'
        '</tr></table>'
        '</details>'
    )


def write_html(entries: list[DiffEntry], old_root: Path, new_root: Path,
               out_path: Path,
               annotations: dict[str, dict] | None = None) -> int:
    """エントリをフォルダ単位の折り畳み（<details>）付き HTML に出力する。
    diff 内容は {html名}_diffs/ に外部 JS ファイルとして分離する。
    annotations が指定された場合、Different ファイルにアノテーションバッジを表示する。
    戻り値は書き込み件数。"""
    from collections import Counter
    diffs_dir = out_path.parent / (out_path.stem + "_diffs")
    diffs_dir.mkdir(exist_ok=True)
    diff_idx = 0
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    counts = Counter(e.result for e in entries)

    # ── サマリテーブル ──
    summary_rows = ""
    for result in ["Different", "Left only", "Right only", "Identical"]:
        n = counts.get(result, 0)
        color = ROW_COLORS[result]
        summary_rows += (
            f'<tr style="background:{color}">'
            f'<td>{html.escape(result)}</td><td>{n}</td></tr>\n'
        )

    # ── フォルダ単位でグループ化（entries のソート順を維持）──
    groups: dict[str, list[DiffEntry]] = {}
    for e in entries:
        key = e.folder if e.folder else ""
        if key not in groups:
            groups[key] = []
        groups[key].append(e)

    # フォルダ自体も「グループ内の最良結果」でソート
    def _folder_sort_key(item: tuple) -> int:
        return min(SORT_ORDER.get(e.result, 99) for e in item[1])

    sorted_groups = sorted(groups.items(), key=_folder_sort_key)

    # ── フォルダ折り畳みセクションを生成 ──
    folder_sections = ""
    for folder_name, folder_entries in sorted_groups:
        folder_counts = Counter(e.result for e in folder_entries)
        display_name = folder_name if folder_name else "(ルート直下)"

        label_parts = [
            f"{r}: {folder_counts[r]}"
            for r in ["Different", "Left only", "Right only", "Identical"]
            if folder_counts.get(r, 0) > 0
        ]

        file_rows = ""
        for e in folder_entries:
            color = ROW_COLORS.get(e.result, "#ffffff")
            # アノテーションエントリを先に取得（diff_td と annot_html の両方で利用）
            annot_key = e.name if not e.folder else f"{e.folder}/{e.name}"
            annot = (annotations or {}).get(annot_key, {})

            if e.ext.lower() in IMAGE_EXTENSIONS:
                diff_td = _image_compare_cell(e, old_root, new_root, out_path)
            elif e.diff_lines:
                key = f"d{diff_idx}"
                diff_idx += 1
                diff_td = _write_diff_js(e, key, diffs_dir, annot.get("details", []))
            else:
                diff_td = ""
            # アノテーションバッジ生成
            annot_html = ""
            if annotations and annot:
                if annot:
                    parts: list[str] = []
                    for d in annot.get("details", []):
                        dt = html.escape(d.get("diff_type", ""))
                        cause = html.escape(d.get("cause", "") or "")
                        if dt:
                            tip = f' title="{cause}"' if cause else ""
                            parts.append(
                                f'<span{tip} style="background:#cfe2ff;border:1px solid #9ec5fe;'
                                f'padding:1px 6px;border-radius:3px;white-space:nowrap;cursor:default">'
                                f'&#128203; {dt}</span>'
                            )
                    reason = html.escape(annot.get("reason", "").strip())
                    if reason:
                        parts.append(
                            f'<span style="background:#fff3cd;border:1px solid #ffc107;'
                            f'padding:1px 6px;border-radius:3px;white-space:nowrap">'
                            f'&#128221; {reason}</span>'
                        )
                    if parts:
                        annot_html = (
                            f'<div style="margin-bottom:4px;font-size:0.85em;'
                            f'display:flex;flex-wrap:wrap;gap:4px">'
                            + "".join(parts)
                            + '</div>'
                        )
            file_rows += (
                f'<tr style="background:{color}">'
                f'<td>{html.escape(e.name)}</td>'
                f'<td>{html.escape(e.result)}</td>'
                f'<td>{html.escape(e.old_mtime)}</td>'
                f'<td>{html.escape(e.new_mtime)}</td>'
                f'<td>{html.escape(e.ext)}</td>'
                f'</tr>\n'
            )
            if diff_td or annot_html:
                file_rows += (
                    f'<tr style="background:{color}">'
                    f'<td colspan="5" style="padding:4px 8px">'
                    f'{annot_html}{diff_td}'
                    f'</td>'
                    f'</tr>\n'
                )

        folder_sections += (
            f'<details>'
            f'<summary style="cursor:pointer;padding:6px 10px;'
            f'background:#e8e8e8;border:1px solid #bbb;margin-top:4px">'
            f'<strong>{html.escape(display_name)}</strong>'
            f'&nbsp;<span style="color:#555;font-size:0.9em">'
            f'[{html.escape(", ".join(label_parts))}]'
            f'&nbsp;{len(folder_entries)} 件</span>'
            f'</summary>\n'
            f'<table style="table-layout:fixed;width:100%">\n'
            f'<colgroup>'
            f'<col style="width:22%"><col style="width:10%">'
            f'<col style="width:15%"><col style="width:15%">'
            f'<col style="width:8%">'
            f'</colgroup>\n'
            f'<thead><tr>'
            f'<th>ファイル名</th><th>比較結果</th>'
            f'<th>旧更新日時</th><th>新更新日時</th><th>拡張子</th>'
            f'</tr></thead>\n'
            f'<tbody>\n{file_rows}</tbody>\n'
            f'</table>\n'
            f'</details>\n'
        )

    html_content = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>output diff: {html.escape(str(old_root))} → {html.escape(str(new_root))}</title>
<style>
  body {{ font-family: sans-serif; font-size: 0.9em; overflow-x: hidden; max-width: 100vw; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 8px; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; vertical-align: top; }}
  th {{ background: #f0f0f0; }}
  details > summary {{ list-style: none; }}
  details > summary::-webkit-details-marker {{ display: none; }}
  details > summary::before {{ content: "▶ "; font-size: 0.8em; }}
  details[open] > summary::before {{ content: "▼ "; font-size: 0.8em; }}
</style>
<script>
function loadDiff(el) {{
  if (!el.open || el.dataset.loaded) return;
  el.dataset.loaded = '1';
  var s = document.createElement('script');
  s.src = el.dataset.diffSrc;
  s.onload = function() {{
    var ph = el.querySelector('.diff-ph');
    var c = (window.DIFF_CACHE || {{}})[el.dataset.diffKey];
    if (ph && c) {{ ph.innerHTML = c; }}
  }};
  document.head.appendChild(s);
}}
function toggleSplit(btn) {{
  var wrap = btn.parentElement.parentElement;
  var uview = wrap.querySelector('[data-view="unified"]');
  var sview = wrap.querySelector('[data-view="split"]');
  if (btn.dataset.mode === 'unified') {{
    uview.style.display = 'none';
    sview.style.display = '';
    btn.dataset.mode = 'split';
    btn.textContent = '\u2261 \u5dee\u5206\u8868\u793a';
  }} else {{
    uview.style.display = '';
    sview.style.display = 'none';
    btn.dataset.mode = 'unified';
    btn.textContent = '\u21d4 \u5de6\u53f3\u8868\u793a';
  }}
}}
function syncScrollX(src, otherId) {{
  var tgt = document.getElementById(otherId);
  if (!tgt || tgt._sx) return;
  src._sx = true;
  tgt.scrollLeft = src.scrollLeft;
  src._sx = false;
}}
// <details> を開閉しても summary の画面位置を固定する
document.addEventListener('click', function(e) {{
  var summary = e.target.closest('summary');
  if (!summary) return;
  var details = summary.parentElement;
  if (!details || details.tagName !== 'DETAILS') return;
  var top = summary.getBoundingClientRect().top;
  requestAnimationFrame(function() {{
    var diff = summary.getBoundingClientRect().top - top;
    window.scrollBy(0, diff);
  }});
}});
</script>
</head>
<body>
<h1>output diff</h1>
<p>生成日時: {now}</p>
<p>旧: {html.escape(str(old_root))}<br>新: {html.escape(str(new_root))}</p>
<p style="font-size:0.85em;color:#666">
  ※ extract_and_write_diff.py では temp/ フォルダは Excel 上 "tmp" と表示されます。<br>
  ※ processing_time_SWC_group_result.csv / node_straddling_slot_pickup_result.csv /
  temp/after_budget.csv は「差分なし期待ファイル」のため Excel には記録されません。
</p>

<h2>サマリ</h2>
<table style="width:auto">
<tr><th>比較結果</th><th>件数</th></tr>
{summary_rows}</table>

<h2>ファイル一覧（フォルダ別）</h2>
{folder_sections}
</body>
</html>
"""
    out_path.write_text(html_content, encoding="utf-8")
    return len(entries)


# ──────────────────────────────────────────
# エントリポイント
# ──────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="2つの OUTPUT フォルダを再帰的に比較し HTML または CSV で出力する"
    )
    parser.add_argument("--old", required=True, type=Path, help="旧フォルダパス")
    parser.add_argument("--new", required=True, type=Path, dest="new_dir",
                        help="新フォルダパス")
    parser.add_argument("--html", action="store_true", help="HTML 形式で出力（デフォルト）")
    parser.add_argument("--csv", action="store_true", help="CSV 形式で出力（--html と排他）")
    parser.add_argument("--out", type=Path, help="出力ファイルパス")
    parser.add_argument(
        "--annotations", type=Path, default=None,
        help="アノテーション JSON ファイルパス（--html 時のみ有効）。"
             "省略時は <out_stem>_annotations.json を自動参照する。",
    )
    args = parser.parse_args()

    # --html / --csv 排他チェック
    if args.html and args.csv:
        print("エラー: --html と --csv は同時に指定できません。")
        raise SystemExit(1)

    # フォルダ存在チェック
    if not args.old.exists():
        print(f"エラー: --old で指定したフォルダが存在しません: {args.old}")
        raise SystemExit(1)
    if not args.new_dir.exists():
        print(f"エラー: --new で指定したフォルダが存在しません: {args.new_dir}")
        raise SystemExit(1)

    use_csv = args.csv  # --html 未指定かつ --csv 未指定 → HTML がデフォルト

    if args.out:
        out_path = args.out
    else:
        out_path = Path("output_diff.csv" if use_csv else "output_diff.html")

    entries = compare_folders(args.old, args.new_dir)

    if use_csv:
        written = write_csv(entries, out_path)
    else:
        # アノテーション JSON スケルトンを自動生成（既存エントリは保持）
        annotations_path = out_path.parent / (out_path.stem + "_annotations.json")
        write_annotations_skeleton(entries, annotations_path)
        # --annotations 指定 > 自動パス の順で読み込む
        ann_src = args.annotations if args.annotations else annotations_path
        annotations = load_annotations(ann_src) if ann_src.exists() else {}
        written = write_html(entries, args.old, args.new_dir, out_path, annotations)

    print(f"  比較完了: {written} 件 → {out_path}")


if __name__ == "__main__":
    main()
