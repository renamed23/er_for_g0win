from er.core.gal_json import GalJson


def generate_testfile_shorten():
    """生成变短的测试文件(generate_testfile_shorten)"""
    (
        GalJson.load_from_path("workspace/raw.json")
        .apply_remove_hiragana(3)
        .apply_map_all_to_zhong()
        .save_to_path("workspace/translated.json")
    )


def generate_testfile_lengthen():
    """生成变长的测试文件(generate_testfile_lengthen)"""
    (
        GalJson.load_from_path("workspace/raw.json")
        .apply_add_chinese_test_tag()
        .save_to_path("workspace/translated.json")
    )
