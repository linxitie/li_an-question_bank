# -*- coding: utf-8 -*-
"""题组图片落盘通道（J-1-1）回归测试。

刻意使用**磁盘上真实存在的图片**（docx 抽图的扁平暂存图），
不使用合成/空文档 —— 符合「不准导入虚拟或者空的文档导入测试」的要求。

只测纯函数 save_images_for_group，不碰真实数据库。
"""
import os
import shutil
import sys
import tempfile
from typing import cast

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.question_ingest.images import (  # noqa: E402
    GROUP_IMG_ROOT,
    GROUP_URL_PREFIX,
    save_images_for_group,
)

STAGING = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'static', 'questions',
)


def _pick_real_image():
    """从真实暂存目录里挑一张**内容图**（classify_image 判定为 keep）。

    必须跳过黑名单图：全目录 37652 张里有 4041 张是推广图黑名单命中，
    题目侧的既有行为是 block 级直接剔除。若测试随便取第一张，很可能正好
    取到推广图，然后断言'<img>'必然失败 —— 那是测试夹具错，不是代码错。

    找不到内容图就 skip，绝不造假数据。
    """
    if not os.path.isdir(STAGING):
        return None
    try:
        from app.services.image_filters import classify_image
    except Exception:
        return None
    for name in sorted(os.listdir(STAGING)):
        if not name.lower().endswith('.png'):
            continue
        p = os.path.join(STAGING, name)
        try:
            if os.path.getsize(p) < 500:
                continue
            data = open(p, 'rb').read()
        except OSError:
            continue
        try:
            decision, _reason = classify_image(data)
        except Exception:
            continue
        if decision == 'keep':
            return p
    return None


def test_real_image_lands_in_group_dir_and_rewrites_placeholder():
    real = _pick_real_image()
    if not real:
        import pytest
        pytest.skip('磁盘上无真实暂存图片，跳过（不造假数据）')

    marker = os.path.splitext(os.path.basename(real))[0]
    gid = 987654
    staging = tempfile.mkdtemp(prefix='grp_stage_')
    shutil.copy2(real, os.path.join(staging, marker + '.png'))
    text = f'某派出所材料开头。[IMAGE:{marker}] 材料结尾。'

    try:
        new_text, urls = save_images_for_group(text, gid, staging_dir=staging)

        # 1) 占位符必须被替换成 <img>
        assert '[IMAGE:' not in new_text, '占位符未被替换'
        assert '<img src="' in new_text

        # 2) 返回 1 张图，且 URL 带 gid 分段（与题目侧 {qid}/ 同构）
        assert len(urls) == 1, f'期望 1 张图，实际 {urls}'
        url = urls[0]
        assert url.startswith(f'{GROUP_URL_PREFIX}/{gid}/'), url

        # 3) 文件必须真的落在题组专属目录下（与题目图物理隔离）
        disk = os.path.join(GROUP_IMG_ROOT, str(gid), os.path.basename(url))
        assert os.path.isfile(disk), f'落盘文件不存在: {disk}'
        assert os.path.getsize(disk) > 0, '落盘文件为空'

        # 4) URL 与磁盘路径对应得上（挂载后可直接访问）
        assert disk.replace('\\', '/').endswith(url.lstrip('/').split('static/')[-1])

        # 5) 不得污染题目图目录
        assert str(gid) not in os.path.basename(os.path.dirname(STAGING))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(os.path.join(GROUP_IMG_ROOT, str(gid)), ignore_errors=True)


def test_missing_source_image_strips_placeholder():
    """源图缺失时必须剔除占位符，否则前端稳定裂图。"""
    gid = 987655
    staging = tempfile.mkdtemp(prefix='grp_empty_')
    text = '材料。[IMAGE:deadbeef_1_0] 结束。'
    try:
        new_text, urls = save_images_for_group(text, gid, staging_dir=staging)
        assert urls == [], f'不应有图: {urls}'
        assert '[IMAGE:' not in new_text, '缺失源图的占位符必须被剔除'
        assert '<img' not in new_text
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(os.path.join(GROUP_IMG_ROOT, str(gid)), ignore_errors=True)


def test_path_traversal_marker_is_ignored():
    """目录穿越型 marker 必须既不落盘也不生成 URL。"""
    gid = 987656
    staging = tempfile.mkdtemp(prefix='grp_trav_')
    evil = '../../../../evil'
    text = f'材料。[IMAGE:{evil}] 结束。'
    try:
        new_text, urls = save_images_for_group(text, gid, staging_dir=staging)
        assert urls == [], f'穿越 marker 不得产出 URL: {urls}'
        # 正则不接受 '/'，故占位符既不匹配也不落盘
        assert not os.path.exists(os.path.join(GROUP_IMG_ROOT, str(gid), 'evil.png'))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(os.path.join(GROUP_IMG_ROOT, str(gid)), ignore_errors=True)


def test_no_placeholder_is_noop():
    gid = 987657
    text = '没有图的材料内容。'
    new_text, urls = save_images_for_group(text, gid)
    assert new_text == text
    assert urls == []


def test_empty_and_non_str_inputs_are_safe():
    # None/非字符串是运行时防御（解析器异常路径会喂进来），用 cast 绕过静态检查
    assert save_images_for_group('', 1) == ('', [])
    assert save_images_for_group(cast(str, None), 1) == (None, [])
    assert save_images_for_group(cast(str, 12345), 1) == (12345, [])


def test_dedup_digest_is_image_insensitive():
    """建组幂等键必须对图片状态不敏感，否则同材料会重复建组。"""
    from app.api.v1.question_import import _digest_for_group_dedup
    a = '某派出所材料。[IMAGE:abc123_1_0] 内容。'
    b = '某派出所材料。<img src="/static/question-groups/1/img_0_deadbeef.png" />内容。'
    assert _digest_for_group_dedup(a) == _digest_for_group_dedup(b), \
        '含占位符与已替换为 img 的同材料应得到同一指纹'
    assert _digest_for_group_dedup(a) == _digest_for_group_dedup(
        '某派出所材料。内容。'), '剔除图片标记后应等于纯文本指纹'