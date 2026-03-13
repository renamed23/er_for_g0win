import os
from pathlib import Path

from er.core.gal_json import GalJson
from er.utils.binary import BinaryReader
from er.utils.console import console
from er.utils.fs import PathLike, collect_files, to_path


def should_ignore(s: str) -> bool:
    if s is None:
        return True
    s = s.strip()
    if s == "":
        return True
    if s.isascii():
        return True
    if len(s) == 1:
        return True
    if "$D" in s:
        return False
    if s == "@・":
        return True
    if ".LNK" in s:
        return True
    if ".sox" in s:
        return True
    # 检查Unicode私有区域字符和半角日语字符
    for char in s:
        code_point = ord(char)
        # 私有使用区: U+E000 - U+F8FF
        if 0xE000 <= code_point <= 0xF8FF:
            return True
        # 补充私有使用区-A: U+F0000 - U+FFFFF
        if 0xF0000 <= code_point <= 0xFFFFF:
            return True
        # 补充私有使用区-B: U+100000 - U+10FFFF
        if 0x100000 <= code_point <= 0x10FFFF:
            return True
        # 半角日语字符(标点+片假名): U+FF61 - U+FF9F
        if 0xFF61 <= code_point <= 0xFF9F:
            return True

        # 控制字符: C0 (0-31, 127) 和 C1 (128-159)
        if code_point < 32 and char not in ("\n", "\r", "\t"):
            return True
        if code_point == 127 or (128 <= code_point <= 159):
            return True
    return False


def _extract_from_script(
    script_path: Path,
    gal_json: GalJson,
) -> None:
    """
    从单个脚本中提取可翻译条目。

    Args:
        script_path: 输入脚本路径。
        gal_json: 原文容器。

    Returns:
        None
    """
    reader = BinaryReader(script_path.read_bytes())

    while not reader.is_eof():
        try:
            trial_reader = reader.fork()
            s = trial_reader.read_str()
            if should_ignore(s):
                reader.seek(1, os.SEEK_CUR)
                continue
            gal_json.add_item({"message": s})
            reader.seek(trial_reader.tell())
        except Exception as _:
            reader.seek(1, os.SEEK_CUR)
            pass


def extract(input_dir: PathLike, gal_json: GalJson) -> None:
    """
    提取目录下脚本文本到容器中。

    Args:
        input_dir: 反汇编后的脚本目录（json）。
        gal_json: 原文容器。

    Returns:
        None
    """
    source_root = to_path(input_dir)
    files = collect_files(source_root)

    for file in files:
        _extract_from_script(file, gal_json)

    console.print(
        f"[OK] 文本提取完成: {source_root} ({len(files)} files, {gal_json.total_count()} items)",
        style="info",
    )
