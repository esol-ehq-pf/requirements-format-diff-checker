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

def _write_diff_js(entry: DiffEntry, key: str, diffs_dir: Path) -> str:
    """unified diff 内容を外部 JS ファイルに書き出し、プレースホルダ <details> HTML を返す。
    呼び出し側が diffs_dir を事前に作成しておくこと。"""
    lines_html: list[str] = []
    for line in entry.diff_lines:
        escaped = html.escape(line)
        if line.startswith("⚠"):
            lines_html.append(
                f'<span style="background:#fff3cd;color:#856404;font-weight:bold">'
                f'{escaped}</span>'
            )
        elif line.startswith("+") and not line.startswith("+++"):
            lines_html.append(f'<span style="background:#dfd">{escaped}</span>')
        elif line.startswith("-") and not line.startswith("---"):
            lines_html.append(f'<span style="background:#fdd">{escaped}</span>')
        else:
            lines_html.append(escaped)
    pre_html = (
        '<pre style="font-size:0.85em;overflow-x:auto">'
        + "".join(lines_html)
        + "</pre>"
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
        f'<summary>差分を表示</summary>'
        f'<div class="diff-ph" style="color:#888;font-size:0.85em">'
        f'（展開すると差分を読み込みます）</div>'
        f'</details>'
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
               out_path: Path) -> int:
    """エントリをフォルダ単位の折り畳み（<details>）付き HTML に出力する。
    diff 内容は {html名}_diffs/ に外部 JS ファイルとして分離する。
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
            if e.ext.lower() in IMAGE_EXTENSIONS:
                diff_td = _image_compare_cell(e, old_root, new_root, out_path)
            elif e.diff_lines:
                key = f"d{diff_idx}"
                diff_idx += 1
                diff_td = _write_diff_js(e, key, diffs_dir)
            else:
                diff_td = ""
            file_rows += (
                f'<tr style="background:{color}">'
                f'<td>{html.escape(e.name)}</td>'
                f'<td>{html.escape(e.result)}</td>'
                f'<td>{html.escape(e.old_mtime)}</td>'
                f'<td>{html.escape(e.new_mtime)}</td>'
                f'<td>{html.escape(e.ext)}</td>'
                f'<td>{diff_td}</td>'
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
            f'<table>\n'
            f'<thead><tr>'
            f'<th>ファイル名</th><th>比較結果</th>'
            f'<th>旧更新日時</th><th>新更新日時</th><th>拡張子</th><th>差分</th>'
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
  body {{ font-family: sans-serif; font-size: 0.9em; }}
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
        written = write_html(entries, args.old, args.new_dir, out_path)

    print(f"  比較完了: {written} 件 → {out_path}")


if __name__ == "__main__":
    main()
