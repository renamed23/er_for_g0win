WINDOW_SIZE = 0x1000
MIN_MATCH = 3
INITIAL_WINDOW_POS = WINDOW_SIZE - 0x12


def _write_window_bytes(window: bytearray, window_pos: int, chunk: bytes) -> int:
    """将一段字节写入循环滑动窗口。

    Args:
        window: LZSS 4KB 滑动窗口。
        window_pos: 当前窗口写入位置。
        chunk: 待写入窗口的字节序列。

    Returns:
        int: 写入后的新窗口位置。
    """

    chunk_length = len(chunk)
    first_part = min(chunk_length, WINDOW_SIZE - window_pos)
    window[window_pos : window_pos + first_part] = chunk[:first_part]

    remaining = chunk_length - first_part
    if remaining > 0:
        window[:remaining] = chunk[first_part:]

    return (window_pos + chunk_length) & (WINDOW_SIZE - 1)


def decompress_lzss(data: bytes, expected_size: int) -> bytes:
    """解压 FFA 风格 LZSS 数据。

    Args:
        data: 压缩后的 LZSS 数据，不包含 8 字节长度头。
        expected_size: 期望解压后的字节数。

    Returns:
        bytes: 解压结果。

    Raises:
        ValueError: 压缩流非法或解压长度与预期不一致。
    """

    window = bytearray(b"\x00" * WINDOW_SIZE)
    window_pos = INITIAL_WINDOW_POS
    output = bytearray(expected_size)
    write_pos = 0
    source_pos = 0

    while write_pos < expected_size:
        if source_pos >= len(data):
            raise ValueError("LZSS 数据提前结束，无法读取控制字节")
        flags = data[source_pos]
        source_pos += 1

        if flags == 0xFF:
            literal_count = min(8, expected_size - write_pos)
            if source_pos + literal_count > len(data):
                raise ValueError("LZSS 数据提前结束，无法批量读取字面量")

            chunk = data[source_pos : source_pos + literal_count]
            source_pos += literal_count
            output[write_pos : write_pos + literal_count] = chunk
            window_pos = _write_window_bytes(window, window_pos, chunk)
            write_pos += literal_count
            continue

        for bit in range(8):
            if write_pos >= expected_size:
                break

            if flags & (1 << bit):
                if source_pos >= len(data):
                    raise ValueError("LZSS 数据提前结束，无法读取字面量")
                value = data[source_pos]
                source_pos += 1
                output[write_pos] = value
                write_pos += 1
                window[window_pos] = value
                window_pos = (window_pos + 1) & (WINDOW_SIZE - 1)
                continue

            if source_pos + 1 >= len(data):
                raise ValueError("LZSS 数据提前结束，无法读取回溯引用")

            low = data[source_pos]
            high = data[source_pos + 1]
            source_pos += 2

            match_pos = low | ((high & 0xF0) << 4)
            match_length = (high & 0x0F) + MIN_MATCH

            for index in range(match_length):
                value = window[(match_pos + index) & (WINDOW_SIZE - 1)]
                output[write_pos] = value
                write_pos += 1
                window[window_pos] = value
                window_pos = (window_pos + 1) & (WINDOW_SIZE - 1)
                if write_pos >= expected_size:
                    break

    if write_pos != expected_size:
        raise ValueError(
            f"LZSS 解压长度不匹配: expected={expected_size}, actual={write_pos}"
        )
    return bytes(output)


def compress_lzss(data: bytes) -> bytes:
    """压缩为与 ``decompress_lzss`` 对应的 LZSS 数据流。

    Args:
        data: 原始字节数据。

    Returns:
        bytes: 压缩后的数据流，不包含 8 字节长度头。

    Notes:
        这里采用“仅输出字面量块”的极简策略，不主动生成回溯引用。
        这样压缩率较低，但编码复杂度为线性，适合本项目“只要求可回环、
        优先整体打包速度”的场景。
    """

    output = bytearray()
    for chunk_start in range(0, len(data), 8):
        chunk = data[chunk_start : chunk_start + 8]
        output.append((1 << len(chunk)) - 1)
        output.extend(chunk)

    return bytes(output)
