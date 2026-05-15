"""
test/test_output_diff.py
output_diff.py のテストスイート

IT-1: TC-7a, TC-7b, TC-8  （フレームワーク: CLIエラー検出）
IT-2: TC-1〜4, TC-10a, TC-10b（比較ロジック）
IT-3: TC-6, TC-12           （CSV 出力）
IT-4: TC-5                  （HTML 出力）
IT-5: TC-9                  （unified diff 展開）
IT-6: TC-11                 （実データ smoke test）
"""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "output_diff.py"


# ─────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────

def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def make_tree(base: Path, files: dict[str, str]) -> None:
    """files = {"相対パス": "ファイル内容"} でフォルダツリーを作成する。"""
    for rel, content in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ─────────────────────────────────────────
# IT-1: フレームワーク（CLIエラー検出）
# ─────────────────────────────────────────

def test_tc7a_old_not_found(tmp_path):
    """TC-7a: --old が存在しない場合は exit=1 で終了する。"""
    new_dir = tmp_path / "new"
    new_dir.mkdir()
    result = run("--old", str(tmp_path / "not_exist"), "--new", str(new_dir))
    assert result.returncode == 1


def test_tc7b_new_not_found(tmp_path):
    """TC-7b: --new が存在しない場合は exit=1 で終了する（RQ-8）。"""
    old_dir = tmp_path / "old"
    old_dir.mkdir()
    result = run("--old", str(old_dir), "--new", str(tmp_path / "not_exist"))
    assert result.returncode == 1


def test_tc8_html_and_csv_exclusive(tmp_path):
    """TC-8: --html と --csv を同時指定した場合は exit=1 で終了する。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    result = run("--old", str(old_dir), "--new", str(new_dir), "--html", "--csv")
    assert result.returncode == 1


# ─────────────────────────────────────────
# IT-2: 比較ロジック
# ─────────────────────────────────────────

def test_tc1_identical(tmp_path):
    """TC-1: 両フォルダに同一内容のファイルが存在する場合は Identical に分類される。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"a.csv": "col1,col2\n1,2\n"})
    make_tree(new_dir, {"a.csv": "col1,col2\n1,2\n"})

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert len(entries) == 1
    assert entries[0].result == "Identical"
    assert entries[0].name == "a.csv"


def test_tc2_different(tmp_path):
    """TC-2: 両フォルダに存在するが内容が異なるファイルは Different に分類される。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"a.csv": "old content\n"})
    make_tree(new_dir, {"a.csv": "new content\n"})

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert len(entries) == 1
    assert entries[0].result == "Different"


def test_tc3_left_only(tmp_path):
    """TC-3: 旧フォルダのみに存在するファイルは Left only に分類される。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"only_old.csv": "data\n"})
    new_dir.mkdir()

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert len(entries) == 1
    assert entries[0].result == "Left only"
    assert entries[0].new_mtime == ""


def test_tc4_right_only(tmp_path):
    """TC-4: 新フォルダのみに存在するファイルは Right only に分類される。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    make_tree(new_dir, {"only_new.csv": "data\n"})

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert len(entries) == 1
    assert entries[0].result == "Right only"
    assert entries[0].old_mtime == ""


def test_tc10a_binary_extension(tmp_path):
    """TC-10a: 拡張子 .png のファイルはバイナリ扱いで Identical / Different に分類される。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    # Identical ケース
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    (old_dir).mkdir()
    (new_dir).mkdir()
    (old_dir / "img.png").write_bytes(png_bytes)
    (new_dir / "img.png").write_bytes(png_bytes)

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert entries[0].result == "Identical"

    # Different ケース
    (new_dir / "img.png").write_bytes(png_bytes + b"\xff")
    entries = compare_folders(old_dir, new_dir)
    assert entries[0].result == "Different"


def test_tc10b_binary_fallback(tmp_path):
    """TC-10b: 拡張子 .csv だが内容が非 UTF-8 バイナリのファイルはバイナリ扱いになる。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    # NUL バイトを含む → バイナリ判定
    binary_content = b"col1,col2\x00\x80\x81\x82"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "weird.csv").write_bytes(binary_content)
    (new_dir / "weird.csv").write_bytes(binary_content)

    from scripts.output_diff import is_binary
    assert is_binary(old_dir / "weird.csv") is True

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert entries[0].result == "Identical"


def test_tc10c_png_idat_identical(tmp_path):
    """TC-10c: PNG で IDAT（画像本体）が同一でメタデータのみ異なる場合は Identical に分類される。"""
    import struct, zlib

    def make_png(text_meta: bytes) -> bytes:
        """最小限の PNG を生成する（IHDR + tEXt + IDAT + IEND）。"""
        def chunk(name: bytes, data: bytes) -> bytes:
            import zlib as _zlib
            return (
                struct.pack(">I", len(data))
                + name
                + data
                + struct.pack(">I", _zlib.crc32(name + data) & 0xFFFFFFFF)
            )

        sig = b"\x89PNG\r\n\x1a\n"
        # IHDR: 1x1 px, 8-bit RGB
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        # IDAT: 最小限の圧縮画像データ（1px=3bytes + filtertype byte）
        raw = b"\x00\xff\x00\x00"  # filter=0, R=255, G=0, B=0
        idat_data = zlib.compress(raw)
        ihdr = chunk(b"IHDR", ihdr_data)
        text = chunk(b"tEXt", text_meta)
        idat = chunk(b"IDAT", idat_data)
        iend = chunk(b"IEND", b"")
        return sig + ihdr + text + idat + iend

    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()

    # IDAT は同一、tEXt メタデータのみ異なる
    old_png = make_png(b"Software\x00Matplotlib version3.10.6")
    new_png = make_png(b"Software\x00Matplotlib version3.10.8")
    (old_dir / "graph.png").write_bytes(old_png)
    (new_dir / "graph.png").write_bytes(new_png)

    assert old_png != new_png, "前提: バイトレベルでは異なること"

    from scripts.output_diff import compare_folders
    entries = compare_folders(old_dir, new_dir)
    assert len(entries) == 1
    assert entries[0].result == "Identical", f"IDAT同一のPNGはIdenticalであること: {entries[0].result}"




def test_tc6_csv_output(tmp_path):
    """TC-6: --csv 指定時に CSV が生成される（ヘッダ・列数・utf-8-sig）。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"a.csv": "old\n", "b.csv": "same\n"})
    make_tree(new_dir, {"a.csv": "new\n", "b.csv": "same\n"})
    out = tmp_path / "out.csv"

    result = run("--old", str(old_dir), "--new", str(new_dir), "--csv", "--out", str(out))
    assert result.returncode == 0
    assert out.exists()

    # BOM 確認
    raw = out.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf", "utf-8-sig BOM が付いていない"

    # ヘッダ・列数確認
    from scripts.output_diff import CSV_COLUMNS
    with open(out, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    assert header == CSV_COLUMNS
    assert len(rows) == 2
    assert all(len(r) == len(CSV_COLUMNS) for r in rows)


def test_tc12_stdout_on_success(tmp_path):
    """TC-12: stdout に '比較完了: N 件 → {out_path}' が含まれる。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"a.csv": "x\n"})
    make_tree(new_dir, {"a.csv": "y\n"})
    out = tmp_path / "result.csv"

    result = run("--old", str(old_dir), "--new", str(new_dir), "--csv", "--out", str(out))
    assert result.returncode == 0
    assert "比較完了:" in result.stdout
    assert str(out) in result.stdout


# ─────────────────────────────────────────
# IT-4: HTML 出力
# ─────────────────────────────────────────

def test_tc5_html_output(tmp_path):
    """TC-5: --html 指定時に HTML が生成される（ファイル存在・テーブル・行色・ソート順）。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"diff.csv": "old\n", "same.csv": "x\n", "left.csv": "l\n"})
    make_tree(new_dir, {"diff.csv": "new\n", "same.csv": "x\n", "right.csv": "r\n"})
    out = tmp_path / "out.html"

    result = run("--old", str(old_dir), "--new", str(new_dir), "--html", "--out", str(out))
    assert result.returncode == 0
    assert out.exists()

    content = out.read_text(encoding="utf-8")
    assert "<table>" in content
    # 行色確認
    assert "#fff3cd" in content   # Different
    assert "#f8d7da" in content   # Left only
    assert "#d4edda" in content   # Right only
    # ソート順確認（Different が Left only より前）
    assert content.index("Different") < content.index("Left only")


# ─────────────────────────────────────────
# IT-5: unified diff 展開
# ─────────────────────────────────────────

def test_tc9_unified_diff_in_html(tmp_path):
    """TC-9: Different テキストファイルの diff が外部 JS ファイルに書き出される。
    HTML にはプレースホルダ <details> が含まれ、diff 内容は _diffs/*.js に格納される。"""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    make_tree(old_dir, {"a.csv": "line1\nold_line\nline3\n"})
    make_tree(new_dir, {"a.csv": "line1\nnew_line\nline3\n"})
    out = tmp_path / "out.html"

    result = run("--old", str(old_dir), "--new", str(new_dir), "--html", "--out", str(out))
    assert result.returncode == 0

    content = out.read_text(encoding="utf-8")
    # HTML にはプレースホルダ <details> と lazy-load 属性が存在する
    assert "<details" in content
    assert "loadDiff" in content
    assert "data-diff-src" in content

    # diff 内容は外部 JS ファイルに書き出される
    diffs_dir = out.parent / (out.stem + "_diffs")
    assert diffs_dir.exists(), "diffs ディレクトリが存在しない"
    js_files = list(diffs_dir.glob("*.js"))
    assert len(js_files) == 1, f"JS ファイルが 1 件あること: {js_files}"
    js_content = js_files[0].read_text(encoding="utf-8")
    assert "new_line" in js_content
    assert "old_line" in js_content


# ─────────────────────────────────────────
# IT-6: 実データ smoke test
# ─────────────────────────────────────────

@pytest.mark.skipif(
    not (Path(__file__).parent.parent / "input" /
         "scheduling_requirement_check_analysis_result").exists(),
    reason="実データが存在しない場合はスキップ",
)
def test_tc11_real_data(tmp_path):
    """TC-11: 実データで比較結果が生成されること（smoke test）。"""
    repo = Path(__file__).parent.parent
    old_dir = repo / "input" / "scheduling_requirement_check_analysis_result"
    new_dir = repo / "input" / "ver1_m02_AP_再解析結果" / "output"
    out = tmp_path / "smoke.html"

    result = run("--old", str(old_dir), "--new", str(new_dir), "--html", "--out", str(out))
    assert result.returncode == 0
    assert out.exists()
    assert out.stat().st_size > 0
