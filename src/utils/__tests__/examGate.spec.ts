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
  examSwitchOn,
  examSwitchVisible,
  examTimingText,
  fromDatetimeLocal,
  mergeExamState,
  nextExamOpen,
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

/**
 * 2026-11-12 事故回归：写端点回包缺 `manual_open` 时，
 * 开关必须不能"显示开却已关闭"，更不能永远发关闭（再也打不开）。
 */
describe('examSwitchOn / nextExamOpen（缺字段兜底）', () => {
  it('manual_open 有值时以它为准', () => {
    expect(examSwitchOn(READY)).toBe(true);
    expect(examSwitchOn({ ...READY, manual_open: 0 })).toBe(false);
  });
  it('manual_open 缺失时按 reason 兜底（只有 closed 判关）', () => {
    const noField = { ...READY } as Partial<LibraryExamState>;
    delete noField.manual_open;
    expect(examSwitchOn({ ...(noField as LibraryExamState), reason: 'closed', ready: false })).toBe(false);
    expect(examSwitchOn({ ...(noField as LibraryExamState), reason: 'ready' })).toBe(true);
    expect(examSwitchOn({ ...(noField as LibraryExamState), reason: 'not_started' })).toBe(true);
  });
  it('没有状态块按"关"处理（开关本来也会被灰掉）', () => {
    expect(examSwitchOn(null)).toBe(false);
    expect(examSwitchOn({ ...READY, known: false })).toBe(false);
  });
  it('下一次点击 = 取反：关着能打开、开着能关闭', () => {
    expect(nextExamOpen({ ...READY, manual_open: 0, reason: 'closed' })).toBe(true);
    expect(nextExamOpen(READY)).toBe(false);
    const noField = { ...READY } as Partial<LibraryExamState>;
    delete noField.manual_open;
    // 事故现场：reason=closed 但没有 manual_open —— 必须能"再次打开"
    expect(nextExamOpen({ ...(noField as LibraryExamState), reason: 'closed' })).toBe(true);
  });
});

describe('mergeExamState（写回不丢字段）', () => {
  it('保留列表行里的 paper_code/paper_id，只覆盖回包里的字段', () => {
    const prev = { ...READY, paper_code: 'GZ-2016-JX-T', paper_id: 5 };
    const next = { ...READY, manual_open: 0, open: false, ready: false, reason: 'closed' } as LibraryExamState;
    delete (next as Partial<LibraryExamState>).paper_code;
    delete (next as Partial<LibraryExamState>).paper_id;
    const merged = mergeExamState(prev, next, false);
    expect(merged?.paper_code).toBe('GZ-2016-JX-T');
    expect(merged?.paper_id).toBe(5);
    expect(merged?.manual_open).toBe(0);
  });
  it('回包缺 manual_open 时用本次意图补齐（最后一道保险）', () => {
    const prev = { ...READY };
    const partial = { ...READY, open: false, ready: false, reason: 'closed' } as LibraryExamState;
    delete (partial as Partial<LibraryExamState>).manual_open;
    expect(mergeExamState(prev, partial, false)?.manual_open).toBe(0);
    expect(mergeExamState(prev, partial)?.manual_open).toBe(0);   // 没给意图时按 reason 兜底
  });
  it('服务端给了值就听服务端的（不被 fallback 覆盖）', () => {
    const partial = { ...READY, manual_open: 1 } as LibraryExamState;
    expect(mergeExamState({ ...READY, manual_open: 0 }, partial, false)?.manual_open).toBe(1);
  });
  it('回包为空时保留原行', () => {
    expect(mergeExamState(READY, null)).toEqual(READY);
    expect(mergeExamState(null, null)).toBeNull();
  });
});
