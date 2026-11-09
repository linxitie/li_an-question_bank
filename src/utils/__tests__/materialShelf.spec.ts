/**
 * 学生端「备考资料」纯函数单测（L2，2026-11-08）。
 * 覆盖：讲义摘要行、试卷元数据行、是否可考/原因、时长格式化、折叠规则。
 */
import { describe, expect, it } from 'vitest';
import {
  canExam,
  COLLAPSED,
  DEFAULT_MOBILE_TYPE,
  emptyTextOf,
  examHint,
  fmtDuration,
  groupShelfItems,
  lectureMetaLine,
  MOBILE_TYPE_TABS,
  normalizeTypeTab,
  paperMetaLine,
  visibleItems
} from '@/utils/materialShelf';
import type { LibraryMaterial, MaterialPaperMeta } from '@/modules/library/api';

const PAPER_OK: MaterialPaperMeta = {
  paper_code: 'GZ-2024-GK-T',
  year: 2024,
  region_name: '国考',
  region_code: 'GK',
  book_kind_label: '题本',
  volume: null,
  meta_label: '2024 · 国考 · 题本',
  exam_paper_id: 4,
  question_count: 100,
  total_score: 100,
  duration: 120,
  paper_type: 'PUBLISHED',
  answerable: true
};

describe('lectureMetaLine', () => {
  it('章节 + 字数都在时用 · 连接', () => {
    expect(lectureMetaLine({ chapter_count: 3, word_count: 9200 })).toBe('3 章 · 9200 字');
  });
  it('缺一项就只显示存在的', () => {
    expect(lectureMetaLine({ chapter_count: 0, word_count: 1200 })).toBe('1200 字');
    expect(lectureMetaLine({ chapter_count: 2, word_count: 0 })).toBe('2 章');
  });
  it('都没有返回空串（调用方不渲染该行）', () => {
    expect(lectureMetaLine({ chapter_count: null, word_count: null })).toBe('');
  });
});

describe('paperMetaLine', () => {
  it('完整元数据按「年份·地区·卷别 ｜ 题量·分值·时长 ｜ 编号」拼', () => {
    expect(paperMetaLine({ paper: PAPER_OK })).toBe(
      '2024 · 国考 · 题本 ｜ 100 题 · 100 分 · 120 分钟 ｜ GZ-2024-GK-T'
    );
  });
  it('缺项显示 — 而不是空白', () => {
    const p: MaterialPaperMeta = { ...PAPER_OK, year: null, region_name: null, duration: null };
    expect(paperMetaLine({ paper: p })).toContain('— · — · 题本');
    // 缺时长时只留一个 —（不带单位，避免出现「— 分钟」这种半截话）
    expect(paperMetaLine({ paper: p })).toContain('100 题 · 100 分 · —');
  });
  it('没有 paper 区块时提示元数据待补', () => {
    expect(paperMetaLine({ paper: null })).toBe('元数据待补');
  });
});

describe('canExam / examHint', () => {
  it('卷已发布且投放位含考试页 → 可考', () => {
    expect(canExam({ paper: PAPER_OK, placement: 'both' })).toBe(true);
    expect(canExam({ paper: PAPER_OK, placement: 'exam' })).toBe(true);
  });
  it('投放位=仅资料页 → 不可考（即便卷字段是 PUBLISHED）', () => {
    expect(canExam({ paper: PAPER_OK, placement: 'library' })).toBe(false);
    expect(examHint({ paper: PAPER_OK, placement: 'library' })).toContain('仅资料页');
  });
  it('没建卷 / 卷里没题 各有明确原因', () => {
    const noPaper = { ...PAPER_OK, exam_paper_id: null, answerable: false };
    expect(canExam({ paper: noPaper, placement: 'both' })).toBe(false);
    expect(examHint({ paper: noPaper, placement: 'both' })).toContain('还没建可作答卷');

    const noQuestion = { ...PAPER_OK, question_count: 0, answerable: false };
    expect(examHint({ paper: noQuestion, placement: 'both' })).toContain('还没有题目');
  });
  it('未发布 → 说明是未发布', () => {
    const draft = { ...PAPER_OK, answerable: false, paper_type: 'DRAFT' };
    expect(examHint({ paper: draft, placement: 'both' })).toContain('未发布');
  });
});

describe('fmtDuration', () => {
  it('秒 → 分钟/小时', () => {
    expect(fmtDuration(0)).toBe('时长未知');
    expect(fmtDuration(90)).toBe('1 分钟');
    expect(fmtDuration(3900)).toBe('1 小时 5 分');
  });
});

describe('visibleItems', () => {
  it('折叠时只给前 4 条，展开给全部', () => {
    const arr = Array.from({ length: 6 }, (_, i) => i);
    expect(visibleItems(arr, true)).toHaveLength(COLLAPSED);
    expect(visibleItems(arr, false)).toHaveLength(6);
  });
});

describe('groupShelfItems（手机端分组）', () => {
  it('讲义 / 试卷 / 其余 三分，且保持原顺序', () => {
    const items = [
      { id: 1, type: 'article' },
      { id: 2, type: 'lecture' },
      { id: 3, type: 'paper' },
      { id: 4, type: 'card' },
      { id: 5, type: 'lecture' }
    ];
    const g = groupShelfItems(items as any[]);
    expect(g.lectures.map((x) => x.id)).toEqual([2, 5]);
    expect(g.papers.map((x) => x.id)).toEqual([3]);
    expect(g.rest.map((x) => x.id)).toEqual([1, 4]);
  });
  it('空输入不炸，三组都是空数组', () => {
    const g = groupShelfItems([] as any[]);
    expect(g.lectures).toEqual([]);
    expect(g.papers).toEqual([]);
    expect(g.rest).toEqual([]);
  });
  it('视频/卡片不会被误分到讲义或试卷', () => {
    const g = groupShelfItems([
      { id: 1, type: 'video_intro' },
      { id: 2, type: 'video_advanced' },
      { id: 3, type: 'card' }
    ] as any[]);
    expect(g.lectures).toHaveLength(0);
    expect(g.papers).toHaveLength(0);
    expect(g.rest).toHaveLength(3);
  });
});

describe('手机端二级 tab（B-M1）', () => {
  it('tab 顺序 = 讲义/文章/卡片/试卷（用户指定）', () => {
    expect(MOBILE_TYPE_TABS.map((t) => t.label)).toEqual(['讲义', '文章', '卡片', '试卷']);
    expect(MOBILE_TYPE_TABS.map((t) => t.key)).toEqual(['lecture', 'article', 'card', 'paper']);
  });
  it('深链参数：合法值原样返回，非法/空回落默认 tab', () => {
    expect(normalizeTypeTab('paper')).toBe('paper');
    expect(normalizeTypeTab('lecture')).toBe('lecture');
    expect(normalizeTypeTab('video_intro')).toBe(DEFAULT_MOBILE_TYPE);
    expect(normalizeTypeTab('')).toBe(DEFAULT_MOBILE_TYPE);
    expect(normalizeTypeTab(null)).toBe(DEFAULT_MOBILE_TYPE);
  });
  it('空态文案带科目与类型，且大字是「无资料」', () => {
    expect(emptyTextOf('gongzhuan', 'lecture')).toEqual({
      title: '无资料',
      hint: '公专还没有「讲义」资料'
    });
    expect(emptyTextOf('xingce', 'paper').hint).toBe('行测还没有「试卷」资料');
    expect(emptyTextOf('shenlun', 'article').hint).toBe('申论还没有「文章」资料');
  });
});

// 仅用于让类型参与检查：LibraryMaterial 至少要有这两个字段才能传给上面的函数
const _typecheck: Pick<LibraryMaterial, 'chapter_count' | 'word_count'> = {
  chapter_count: 1,
  word_count: 2
};
void _typecheck;
