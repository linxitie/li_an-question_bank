import { describe, expect, it } from 'vitest';
import { buildSteps, initialAnswers } from '../pool';

/**
 * 画像动态问题池（模块7 P1）
 * 锁住三件事：
 *   1) 结构稳定：6 个维度、每维至少 1 题
 *   2) 轮换生效：不同 seed 给出的问法不同（用户反馈过「问题单一」）
 *   3) 提交安全：题目的 key 只能落在后端 UserProfile 已有字段上，不能造新字段
 */
const ALLOWED_KEYS = new Set([
  'grade',
  'exam_date',
  'target_score',
  'daily_hours',
  'self_level',
  'subject_weaknesses',
  'subject_strengths',
  'target_region',
  'target_post',
  'self_intro',
]);

describe('profile-quiz pool', () => {
  it('返回 6 个维度步骤', () => {
    const steps = buildSteps({ seed: 'fixed' });
    expect(steps).toHaveLength(6);
    expect(steps.map((s) => s.dimension)).toEqual([
      'basic',
      'target',
      'level',
      'weakness',
      'habit',
      'self',
    ]);
  });

  it('每一步都有标题与至少一个字段', () => {
    const steps = buildSteps({ seed: 'fixed' });
    for (const step of steps) {
      expect(step.title.length).toBeGreaterThan(0);
      expect(step.fields.length).toBeGreaterThan(0);
    }
  });

  it('不同 seed 会换问法（动态变换生效）', () => {
    const a = buildSteps({ seed: 'seed-a' }).map((s) => s.fields.map((f) => f.label).join('|'));
    const b = buildSteps({ seed: 'seed-b' }).map((s) => s.fields.map((f) => f.label).join('|'));
    expect(a.join('##')).not.toBe(b.join('##'));
  });

  it('同一 seed 结果稳定（可复现）', () => {
    const a = buildSteps({ seed: 'same' }).map((s) => s.fields.map((f) => f.key).join(','));
    const b = buildSteps({ seed: 'same' }).map((s) => s.fields.map((f) => f.key).join(','));
    expect(a).toEqual(b);
  });

  it('所有字段 key 都在后端允许集合内（零后端改动的前提）', () => {
    for (const seed of ['s1', 's2', 's3', 's4', 's5']) {
      for (const step of buildSteps({ seed })) {
        for (const field of step.fields) {
          expect(ALLOWED_KEYS.has(field.key)).toBe(true);
        }
      }
    }
  });

  it('同一维度内不出现重复字段', () => {
    for (const seed of ['x', 'y', 'z']) {
      for (const step of buildSteps({ seed })) {
        const keys = step.fields.map((f) => f.key);
        expect(new Set(keys).size).toBe(keys.length);
      }
    }
  });

  it('自述题始终是长文本类型', () => {
    const steps = buildSteps({ seed: 'self-check' });
    const selfStep = steps.find((s) => s.dimension === 'self');
    expect(selfStep).toBeTruthy();
    const intro = selfStep!.fields.find((f) => f.key === 'self_intro');
    expect(intro?.type).toBe('textarea');
  });

  it('initialAnswers 为每题给出正确初值', () => {
    const steps = buildSteps({ seed: 'init' });
    const answers = initialAnswers(steps);
    for (const step of steps) {
      for (const field of step.fields) {
        const value = answers[field.key];
        if (field.type === 'multi') expect(Array.isArray(value)).toBe(true);
        else if (field.type === 'slider') expect(typeof value).toBe('number');
        else expect(value).toBe('');
      }
    }
  });
});
