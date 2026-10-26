"""分类树 v2 常量结构校验（纯数据，不连数据库）"""
from scripts.admin.seed import KNOWLEDGE_TREE_V2


def _subjects():
    return KNOWLEDGE_TREE_V2


def _flat_l2():
    for subject, sub_categories in KNOWLEDGE_TREE_V2.items():
        for sub_name, l2_map in sub_categories.items():
            for l2_name, l3_list in l2_map.items():
                yield subject, sub_name, l2_name, l3_list


def test_subject_keys():
    assert set(KNOWLEDGE_TREE_V2.keys()) == {"行测", "申论", "公专"}


def test_total_counts():
    assert len(list(_flat_l2())) == 91
    assert sum(len(l3) for *_, l3 in _flat_l2()) == 427
    assert len(list(_flat_l2())) + sum(len(l3) for *_, l3 in _flat_l2()) == 518


def test_per_subject_counts():
    expected = {"行测": (31, 146), "申论": (25, 109), "公专": (35, 172)}
    for subject, (l2_count, l3_count) in expected.items():
        sub_categories = KNOWLEDGE_TREE_V2[subject]
        l2_total = sum(len(l2_map) for l2_map in sub_categories.values())
        l3_total = sum(
            len(l3_list) for l2_map in sub_categories.values() for l3_list in l2_map.values()
        )
        assert (l2_total, l3_total) == (l2_count, l3_count), subject


def test_each_l2_has_single_other_and_valid_size():
    for subject, sub_name, l2_name, l3_list in _flat_l2():
        label = f"{subject}/{sub_name}/{l2_name}"
        assert l3_list.count("其他") == 1, label
        assert 4 <= len(l3_list) <= 8, label


def test_no_duplicate_l3_within_l2():
    for subject, sub_name, l2_name, l3_list in _flat_l2():
        label = f"{subject}/{sub_name}/{l2_name}"
        assert len(set(l3_list)) == len(l3_list), label


def test_no_duplicate_l2_and_no_other_l2():
    for subject, sub_categories in KNOWLEDGE_TREE_V2.items():
        for sub_name, l2_map in sub_categories.items():
            label = f"{subject}/{sub_name}"
            assert len(l2_map) == len(set(l2_map)), label
            assert "其他" not in l2_map, label


def test_no_empty_levels():
    for subject, sub_categories in KNOWLEDGE_TREE_V2.items():
        assert sub_categories, subject
        for sub_name, l2_map in sub_categories.items():
            assert l2_map, f"{subject}/{sub_name}"
            for l2_name, l3_list in l2_map.items():
                assert l3_list, f"{subject}/{sub_name}/{l2_name}"


def test_spot_checks():
    assert KNOWLEDGE_TREE_V2["行测"]["言语理解与表达"]["逻辑填空"] == [
        "实词填空",
        "成语填空",
        "混搭填空",
        "关联词",
        "其他",
    ]
    public_doc = KNOWLEDGE_TREE_V2["申论"]["应用文写作"]["公文写作"]
    assert len(public_doc) == 7
    assert public_doc[-1] == "其他"
    assert "公安执法监督" in KNOWLEDGE_TREE_V2["公专"]["基础知识"]
