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

# bind_asset_virtualizer, bind_font_manager, bind_lifecycle_guard
# bind_path_redirector, bind_text_mapping, bind_user_interface_patcher
# bind_window_title_overrider, disable_forced_font, enable_debug_output
# assume_text_out_arg_c_is_byte_len, enable_window_title_override
# enable_text_mapping_debug, enable_x64dbg_1337_patch
# auto_apply_1337_patch_on_attach, auto_apply_1337_patch_on_hwbp_hit
# enable_attach_cleanup, enable_overlay_gl, enable_overlay
# enable_gl_painter, enable_win_event_hook, enable_worker_thread
# enable_hwbp_from_constants, enable_veh, enable_resource_pack
# embed_resource_pack, enable_iat_hook, enable_text_patch
# extract_text, enable_patch, extract_patch, enable_custom_font
# export_default_dll_main, enable_locale_emulator, enable_delayed_attach
# enable_dll_hijacking, export_hook_symbols, default_impl
FEATURES = [
    "g0win",
    "bind_text_mapping",
    "bind_font_manager",
    "enable_iat_hook",
    "assume_text_out_arg_c_is_byte_len",
    "enable_text_patch",
    "bind_window_title_overrider",
    "enable_window_title_override",
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
