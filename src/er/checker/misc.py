import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from er.core.gal_text_t import DEFAULT_ITEM_TEXT_FIELDS, GalTextT
from er.utils.misc import ensure_str, str_or_none


DEFAULT_DUPLICATE_QUOTES: tuple[str, ...] = ("「「", "」」", "『『", "』』")

DEFAULT_FORBIDDEN_WORDS: tuple[str, ...] = (
    "学长",  # 统一为前辈
    "学姐",
    "学弟",  # 统一为后辈
    "学妹",
    "酱",  # 使用'小XX'而不是'XX酱'
    "肉刃",
    "桑",
    "甬道",
    "妳",  # 使用'你'
    "name",
    "dst",
    "message",
    ":",
    "甫",  # 使用 '刚' 或者 '刚刚'
)

KOREAN_PATTERN = re.compile(r"[ㄱ-ㅎㅏ-ㅣ가-힣]")

HIRAGANA_PATTERN = re.compile(r"[\u3040-\u309F]")

KATAKANA_PATTERN = re.compile(r"[\u30A0-\u30FF]")

INVISIBLE_PATTERN = re.compile(
    r"[\u200B-\u200F\u2060-\u2064\u206A-\u206F\uFEFF\u202A-\u202E\u180E\u2063]"
)

INVISIBLE_CHAR_NAMES: dict[str, str] = {
    "\u200b": "U+200B(零宽度空格)",
    "\u200c": "U+200C(零宽度非连接符)",
    "\u200d": "U+200D(零宽度连接符)",
    "\u200e": "U+200E(左至右标记)",
    "\u200f": "U+200F(右至左标记)",
    "\u2060": "U+2060(单词连接符)",
    "\u2061": "U+2061(函数应用)",
    "\u2062": "U+2062(不可见乘号)",
    "\u2063": "U+2063(不可见分隔符)",
    "\u2064": "U+2064(不可见加号)",
    "\u206a": "U+206A(不可见乘号变体)",
    "\u206b": "U+206B(不可见乘号变体)",
    "\ufeff": "U+FEFF(零宽度不换行空格/字节顺序标记)",
    "\u202a": "U+202A(左至右嵌入)",
    "\u202b": "U+202B(右至左嵌入)",
    "\u202c": "U+202C(弹出方向格式化)",
    "\u202d": "U+202D(左至右覆盖)",
    "\u202e": "U+202E(右至左覆盖)",
    "\u180e": "U+180E(蒙古文元音分隔符)",
}

OPEN_TO_CLOSE_QUOTES: dict[str, str] = {
    "「": "」",
    "『": "』",
    "“": "”",
    "‘": "’",
    "（": "）",
}


@dataclass(frozen=True)
class TextCheckTarget:
    """
    封装检查目标的上下文信息。

    Attributes:
        location: 错误发生的位置描述（如 'items[10]'）。
        field: 检查的字段名（如 'message'）。
        raw_text: 该字段对应的原始文本。
        text: 待检查的译文文本。
    """

    location: str
    field: str
    raw_text: str
    text: str


def _highlight_literals(text: str, literals: Iterable[str]) -> str:
    """
    在文本中用【】包裹指定的字面量以实现高亮显示。

    Args:
        text: 目标文本。
        literals: 需要高亮的字符串列表。

    Returns:
        处理后的字符串。
    """
    highlighted = text
    for literal in sorted(set(literals), key=len, reverse=True):
        highlighted = highlighted.replace(literal, f"【{literal}】")
    return highlighted


def _iter_check_targets(
    names: dict[str, str],
    items: list[dict[str, object]],
    item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
    include_names: bool = True,
) -> Iterable[TextCheckTarget]:
    """
    生成器：遍历所有待检查的文本目标，自动关联原文与译文。

    Args:
        names: 角色名映射表。
        items: 文本条目列表。
        item_fields: 需要检查的项目字段。
        include_names: 是否包含角色名表的检查。

    Yields:
        TextCheckTarget 对象。
    """
    if include_names:
        for raw_name, name in names.items():
            yield TextCheckTarget(
                location=f"names['{raw_name}']",
                field="name",
                raw_text=raw_name,
                text=name,
            )

    for index, item in enumerate(items):
        for field in item_fields:
            value = str_or_none(item.get(field))
            if value is None:
                continue

            raw_text = ensure_str(item.get(f"raw_{field}"))

            yield TextCheckTarget(
                location=f"items[{index}]",
                field=field,
                raw_text=raw_text,
                text=value,
            )


def _append_block_error(
    errors: list[str],
    target: TextCheckTarget,
    title: str,
    detail: str,
    highlighted: str,
) -> None:
    """
    向错误列表中添加一个格式化的错误报告块。

    每个块包含位置、字段信息、原/译文对照及高亮显示，末尾带空行分隔。
    """
    errors.append(f"{target.location} {target.field}字段{title}: {detail}")
    errors.append(f"  原文{target.field}: {target.raw_text}")
    errors.append(f"  译文{target.field}: {target.text}")
    errors.append(f"  高亮显示: {highlighted}")
    errors.append("")


def _check_by_literals(
    names: dict[str, str],
    items: list[dict[str, object]],
    errors: list[str],
    literals: tuple[str, ...],
    title: str,
    item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
    include_names: bool = True,
) -> None:
    """
    基于固定字面量列表进行文本匹配检查。

    遍历所有检查目标，若译文中包含任意一个指定的字面量（如禁用词、重复引号），
    则生成一个格式化的错误块并追加到 errors 列表中。

    Args:
        names: 角色名映射表 {原文: 译文}。
        items: 文本条目列表。
        errors: 错误信息收集列表。注意：本函数会直接修改此列表。
        literals: 待匹配的字面量元组（如禁用词列表）。
        title: 错误块的标题描述（如 "中包含禁用词"）。
        item_fields: 需要检查的项目字段名集合。
        include_names: 是否同时检查角色名映射表。
    """
    for target in _iter_check_targets(
        names,
        items,
        item_fields=item_fields,
        include_names=include_names,
    ):
        found = [literal for literal in literals if literal in target.text]
        if not found:
            continue

        _append_block_error(
            errors,
            target,
            title=title,
            detail=", ".join(found),
            highlighted=_highlight_literals(target.text, found),
        )


def _check_by_char_matches(
    names: dict[str, str],
    items: list[dict[str, object]],
    errors: list[str],
    title: str,
    finder: Callable[[str], list[str]],
    item_fields: tuple[str, ...] = DEFAULT_ITEM_TEXT_FIELDS,
    include_names: bool = True,
    detail_builder: Callable[[list[str]], str] | None = None,
) -> None:
    """
    基于字符匹配逻辑（通常是正则）进行文本检查。

    通过传入的 finder 函数提取文本中的非法字符，并支持自定义详情构建。

    Args:
        names: 角色名映射表。
        items: 文本条目列表。
        errors: 错误信息收集列表。
        title: 错误块的标题描述（如 "中包含韩文字符"）。
        finder: 匹配函数。接收一个字符串，返回所有匹配到的非法字符列表。
            通常使用 re.findall 实现。
        item_fields: 需要检查的项目字段名集合。
        include_names: 是否检查角色名映射表。
        detail_builder: 可选。自定义错误详情字符串的构建逻辑。
            接收 finder 返回的字符列表，返回一段描述文本。若为 None，则默认使用字符集的排序列表。
    """
    for target in _iter_check_targets(
        names,
        items,
        item_fields=item_fields,
        include_names=include_names,
    ):
        matches = finder(target.text)
        if not matches:
            continue

        detail = (
            detail_builder(matches) if detail_builder else str(sorted(set(matches)))
        )
        _append_block_error(
            errors,
            target,
            title=title,
            detail=detail,
            highlighted=_highlight_literals(target.text, sorted(set(matches))),
        )


class MiscCheckerMixin:
    """
    GalText 检查混合类

    提供多样化的文本合规性检查方法。
    所有方法均遵循链式调用约定，返回 self 并将错误记录至 self.errors。
    """

    def check_duplicate_quotes(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含重复的引号（如「「）。
        """
        _check_by_literals(
            self.names,
            self.items,
            self.errors,
            DEFAULT_DUPLICATE_QUOTES,
            title="中包含重复引号",
        )
        return self

    def check_forbidden_words(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含禁用词（如残留的 JSON 键名或不符合规范的称呼）。
        """
        _check_by_literals(
            self.names,
            self.items,
            self.errors,
            DEFAULT_FORBIDDEN_WORDS,
            title="中包含禁用词",
        )
        return self

    def check_korean_characters(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含韩文字符（ㄱ-ㅎ, ㅏ-ㅣ, 가-힣）。
        """
        _check_by_char_matches(
            self.names,
            self.items,
            self.errors,
            title="中包含韩文字符",
            finder=lambda text: KOREAN_PATTERN.findall(text),
        )
        return self

    def check_japanese_characters(self: GalTextT) -> GalTextT:
        """
        检查译文中是否包含日语假名（平假名/片假名）。

        注：本检查不包含日语汉字，仅针对明确的假名残留。
        """

        def finder(text: str) -> list[str]:
            return HIRAGANA_PATTERN.findall(text) + KATAKANA_PATTERN.findall(text)

        def detail_builder(matches: list[str]) -> str:
            hiragana = sorted({ch for ch in matches if HIRAGANA_PATTERN.fullmatch(ch)})
            katakana = sorted({ch for ch in matches if KATAKANA_PATTERN.fullmatch(ch)})
            details: list[str] = []
            if hiragana:
                details.append(f"平假名{hiragana}")
            if katakana:
                details.append(f"片假名{katakana}")
            return " ".join(details)

        _check_by_char_matches(
            self.names,
            self.items,
            self.errors,
            title="中包含日语假名字符",
            finder=finder,
            detail_builder=detail_builder,
        )
        return self

    def check_invisible_characters(self: GalTextT) -> GalTextT:
        """
        检查并识别译文中的不可见字符（如零宽度空格 U+200B）。

        高亮显示时会替换为字符对应的 Unicode 名称或编码，方便定位。
        """
        for target in _iter_check_targets(self.names, self.items):
            invisible_matches = INVISIBLE_PATTERN.findall(target.text)
            if not invisible_matches:
                continue

            char_count: dict[str, int] = {}
            for char in invisible_matches:
                char_count[char] = char_count.get(char, 0) + 1

            details: list[str] = []
            for char, count in char_count.items():
                char_name = INVISIBLE_CHAR_NAMES.get(
                    char, f"U+{ord(char):04X}(未知不可见字符)"
                )
                details.append(f"{char_name}: {count}次")

            highlighted = target.text
            for char in char_count:
                char_code = INVISIBLE_CHAR_NAMES.get(char, f"U+{ord(char):04X}").split(
                    "("
                )[0]
                highlighted = highlighted.replace(char, f"【{char_code}】")

            _append_block_error(
                self.errors,
                target,
                title="中包含不可见字符",
                detail="; ".join(details),
                highlighted=highlighted,
            )
        return self

    def check_unpaired_quotes(self: GalTextT) -> GalTextT:
        """
        使用栈算法检查成对标点（「」、『』、“”、‘’、（））是否正确闭合。

        支持嵌套检查。如果发现未关闭或多余的引号，将记录具体位置。
        """
        close_to_open = {v: k for k, v in OPEN_TO_CLOSE_QUOTES.items()}

        for target in _iter_check_targets(self.names, self.items):
            stack: list[tuple[str, int]] = []
            details: list[str] = []

            for pos, char in enumerate(target.text):
                if char in OPEN_TO_CLOSE_QUOTES:
                    stack.append((char, pos))
                elif char in close_to_open:
                    if stack and stack[-1][0] == close_to_open[char]:
                        stack.pop()
                    else:
                        details.append(f"位置 {pos}: 多余的 '{char}'")

            for quote_char, pos in stack:
                details.append(f"位置 {pos}: 未关闭的 '{quote_char}'")

            if not details:
                continue

            highlighted_chars = list(target.text)
            for quote_char, pos in stack:
                highlighted_chars[pos] = f"【{quote_char}】"

            temp_stack: list[str] = []
            for pos, char in enumerate(target.text):
                if char in OPEN_TO_CLOSE_QUOTES:
                    temp_stack.append(char)
                elif char in close_to_open:
                    if temp_stack and temp_stack[-1] == close_to_open[char]:
                        temp_stack.pop()
                    else:
                        highlighted_chars[pos] = f"【{char}】"

            _append_block_error(
                self.errors,
                target,
                title="中存在未配对的引号",
                detail="; ".join(details),
                highlighted="".join(highlighted_chars),
            )

        return self

    def check_quote_consistency(self: GalTextT) -> GalTextT:
        """
        对比原文与译文的首尾引号是否一致。

        严格校验引号类型。如果原文以「开头，译文也必须以「开头。
        """

        def _contains_quote_marker(text: str) -> bool:
            return bool(text) and (text[0] in "「『」』" or text[-1] in "「『」』")

        for target in _iter_check_targets(self.names, self.items):
            raw_text = target.raw_text.strip()
            text = target.text.strip()

            if not raw_text or not text:
                continue

            if not (_contains_quote_marker(raw_text) or _contains_quote_marker(text)):
                continue

            has_error = False
            details: list[str] = []

            if raw_text[0] in "「『" and raw_text[0] != text[0]:
                has_error = True
                details.append(f"开头引号不一致: 原文'{raw_text[0]}' 译文'{text[0]}'")
            if raw_text[-1] in "」』" and raw_text[-1] != text[-1]:
                has_error = True
                details.append(f"结尾引号不一致: 原文'{raw_text[-1]}' 译文'{text[-1]}'")
            if text[0] in "「『" and raw_text[0] != text[0]:
                has_error = True
                details.append(
                    f"译文额外开头引号不一致: 原文'{raw_text[0]}' 译文'{text[0]}'"
                )
            if text[-1] in "」』" and raw_text[-1] != text[-1]:
                has_error = True
                details.append(
                    f"译文额外结尾引号不一致: 原文'{raw_text[-1]}' 译文'{text[-1]}'"
                )

            if has_error:
                _append_block_error(
                    self.errors,
                    target,
                    title="首尾引号不一致",
                    detail="; ".join(details),
                    highlighted=target.text,
                )
        return self

    def check_length_discrepancy(
        self: GalTextT,
        max_ratio: float = 2.0,
        min_ratio: float = 0.3,
    ) -> GalTextT:
        """
        根据原文长度校验译文长度的异常偏差。

        Args:
            max_ratio: 最大比例阈值，超过则视为过长。
            min_ratio: 最小比例阈值，低于则视为过短。
        """
        for target in _iter_check_targets(self.names, self.items):
            raw_len = len(target.raw_text)
            text_len = len(target.text)

            if raw_len == 0:
                continue

            ratio = text_len / raw_len
            if ratio > max_ratio:
                _append_block_error(
                    self.errors,
                    target,
                    title="长度过长",
                    detail=(
                        f"原文长度 {raw_len}，译文长度 {text_len}，"
                        f"比例 {ratio:.2f} (超过阈值 {max_ratio})"
                    ),
                    highlighted=target.text,
                )
            elif ratio < min_ratio:
                _append_block_error(
                    self.errors,
                    target,
                    title="长度过短",
                    detail=(
                        f"原文长度 {raw_len}，译文长度 {text_len}，"
                        f"比例 {ratio:.2f} (低于阈值 {min_ratio})"
                    ),
                    highlighted=target.text,
                )

        return self

    def check_max_text_len(self: GalTextT, max_text_len: int = 128) -> GalTextT:
        """
        检查译文单行是否超过游戏长度限制。

        Args:
            max_text_len: 允许的最大字符数。
        """
        for target in _iter_check_targets(
            self.names,
            self.items,
            item_fields=("message",),
            include_names=False,
        ):
            text_len = len(target.text)
            if text_len <= max_text_len:
                continue

            _append_block_error(
                self.errors,
                target,
                title="超长",
                detail=f"{text_len} > {max_text_len}",
                highlighted=target.text,
            )
        return self

    def check_command_consistency(self: GalTextT) -> GalTextT:
        """
        检查原文与译文中的指令（$后跟字母数字）是否完全一致。

        校验逻辑：提取所有符合 $[a-zA-Z0-9]+ 格式的指令，要求数量和顺序必须完全相同。
        """
        # 匹配 $ 后面跟着一系列字母或数字
        command_pattern = re.compile(r"\$[a-zA-Z0-9]+")

        for target in _iter_check_targets(self.names, self.items):
            raw_cmds = command_pattern.findall(target.raw_text)
            text_cmds = command_pattern.findall(target.text)

            if raw_cmds == text_cmds:
                continue

            # 构造错误详情
            if len(raw_cmds) != len(text_cmds):
                detail = (
                    f"指令数量不符: 原文 {len(raw_cmds)} 个, 译文 {len(text_cmds)} 个"
                )
            else:
                # 找出第一个不匹配的位置
                diff_idx = next(
                    i for i, (r, t) in enumerate(zip(raw_cmds, text_cmds)) if r != t
                )
                detail = f"第 {diff_idx + 1} 个指令不匹配: 原文 '{raw_cmds[diff_idx]}', 译文 '{text_cmds[diff_idx]}'"

            _append_block_error(
                self.errors,
                target,
                title="指令不一致",
                detail=f"{detail} | 原文序列: {raw_cmds} | 译文序列: {text_cmds}",
                highlighted=_highlight_literals(
                    target.text, set(text_cmds) | set(raw_cmds)
                ),
            )

        return self
