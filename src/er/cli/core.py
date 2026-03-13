import os

from er.core import text_hook
from er.core import config
from er.core.config import FEATURES
from er.core.gal_json import GalJson
from er.core.pipeline import packer, textract
from er.processor.mapping import EncodingType, ReplacementPoolBuilder
from er.utils import fs
from er.utils.console import console


def extract() -> None:
    """提取(extract)相关逻辑"""
    console.print("执行提取...", style="info")

    packer.unpack_lzss_dir("workspace/packed_script", "workspace/script")

    gal_json = GalJson()
    textract.extract("workspace/script", gal_json)

    (
        gal_json.apply_current_to_raw_fields()
        .apply_add_tags()
        .save_to_path("workspace/raw.json")
    )

    console.print("提取完成", style="info")


def replace(check: bool = True) -> None:
    """替换(replace)相关逻辑"""
    console.print("执行替换...", style="info")

    gal_json = GalJson.load_from_path("workspace/translated.json")
    gal_json.apply_remove_tags()

    if check:
        (
            gal_json.check_command_consistency()
            .check_korean_characters()
            .check_japanese_characters()
            .check_duplicate_quotes()
            .check_length_discrepancy()
            .check_quote_consistency()
            .check_invisible_characters()
            .check_forbidden_words()
            .check_unpaired_quotes()
            .ok_or_print_error_and_exit()
        )

    (
        gal_json.apply_restore_whitespace()
        .apply_replace_rare_characters()
        .apply_replace_nested_brackets()
        .apply_replace_quotation_marks()
    )

    pool = (
        ReplacementPoolBuilder()
        .with_encoding(EncodingType.GBK)
        .exclude_from_gal_text(gal_json)
        .build()
    )
    gal_json.apply_mapping(pool)
    pool.save_mapping_to_path("workspace/generated/mapping.json")

    fs.copy_entry("assets/raw_text", "workspace/generated/raw_text", overwrite=True)
    fs.copy_entry(
        "assets/translated_text",
        "workspace/generated/translated_text",
        overwrite=True,
    )
    fs.copy_entry("workspace/raw.json", "workspace/generated/raw_text/text.json")
    gal_json.save_to_path("workspace/generated/translated_text/text.json")

    fs.merge_dir("assets/dist_extra", "workspace/generated/dist")
    config.generate_config_files()

    text_hook.TextHookBuilder(os.environ["TEXT_HOOK_PROJECT_PATH"]).build(
        FEATURES, panic="immediate-abort"
    )

    console.print("替换完成", style="info")


def fix_translated() -> None:
    """修复翻译JSON(fix_translated)的逻辑"""
    gal_json = GalJson.load_from_path("workspace/translated.json")
    (
        gal_json.apply_align_leading_digits()
        .apply_align_brackets_closure()
        .apply_align_leading_whitespace()
        .save_to_path("workspace/translated.json")
    )
