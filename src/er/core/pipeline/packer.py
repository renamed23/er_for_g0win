from pathlib import Path

from er.core.pipeline.lzss import compress_lzss, decompress_lzss
from er.utils.binary import BinaryReader, BinaryWriter
from er.utils.console import console
from er.utils.fs import PathLike, collect_files, to_path


LST_ENTRY_SIZE = 0x16
LST_NAME_SIZE = 14
COMPRESSED_EXTENSIONS = {".so4", ".so5"}
ENABLE_ROUNDTRIP_VALIDATION = False


def _decode_entry_name(raw_name: bytes) -> str:
    """解码 LST 中的固定长度文件名字段。

    Args:
        raw_name: 14 字节定长名称字段。

    Returns:
        str: 解码后的文件名。
    """

    return raw_name.split(b"\x00", 1)[0].decode("cp932")


def _encode_entry_name(file_name: str) -> bytes:
    """编码 LST 中的固定长度文件名字段。

    Args:
        file_name: 待编码文件名。

    Returns:
        bytes: 固定 14 字节编码结果。

    Raises:
        ValueError: 文件名编码后超过格式允许长度。
    """

    encoded_name = file_name.encode("cp932")
    if len(encoded_name) > LST_NAME_SIZE:
        raise ValueError(
            f"文件名过长，无法写入 {LST_NAME_SIZE} 字节索引字段: {file_name}"
        )
    return encoded_name.ljust(LST_NAME_SIZE, b"\x00")


def _read_archive_payload(file_data: bytes, file_name: str) -> bytes:
    """按条目规则解码 DAT 中的单个文件内容。

    Args:
        file_data: 从 DAT 中截取的条目原始字节。
        file_name: 条目文件名。

    Returns:
        bytes: 可落盘的文件内容。
    """

    if (
        len(file_data) <= 8
        or Path(file_name).suffix.lower() not in COMPRESSED_EXTENSIONS
    ):
        return file_data

    reader = BinaryReader(file_data)
    packed_size = int(reader.read_u32())
    unpacked_size = int(reader.read_u32())
    if packed_size <= 0 or unpacked_size <= 0 or packed_size + 8 != len(file_data):
        return file_data

    return decompress_lzss(reader.read_bytes(packed_size), unpacked_size)


def _build_archive_payload(file_name: str, file_data: bytes) -> bytes:
    """按条目规则构造写入 DAT 的单个文件内容。

    Args:
        file_name: 条目文件名。
        file_data: 原始文件字节。

    Returns:
        bytes: 归档时应写入 DAT 的字节。
    """

    if Path(file_name).suffix.lower() not in COMPRESSED_EXTENSIONS:
        return file_data

    packed_data = compress_lzss(file_data)
    writer = BinaryWriter()
    writer.write_u32(len(packed_data))
    writer.write_u32(len(file_data))
    writer.write_bytes(packed_data)
    return writer.to_bytes()


def _validate_roundtrip(
    file_name: str, original_data: bytes, stored_data: bytes
) -> None:
    """验证压缩条目可正确回环。

    Args:
        file_name: 条目文件名。
        original_data: 原始文件字节。
        stored_data: 写入 DAT 的条目字节。

    Returns:
        None

    Raises:
        ValueError: 回环验证失败。
    """

    if Path(file_name).suffix.lower() not in COMPRESSED_EXTENSIONS:
        return

    restored_data = _read_archive_payload(stored_data, file_name)
    if restored_data != original_data:
        raise ValueError(f"LZSS 回环验证失败: {file_name}")


def _maybe_validate_roundtrip(
    file_name: str, original_data: bytes, stored_data: bytes
) -> None:
    """按配置决定是否执行压缩回环校验。

    Args:
        file_name: 条目文件名。
        original_data: 原始文件字节。
        stored_data: 写入 DAT 的条目字节。

    Returns:
        None
    """

    if not ENABLE_ROUNDTRIP_VALIDATION:
        return

    _validate_roundtrip(file_name, original_data, stored_data)


def unpack_lzss_dir(input_dir: PathLike, out_dir: PathLike) -> None:
    """批量解压目录中的离散 LZSS 文件。

    会递归扫描输入目录下的所有文件，并按照相对路径写入输出目录。
    对于 ``.so4`` / ``.so5`` 文件，会尝试按 packer 条目规则读取 8 字节头并
    解压；若文件本身不满足该格式，则原样写出。

    Args:
        input_dir: 待批量解压的输入目录。
        out_dir: 解压结果输出目录。

    Returns:
        None

    Raises:
        ValueError: 输入目录为空时抛出。
    """

    input_root = to_path(input_dir)
    output_root = to_path(out_dir)
    if not input_root.is_dir():
        raise ValueError(f"输入目录不存在: {input_root}")

    files = collect_files(input_root)
    if not files:
        raise ValueError(f"输入目录为空，没有可解压文件: {input_root}")

    output_root.mkdir(parents=True, exist_ok=True)

    for file_path in files:
        relative_path = file_path.relative_to(input_root)
        restored_data = _read_archive_payload(file_path.read_bytes(), file_path.name)

        output_file = output_root / relative_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(restored_data)

    console.print(
        f"[OK] unpack_lzss_dir 完成: {input_root} -> {output_root}",
        style="info",
    )


def pack_lzss_dir(input_dir: PathLike, out_dir: PathLike) -> None:
    """批量压缩目录中的离散文件为 packer 使用的 LZSS 条目格式。

    会递归扫描输入目录下的所有文件，并按照相对路径写入输出目录。
    对于 ``.so4`` / ``.so5`` 文件，会写出 ``packed_size`` + ``unpacked_size``
    的 8 字节头，再附加 LZSS 压缩流；其它后缀文件原样复制。

    Args:
        input_dir: 待批量压缩的输入目录。
        out_dir: 压缩结果输出目录。

    Returns:
        None

    Raises:
        ValueError: 输入目录为空时抛出。
    """

    input_root = to_path(input_dir)
    output_root = to_path(out_dir)
    if not input_root.is_dir():
        raise ValueError(f"输入目录不存在: {input_root}")

    files = collect_files(input_root)
    if not files:
        raise ValueError(f"输入目录为空，没有可压缩文件: {input_root}")

    output_root.mkdir(parents=True, exist_ok=True)

    for file_path in files:
        relative_path = file_path.relative_to(input_root)
        original_data = file_path.read_bytes()
        stored_data = _build_archive_payload(file_path.name, original_data)
        _maybe_validate_roundtrip(file_path.name, original_data, stored_data)

        output_file = output_root / relative_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(stored_data)

    console.print(
        f"[OK] pack_lzss_dir 完成: {input_root} -> {output_root}",
        style="info",
    )


def unpack(input_path: PathLike, out_dir: PathLike) -> None:
    """
    解包。

    Args:
        input_path: 输入包路径。
        out_dir: 解包输出目录。

    Returns:
        None
    """
    source = to_path(input_path)
    output_dir = to_path(out_dir)
    if not source.is_file():
        raise FileNotFoundError(f"输入包不存在: {source}")

    lst_path = source.with_suffix(".lst")
    if not lst_path.is_file():
        raise FileNotFoundError(f"缺少同名索引文件: {lst_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    dat_data = source.read_bytes()
    lst_data = lst_path.read_bytes()
    if len(lst_data) % LST_ENTRY_SIZE != 0:
        raise ValueError(f"LST 大小非法，不是 {LST_ENTRY_SIZE:#x} 的整数倍: {lst_path}")

    reader = BinaryReader(lst_data)
    while not reader.is_eof():
        file_name = _decode_entry_name(reader.read_bytes(LST_NAME_SIZE))
        if not file_name:
            raise ValueError(f"发现空文件名条目: {lst_path}")

        offset = int(reader.read_u32())
        size = int(reader.read_u32())
        if offset + size > len(dat_data):
            raise ValueError(
                f"条目越界: name={file_name}, offset={offset}, size={size}, total={len(dat_data)}"
            )

        payload = dat_data[offset : offset + size]
        restored_data = _read_archive_payload(payload, file_name)
        output_file = output_dir / file_name
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(restored_data)

    console.print(
        f"[OK] unpack 完成: {source} -> {output_dir}",
        style="info",
    )


def pack(input_dir: PathLike, out_path: PathLike) -> None:
    """
    将目录内容重新打包。

    Args:
        input_dir: 输入目录路径。
        out_path: 输出包路径。

    Returns:
        None

    Raises:
        ValueError: 输入非法、命名冲突或字段超限。
    """
    input_root = to_path(input_dir)
    output_path = to_path(out_path)
    if not input_root.is_dir():
        raise ValueError(f"输入目录不存在: {input_root}")

    files = collect_files(input_root)
    if not files:
        raise ValueError(f"输入目录为空，没有可打包文件: {input_root}")

    seen_names: set[str] = set()
    entries: list[tuple[str, bytes]] = []
    for file_path in files:
        relative_path = file_path.relative_to(input_root)
        if len(relative_path.parts) != 1:
            raise ValueError(f"v1 DAT 不支持子目录: {relative_path.as_posix()}")

        file_name = relative_path.name
        folded_name = file_name.lower()
        if folded_name in seen_names:
            raise ValueError(f"存在重名条目（大小写不敏感）: {file_name}")
        seen_names.add(folded_name)

        original_data = file_path.read_bytes()
        stored_data = _build_archive_payload(file_name, original_data)
        _maybe_validate_roundtrip(file_name, original_data, stored_data)
        entries.append((file_name, stored_data))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lst_path = output_path.with_suffix(".lst")

    dat_writer = BinaryWriter()
    lst_writer = BinaryWriter()
    offset = 0
    for file_name, stored_data in entries:
        lst_writer.write_bytes(_encode_entry_name(file_name))
        lst_writer.write_u32(offset)
        lst_writer.write_u32(len(stored_data))
        dat_writer.write_bytes(stored_data)
        offset += len(stored_data)

    output_path.write_bytes(dat_writer.to_bytes())
    lst_path.write_bytes(lst_writer.to_bytes())

    console.print(
        f"[OK] pack 完成: {input_root} -> {output_path}",
        style="info",
    )
