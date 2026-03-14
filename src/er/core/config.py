from er.utils import misc


CONFIG = {
    "FONT_FACE": "SimHei",
    "CHAR_SET": 134,
    "FONT_FILTER": ["Microsoft YaHei", "Microsoft YaHei UI"],
    "WINDOW_TITLE": "咏奏",
    "ARG_GAME_TYPE": {
        "value": "うたかな",
        "type": "&str",
    },
}

HOOK_LISTS = {
    "enable": [],
    "disable": [
        "PropertySheetA",
        "ModifyMenuA",
        "MessageBoxA",
        "SetDlgItemTextA",
        "SetWindowTextA",
        "SendMessageA",
    ],
}

FEATURES = [
    "g0win",
    "text_hook",
    "iat_hook",
    "text_out_arg_c_is_bytes",
    "text_patch",
    "override_window_title",
]

BITMAP_FONT = {
    "font_path": "assets/font/unifont-17.0.03.otf",
    "font_size": 16,
    "padding": 2,
    "texture_max_width": 2048,
    "chars": "",
}


def generate_config_files() -> None:
    """生成配置文件"""
    misc.write_json("workspace/generated/config.json", CONFIG)
    misc.write_json("workspace/generated/hook_lists.json", HOOK_LISTS)


def generate_bitmap_font_config(chars: str) -> None:
    """生成位图字体配置文件"""
    BITMAP_FONT["chars"] = chars
    misc.write_json("workspace/generated/bitmap_font.json", BITMAP_FONT)
