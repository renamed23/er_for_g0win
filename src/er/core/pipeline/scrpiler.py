from er.utils.console import console
from er.utils.instructions import (
    Handler,
    HandlerResult,
    Instruction,
    ParseContext,
    assemble_one_inst,
    fix_offset,
    h,
    parse_data,
    string,
    u32,
)
from er.utils.binary import BinaryReader, BinaryType, se
from er.utils.fs import PathLike, collect_files, to_path
from er.utils.misc import read_json, write_json


def get_so4_inst_end(reader: BinaryReader, ctx: ParseContext) -> int:
    """
    计算当前 SO4 指令的结束偏移。

    指令格式已确认是：`u16 opcode + u16 inst_size + payload...`。

    Args:
        reader: 二进制读取器。
        ctx: 当前指令上下文。

    Returns:
        int: 当前指令结束位置（开区间偏移）。
    """
    inst_offset = ctx["offset"]
    size_offset = inst_offset + 2
    inst_size = int.from_bytes(reader.data[size_offset : size_offset + 2], "little")
    return inst_offset + inst_size


def read_vm_expr(reader: BinaryReader) -> list[BinaryType]:
    """
    读取一段 SO4 VM 表达式字节流。

    规则来自 `sub_429F90` / `sub_42A380`：
    - 每个 token 先读 1 字节；
    - token `0` 表示表达式结束；
    - token `1` / `2` 后额外跟随 4 字节；
    - 其余当前已确认 token 不带额外立即数。

    Args:
        reader: 二进制读取器。

    Returns:
        bytes: 包含终止 token `0` 在内的原始表达式字节流。
    """
    result = []

    while True:
        token = reader.read_u8()
        result.append(token)

        if token == 0:
            return result

        if token in {1, 2}:
            result.append(reader.read_bytes(4))


def expr_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    """
    读取 SO4 的表达式参数字节流。

    Args:
        reader: 二进制读取器。
        ctx: 解析上下文。

    Returns:
        HandlerResult: `bytes:...` 形式的原始表达式字节流。
    """
    _ = ctx
    return [se(arg) for arg in read_vm_expr(reader)]


def eval_vm_expr_static(expr_items: list[BinaryType]) -> int | None:
    """
    尝试对不依赖运行时变量的 VM 表达式做静态求值。

    当前仅在“所有输入都能静态确定”时返回结果；一旦遇到变量读取等运行时依赖，
    就返回 `None`，由上层决定是否拒绝该声明式解析。

    Args:
        expr_items: `read_vm_expr()` 读取出的表达式 token 流。

    Returns:
        int | None: 可静态求值时返回结果，否则返回 `None`。
    """
    stack: list[int] = []
    refs: list[int] = []
    item_index = 0

    while item_index < len(expr_items):
        item = expr_items[item_index]
        if not isinstance(item, int):
            raise TypeError(f"非法 expr token: {item}")

        token = int(item)
        item_index += 1

        match token:
            case 0:
                if not stack:
                    raise ValueError("表达式在终止时栈为空")
                return stack[-1]
            case 1:
                raw_imm = expr_items[item_index]
                item_index += 1
                if not isinstance(raw_imm, bytes):
                    raise TypeError(f"expr 立即数不是 bytes: {raw_imm}")
                stack.append(int.from_bytes(raw_imm, "little", signed=False))
                refs.append(-1)
            case 2:
                return None
            case 130:
                refs[-1] = -1
            case 131:
                stack[-1] = -stack[-1]
                refs[-1] = -1
            case 132:
                stack[-1] = ~stack[-1]
                refs[-1] = -1
            case 133:
                stack[-1] = int(stack[-1] == 0)
                refs[-1] = -1
            case 134:
                if len(refs) < 2 or refs[-2] < 0:
                    return None
                refs[-1] = refs[-2]
            case 135:
                return None
            case 136:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs * rhs)
                refs.append(-1)
            case 137:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs // rhs)
                refs.append(-1)
            case 138:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs % rhs)
                refs.append(-1)
            case 139:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs + rhs)
                refs.append(-1)
            case 140:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs - rhs)
                refs.append(-1)
            case 141:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs << rhs)
                refs.append(-1)
            case 142:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs >> rhs)
                refs.append(-1)
            case 143:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(lhs >= rhs))
                refs.append(-1)
            case 144:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(lhs > rhs))
                refs.append(-1)
            case 145:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(lhs <= rhs))
                refs.append(-1)
            case 146:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(lhs < rhs))
                refs.append(-1)
            case 147:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(lhs == rhs))
                refs.append(-1)
            case 148:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(lhs != rhs))
                refs.append(-1)
            case 149:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs & rhs)
                refs.append(-1)
            case 150:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs ^ rhs)
                refs.append(-1)
            case 151:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(lhs | rhs)
                refs.append(-1)
            case 152:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(bool(lhs) and bool(rhs)))
                refs.append(-1)
            case 153:
                rhs = stack.pop()
                lhs = stack.pop()
                refs.pop()
                refs.pop()
                stack.append(int(bool(lhs) or bool(rhs)))
                refs.append(-1)
            case 155:
                if len(stack) < 2 or len(refs) < 2 or refs[-2] < 0:
                    return None
                value = stack.pop()
                stack.pop()
                refs.pop()
                refs.pop()
                stack.append(value)
                refs.append(-1)
            case _:
                raise ValueError(f"未知 expr token: {token}")

    raise ValueError("表达式缺少终止 token 0")


def optional_expr_ref_handler(reader: BinaryReader, ctx: ParseContext) -> HandlerResult:
    """
    按当前指令长度判断是否存在一个可选的 `expr_ref` 尾参数。

    Args:
        reader: 二进制读取器。
        ctx: 当前指令上下文。

    Returns:
        HandlerResult: 若存在尾参则返回该表达式字节流，否则返回 `None`。
    """
    if reader.tell() >= get_so4_inst_end(reader, ctx):
        return None
    return expr_handler(reader, ctx)


def expr_u32_table_jump_handler(
    reader: BinaryReader, ctx: ParseContext
) -> HandlerResult:
    """
    读取 `expr(计数) + [计数 * u32 表项] + u32 跳转偏移` 结构。

    目前用于 `h("41 02") -> sub_43B460`。若计数表达式无法静态求值，
    则立即抛错，避免生成错误结构。

    Args:
        reader: 二进制读取器。
        ctx: 当前指令上下文。

    Returns:
        HandlerResult: 展平后的参数序列。
    """
    expr_items = read_vm_expr(reader)
    count = eval_vm_expr_static(expr_items)
    if count is None:
        raise ValueError("41 02 的计数 expr 含运行时变量，当前无法静态确定 repeat 次数")
    if count < 0:
        raise ValueError(f"41 02 的计数 expr 为负数: {count}")

    result = [se(arg) for arg in expr_items]
    for _ in range(count):
        result.append(se(reader.read_u32()))
    result.append(se(reader.read_u32()))
    return result


expr = Handler(expr_handler)
expr_ref = Handler(expr_handler)
optional_expr_ref = Handler(optional_expr_ref_handler)
expr_u32_table_jump = Handler(expr_u32_table_jump_handler)


FIX_INST_MAP = {
    "4D 02": [0],  # h("4D 02"): 条件成立时跳转到脚本内偏移
    "4E 02": [0],  # h("4E 02"): 条件不成立时跳转到脚本内偏移
}

INST_MAP = {
    # ==== 已确认锚点：直接来自 EXE 反编译，确保参数模型无歧义 ====
    # h("E2 00 xx") -> sub_437B30（file/time/text/file-op 家族）
    # 由 0x442D70 中 dword_4C9C4C = sub_437B30 可反推出主 opcode 为 0x00E2。
    # 该家族内部先读取 1 字节子 opcode，因此这里直接写成 3 字节签名。
    h("E2 00 00"): [expr_ref, expr, expr, string],
    h("E2 00 01"): [expr_ref.repeat(8), string],
    h("E2 00 02"): [expr.repeat(8), string],
    h("E2 00 03"): [expr_ref, string],
    h("E2 00 04"): [expr_ref],
    h("E2 00 05"): [],
    h("E2 00 06"): [expr_ref],
    h("E2 00 07"): [expr_ref.repeat(8)],
    h("E2 00 08"): [expr_ref.repeat(8)],
    h("E2 00 09"): [expr_ref.repeat(8)],
    h("E2 00 10"): [expr_ref, expr_ref],
    h("E2 00 11"): [expr, expr],
    h("E2 00 12"): [expr, expr],
    h("E2 00 13"): [expr_ref, string],
    h("E2 00 14"): [expr_ref, string],
    h("E2 00 15"): [expr_ref.repeat(8), string],
    h("E2 00 16"): [expr_ref.repeat(8), string],
    h("E2 00 17"): [string, string],
    h("E2 00 18"): [string, string],
    h("E2 00 19"): [],
    h("E2 00 20"): [string],
    h("E2 00 21"): [],
    h("E2 00 22"): [expr_ref],
    h("E2 00 23"): [expr, expr, expr],
    h("E2 00 24"): [expr, expr, expr, expr],
    h("E2 00 25"): [expr, expr, expr, expr, expr],
    h("E2 00 26"): [expr, expr, expr],
    h("E2 00 27"): [expr_ref, string, string],
    h("E2 00 28"): [string, expr, optional_expr_ref],
    h("E2 00 29"): [string, expr, optional_expr_ref],
    h("E2 00 30"): [string],
    h("E2 00 31"): [expr_ref, expr, expr, string],
    h("E2 00 32"): [expr_ref, string],
    h("E2 00 33"): [expr_ref, string],
    h("E2 00 34"): [expr],
    h("E2 00 35"): [expr],
    h("E2 00 36"): [expr, string, optional_expr_ref],
    h("E2 00 37"): [expr, string, expr, optional_expr_ref],
    # h("E3 00 xx") -> sub_4380B0（CDDA / AVI / media 家族）
    # 由 0x442D70 中 dword_4C9C50 = sub_4380B0 可反推出主 opcode 为 0x00E3。
    h("E3 00 00"): [expr_ref],
    h("E3 00 01"): [expr_ref],
    h("E3 00 02"): [expr_ref, expr_ref, expr],
    h("E3 00 03"): [expr_ref, string, expr.repeat(8)],
    h("E3 00 04"): [expr_ref, string, expr, expr],
    h("E3 00 05"): [],
    h("E3 00 06"): [],
    h("E3 00 07"): [expr_ref],
    h("E3 00 08"): [expr, expr, expr, expr],
    h("E3 00 09"): [expr_ref, expr_ref, expr],
    h("E3 00 10"): [expr_ref],
    h("E3 00 11"): [expr],
    # h("41 02") -> sub_43B460
    # 结构：expr(计数) + [计数 * u32 表项] + u32 跳转偏移。
    # 当前实现只在 expr 可静态求值时接受该结构；若 expr 依赖运行时变量会直接抛错。
    h("41 02"): [expr_u32_table_jump],
    # h("4D 02") -> sub_43BC10
    # dword_4AC290 += 4;
    # dwNewLong = sub_42A790();
    # if (sub_429F90(...)) dword_4AC290 = base + dwNewLong;
    # 即：u32 脚本内偏移 + expr 条件。
    h("4D 02"): [u32, expr],
    # h("4E 02") -> sub_43BC50
    # dword_4AC290 += 4;
    # dwNewLong = sub_42A790();
    # if (!sub_429F90(...)) dword_4AC290 = base + dwNewLong;
    # 即：u32 脚本内偏移 + expr 条件。
    h("4E 02"): [u32, expr],
    # h("50 02") -> sub_43BCF0
    # dword_4AC290 += 4;
    # dst = sub_42A380(...);
    # var[dst] = sub_42A790();
    # 即：expr_ref(变量槽引用) + u32 常量。
    h("50 02"): [expr_ref, u32],
    # ---
    h("37 02 1F 00 01 7E 00 00 00 00 01 00 00 00 00 00"): [string],
}


def decompile(input_path: PathLike, output_path: PathLike) -> None:
    """反编译：将二进制文件转换为JSON"""
    input_root = to_path(input_path)
    output_root = to_path(output_path)
    files = collect_files(input_root)

    for file in files:
        reader = BinaryReader(file.read_bytes())

        insts = parse_data(
            {
                "file_name": str(file),
                "offset": 0,
            },
            reader,
            INST_MAP,
        )

        assert reader.is_eof()

        # 保存为JSON
        rel_path = file.relative_to(input_root)
        out_file = output_root / f"{rel_path.as_posix()}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)

        write_json(out_file, insts)

    console.print(f"[OK] decompile 完成: {input_path} -> {output_path}", style="info")


def compile(input_path: PathLike, output_path: PathLike) -> None:
    """编译：将JSON转换回二进制文件"""
    input_root = to_path(input_path)
    output_root = to_path(output_path)
    files = collect_files(input_root, "json")

    for file in files:
        insts: list[Instruction] = read_json(file)

        # ========= 第一步：assemble instruction，计算新 offset =========
        old2new = {}  # old_offset -> new_offset
        cursor = 0

        for inst in insts:
            old_offset = inst["offset"]
            b = assemble_one_inst(inst)

            old2new[old_offset] = cursor
            cursor += len(b)

        # ========= 第二步：修复指令的偏移 =========
        insts = fix_offset(str(file), insts, old2new, FIX_INST_MAP)

        # ========= 第三步：assemble 修复过偏移的指令 =========
        new_blob = b"".join([assemble_one_inst(inst) for inst in insts])

        # 保存二进制文件
        rel_path = file.relative_to(input_root)
        out_file = output_root / rel_path.with_suffix("")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        out_file.write_bytes(new_blob)

    console.print(f"[OK] compile 完成: {input_path} -> {output_path}", style="info")
