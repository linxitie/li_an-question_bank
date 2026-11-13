# -*- coding: utf-8 -*-
"""生成两张演示配图（渐变 + 中文标题 + 网格），供三轮验收截图使用。

输出：_run/demo-img-1.png、_run/demo-img-2.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    r'C:\Windows\Fonts\msyhbd.ttc',
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make(path, title, subtitle, top_rgb, bottom_rgb):
    w, h = 1200, 800
    img = Image.new('RGB', (w, h), top_rgb)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        draw.line(
            [(0, y), (w, y)],
            fill=tuple(int(top_rgb[i] + (bottom_rgb[i] - top_rgb[i]) * t) for i in range(3)),
        )
    # 装饰网格
    for x in range(0, w, 80):
        draw.line([(x, 0), (x, h)], fill=(255, 255, 255, 20), width=1)
    for y in range(0, h, 80):
        draw.line([(0, y), (w, y)], fill=(255, 255, 255, 20), width=1)
    # 卡片式文字块
    draw.rounded_rectangle([90, 250, w - 90, 560], radius=28, fill=(255, 255, 255, 235))
    f1 = load_font(64)
    f2 = load_font(30)
    draw.text((140, 300), title, font=f1, fill=(26, 42, 74))
    draw.text((140, 396), subtitle, font=f2, fill=(90, 107, 136))
    draw.text((140, 460), '点击任意处关闭 · 左右键切换 · 滚轮缩放', font=f2, fill=(140, 155, 178))
    img.save(path)
    print('saved', path, os.path.getsize(path), 'bytes')


make(os.path.join(OUT_DIR, 'demo-img-1.png'),
     '申论 · 综合分析三步拆解', '配图 1／2：材料分层示意图', (37, 99, 235), (147, 197, 253))
make(os.path.join(OUT_DIR, 'demo-img-2.png'),
     '申论 · 综合分析三步拆解', '配图 2／2：答题结构对照表', (180, 83, 9), (253, 186, 116))
