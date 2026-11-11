import { describe, expect, it } from 'vitest';
import { buildExamSummary, formatDuration, percent2, pickLatestProgress } from '../examSummary';

/**
 * 口径单测（2026-11-11 用户真机验收发现"2/97 显示成 2%、正确/错误 97/0"后补）。
 * 数值取自真实的 record #3：97 题、答 2 题且全对、其余空白按错计。
 */
describe('examSummary · 得分率口径', () => {
  it('2 / 97 必须保留两位小数（2.06%），不能取整成 2%', () => {
    expect(percent2(2, 97)).toBe(2.06);
    const s = buildExamSummary({
      score: 2, maxScore: 97, correct: 2, wrong: 95, unanswered: 95,
      total: 97, answered: 2, seconds: 139
    });
    expect(s.rateText).toBe('2.06%');
    expect(s.rateRatioText).toBe('2 ÷ 97');
  });

  it('正确/错误 = 答对 / (总题数 - 答对)，空白算"错"（学生视角）', () => {
    const s = buildExamSummary({
      score: 2, maxScore: 97, correct: 2, wrong: 0, unanswered: 95,
      total: 97, answered: 2
    });
    expect(s.correctText).toBe('2');
    expect(s.wrongText).toBe('95');   // 不用后端 wrong_count(0)，否则显示 2/0
    expect(s.answeredText).toBe('2 / 97');
    expect(s.unansweredText).toBe('95');
  });

  it('答对率按"已答"算，与得分率分开（2/2 = 100%）', () => {
    const s = buildExamSummary({
      score: 2, maxScore: 97, correct: 2, wrong: 0, unanswered: 95,
      total: 97, answered: 2
    });
    expect(s.accuracyAnsweredText).toBe('100%');
  });

  it('得分与满分原样展示，不再 `|| 100` 兜底', () => {
    const s = buildExamSummary({
      score: 0, maxScore: 97, correct: 0, wrong: 97, unanswered: 97,
      total: 97, answered: 0
    });
    expect(s.scoreText).toBe('0 / 97');
  });

  it('满分缺失时显示 0 而不是 100', () => {
    const s = buildExamSummary({
      score: 0, maxScore: 0, correct: 0, wrong: 0, unanswered: 0,
      total: 0, answered: 0
    });
    expect(s.scoreText).toBe('0 / 0');
    expect(s.rateText).toBe('0%');
    expect(s.accuracyAnsweredText).toBe('—');
  });

  it('有待人工评分时给出提示文案', () => {
    const s = buildExamSummary({
      score: 5, maxScore: 10, correct: 5, wrong: 4, unanswered: 0,
      total: 9, answered: 9, manualPending: 2
    });
    expect(s.pendingText).toContain('2 题待人工评分');
  });
});

describe('examSummary · 用时格式化', () => {
  it('秒/分/时三档', () => {
    expect(formatDuration(9)).toBe('00:09');
    expect(formatDuration(139)).toBe('02:19');
    expect(formatDuration(3725)).toBe('01:02:05');
    expect(formatDuration(null)).toBe('00:00');
  });

  it('结果页用的 timeText 与库里 duration_used 一致（服务端口径）', () => {
    const s = buildExamSummary({
      score: 2, maxScore: 97, correct: 2, wrong: 95, unanswered: 95,
      total: 97, answered: 2, seconds: 139
    });
    expect(s.timeText).toBe('02:19');
  });
});

/**
 * 试卷列表「我的得分」取哪一条（2026-11-11 用户复测发现：
 * 刚考完 2 分，卡片仍显示 0 / 97 —— 旧的 0 分记录把新的盖掉了）。
 */
describe('examSummary · 每套卷取最近一次已完成成绩', () => {
  it('接口按时间倒序返回时，不能被最老那条覆盖', () => {
    const progress = pickLatestProgress([
      { paper_id: 5, record_id: 3, is_completed: 1, total_score: 2 },
      { paper_id: 5, record_id: 2, is_completed: 1, total_score: 2 },
      { paper_id: 5, record_id: 1, is_completed: 1, total_score: 0 },
    ]);
    expect(progress['5'].score).toBe(2);
    expect(progress['5'].recordId).toBe(3);
  });

  it('未完成的记录不能盖掉已完成的成绩', () => {
    const progress = pickLatestProgress([
      { paper_id: 5, record_id: 9, is_completed: 0, total_score: 0 },
      { paper_id: 5, record_id: 4, is_completed: 1, total_score: 7 },
    ]);
    expect(progress['5'].score).toBe(7);
    expect(progress['5'].completed).toBe(true);
  });

  it('全是未完成时取最新的一条（显示"进行中"）', () => {
    const progress = pickLatestProgress([
      { paper_id: 5, record_id: 9, is_completed: 0, total_score: 0 },
      { paper_id: 5, record_id: 8, is_completed: 0, total_score: 0 },
    ]);
    expect(progress['5'].recordId).toBe(9);
    expect(progress['5'].completed).toBe(false);
  });

  it('多套卷互不干扰', () => {
    const progress = pickLatestProgress([
      { paper_id: 2, record_id: 1, is_completed: 1, total_score: 88 },
      { paper_id: 5, record_id: 3, is_completed: 1, total_score: 2 },
    ]);
    expect(progress['2'].score).toBe(88);
    expect(progress['5'].score).toBe(2);
  });
});
