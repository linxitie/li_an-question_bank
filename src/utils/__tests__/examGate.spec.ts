/**
 * 考试开关纯函数单测（P2，2026-11-09）。
 *
 * 只测"翻译层"：原因码 → 文案/色调、定时摘要、datetime-local 互转、今晚快速填。
 * 真正的判定在服务端 `exam/contract.py`（那边有 pytest 覆盖），前端不重复实现。
 */
import { describe, expect, it } from 'vitest';
import {
  examNowLine,
  examStatusLabel,
  examStatusTone,
  examSwitchEnabled,
  examSwitchHint,
  examSwitchVisible,
  examTimingText,
  fromDatetimeLocal,
  tonightWindow,
  toDatetimeLocal
} from '@/utils/examGate';
import type { LibraryExamState } from '@/modules/library/api';

const READY: LibraryExamState = {
  known: true,
  published: true,
  open: true,
  ready: true,
  reason: 'ready',
  open_at: null,
  close_at: null,
  question_count: 100,
  manual_open: 1,
  server_now: '2026-11-09 20:41:00'
};

describe('examStatusLabel / examStatusTone', () => {
  it('七个原因码各有中文标签', () => {
    expect(examStatusLabel(READY)).toBe('可进入');
    expect(examStatusLabel({ ...READY, reason: 'closed', ready: false })).toBe('已关闭');
    expect(examStatusLabel({ ...READY, reason: 'draft' })).toBe('未发布');
    expect(examStatusLabel({ ...READY, reason: 'no_questions' })).toBe('无题');
    expect(examStatusLabel({ ...READY, reason: 'not_started' })).toBe('未开始');
    expect(examStatusLabel({ ...READY, reason: 'expired' })).toBe('已结束');
    expect(examStatusLabel({ ...READY, known: false, reason: 'no_paper' })).toBe('未建卷');
  });
  it('没有状态块（老接口）按「未建卷」显示，不抛错', () => {
    expect(examStatusLabel(null)).toBe('未建卷');
    expect(examStatusLabel(undefined)).toBe('未建卷');
    expect(examStatusTone(null)).toBe('muted');
  });
  it('色调：可进入=ok，已关闭=danger，无题/未开始=warn', () => {
    expect(examStatusTone(READY)).toBe('ok');
    expect(examStatusTone({ ...READY, reason: 'closed' })).toBe('danger');
    expect(examStatusTone({ ...READY, reason: 'no_questions' })).toBe('warn');
    expect(examStatusTone({ ...READY, reason: 'not_started' })).toBe('warn');
  });
});

describe('examTimingText', () => {
  it('两端都有 → 20:00-22:00 定时', () => {
    expect(examTimingText({
      ...READY,
      open_at: '2026-11-09 20:00:00',
      close_at: '2026-11-09 22:00:00'
    })).toBe('20:00-22:00 定时');
  });
  it('只设一侧 → 起/止', () => {
    expect(examTimingText({ ...READY, open_at: '2026-11-09 08:00:00' })).toBe('08:00 起可考');
    expect(examTimingText({ ...READY, close_at: '2026-11-09 22:00:00' })).toBe('22:00 前可考');
  });
  it('没定时 → 手动开启；手动关掉 → 已手动关闭', () => {
    expect(examTimingText(READY)).toBe('手动开启');
    expect(examTimingText({ ...READY, manual_open: 0, open: false, ready: false, reason: 'closed' }))
      .toBe('已手动关闭');
  });
  it('0 题 / 未发布 / 未建卷 三态说清楚', () => {
    expect(examTimingText({ ...READY, question_count: 0 })).toBe('无题（0 题）不可开');
    expect(examTimingText({ ...READY, published: false })).toBe('资料未发布');
    expect(examTimingText({ ...READY, known: false })).toBe('未建可作答卷');
  });
});

describe('examSwitchVisible / examSwitchEnabled / examSwitchHint', () => {
  it('只有试卷 + 投放位含考试页才显示开关', () => {
    expect(examSwitchVisible({ type: 'paper', placement: 'exam' })).toBe(true);
    expect(examSwitchVisible({ type: 'paper', placement: 'both' })).toBe(true);
    expect(examSwitchVisible({ type: 'paper', placement: 'library' })).toBe(false);
    expect(examSwitchVisible({ type: 'lecture', placement: 'library' })).toBe(false);
    // placement 缺省（老接口没这个字段）按 both 兜底（与后端 normalize 一致）
    expect(examSwitchVisible({ type: 'paper' })).toBe(true);
  });
  it('0 题开关必须灰掉（打开也进不去）', () => {
    expect(examSwitchEnabled({ ...READY, question_count: 0 })).toBe(false);
    expect(examSwitchEnabled({ ...READY, known: false })).toBe(false);
    expect(examSwitchEnabled(READY)).toBe(true);
  });
  it('灰掉时给出可操作的原因', () => {
    expect(examSwitchHint({ ...READY, question_count: 0 })).toContain('0 题');
    expect(examSwitchHint({ ...READY, known: false })).toContain('建卷');
    expect(examSwitchHint(READY)).toContain('当前学生可以进入');
  });
});

describe('datetime-local 互转', () => {
  it('后端格式 → 输入框格式', () => {
    expect(toDatetimeLocal('2026-11-09 20:00:00')).toBe('2026-11-09T20:00');
    expect(toDatetimeLocal(null)).toBe('');
    expect(toDatetimeLocal('')).toBe('');
  });
  it('输入框格式 → 后端格式（空 = 不限，发 null）', () => {
    expect(fromDatetimeLocal('2026-11-09T20:00')).toBe('2026-11-09 20:00');
    expect(fromDatetimeLocal('')).toBeNull();
    expect(fromDatetimeLocal('  ')).toBeNull();
  });
  it('往返不丢信息', () => {
    const local = '2026-11-09T22:30';
    expect(toDatetimeLocal(fromDatetimeLocal(local))).toBe(local);
  });
});

describe('tonightWindow / examNowLine', () => {
  it('今晚 = 服务器日期 20:00–22:00', () => {
    expect(tonightWindow('2026-11-09 20:41:00')).toEqual({
      open: '2026-11-09T20:00',
      close: '2026-11-09T22:00'
    });
  });
  it('「当前」用服务器时间显示（避免浏览器时区误导）', () => {
    expect(examNowLine(READY)).toBe('当前：可进入（服务器时间 20:41）');
    expect(examNowLine({ ...READY, reason: 'closed', ready: false }))
      .toBe('当前：已关闭（服务器时间 20:41）');
    expect(examNowLine(null)).toBe('当前：还没有可作答卷');
  });
});
