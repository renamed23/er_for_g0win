import json
from typing import Any

from er.utils.fs import PathLike, to_path


def str_or_none(val: object, context: str = "") -> str | None:
    """确保val为str或None，否则抛出TypeError异常"""
    if isinstance(val, (str, type(None))):
        return val
    msg = f"预期 str/None，但收到了  {type(val).__name__}"
    if context:
        msg += f" (上下文: {context})"
    raise TypeError(msg)


def ensure_str(val: object, context: str = "") -> str:
    """确保val为str，否则抛出TypeError异常"""
    if not isinstance(val, str):
        msg = f"期待 str，但收到了 {type(val).__name__}"
        if context:
            msg += f" (上下文: {context})"
        raise TypeError(msg)
    return val


def write_json(
    path: PathLike,
    value: object,
    *,
    create_dir: bool = True,
    ensure_ascii: bool = False,
    indent: int | None = 2,
    encoding="utf-8",
):
    """
    将 Python 对象序列化为 JSON 并写入文件。（如果路径没有目录，默认会创建）

    默认配置针对人类可读性优化：使用 UTF-8 编码支持非 ASCII 字符（如中文），
    并启用缩进格式化。

    Args:
        path: 目标文件路径，支持字符串或 Path 对象
        value: 要序列化的 Python 对象，需为 JSON 可序列化类型
    """
    path = to_path(path)
    if create_dir:
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding) as f:
        json.dump(value, f, ensure_ascii=ensure_ascii, indent=indent)


def read_json(path: PathLike, encoding="utf-8") -> Any:
    """
    从文件读取并解析 JSON 内容。

    返回解析后的原始 Python 对象（dict/list 等）。

    Args:
        path: JSON 文件路径，支持字符串或 Path 对象

    Returns:
        解析后的 Python 对象。
    """
    path = to_path(path)
    with path.open("r", encoding=encoding) as f:
        return json.load(f)
