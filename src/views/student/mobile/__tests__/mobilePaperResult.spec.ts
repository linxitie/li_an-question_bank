// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';

/**
 * D6 手机结果页：钉住三件容易再次走偏的事。
 *
 * 1) 数字口径必须与 PC 结果页逐项相同（同一个 buildExamSummary）：
 *    得分率、正确/错误、已答/未答、答对率——这里用真机记录 4 的数据回放；
 * 2) 「错误」含未答，所以「已答 · 未答」那行必须同时渲染，否则 2+95+93 看起来对不上；
 * 3) 逐题回顾默认收起、点开后条数 = details 条数（97 条）。
 *
 * 真机证据见 docs/plans/assets/备考资料缺陷排查/15_真机_D6_手机结果页.png。
 */
const replace = vi.fn();
const push = vi.fn();
const back = vi.fn();

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { record_id: '4' } }),
  useRouter: () => ({ replace, push, back })
}));

vi.mock('@/utils/questionRender', () => ({
  renderQuestionContent: (html: string) => `<p class="stub-stem">${html}</p>`
}));

import MobilePaperResult from '../mobile_paper_result.vue';

/** 真机 record 4：97 题、作答 4 题、对 2 题、得 2 分、用时 17 秒 */
function recordPayload() {
  const answered = [
    { question_id: 1, is_correct: true, student_answer: 'D', correct_answer: 'D', question_content: '甲', answer_analysis: '解析1' },
    { question_id: 2, is_correct: true, student_answer: 'C', correct_answer: 'C', question_content: '乙', answer_analysis: '解析2' },
    { question_id: 3, is_correct: false, student_answer: 'A', correct_answer: 'B', question_content: '丙', answer_analysis: '解析3' },
    { question_id: 4, is_correct: false, student_answer: 'B', correct_answer: 'A', question_content: '丁', answer_analysis: '解析4' }
  ];
  const blank = Array.from({ length: 93 }, (_, i) => ({
    question_id: 100 + i,
    is_correct: null,
    student_answer: null,
    correct_answer: 'C',
    question_content: `未答题干${i + 1}`,
    answer_analysis: '解析'
  }));
  return {
    record_id: 4,
    paper_id: 5,
    paper_name: '2016江西招警考试《人民警察基础知识》真题（部分）',
    total_score: 2,
    max_score: 97,
    question_total: 97,
    answered_count: 4,
    duration_used: 17,
    manual_pending_count: 0,
    is_completed: true,
    details: [...answered, ...blank]
  };
}

function installAuth(payload: any) {
  const apiFetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => payload }));
  (window as any).__VTJ_AUTH__ = {
    apiFetch,
    getJsonHeaders: () => ({ 'Content-Type': 'application/json' })
  };
  return apiFetch;
}

async function mountPage() {
  const wrapper = mount(MobilePaperResult);
  await flushPromises();
  await flushPromises();
  return wrapper;
}

describe('mobile_paper_result.vue（D6 手机结果页）', () => {
  beforeEach(() => {
    replace.mockClear();
    push.mockClear();
    back.mockClear();
  });

  afterEach(() => {
    delete (window as any).__VTJ_AUTH__;
  });

  it('拉同一接口 GET /api/exams/records/{id}，并逐项复现 PC 口径', async () => {
    const apiFetch = installAuth(recordPayload());
    const wrapper = await mountPage();

    expect(apiFetch).toHaveBeenCalledWith('/api/exams/records/4', expect.anything());

    const text = wrapper.text();
    expect(text).toContain('考试结果');
    expect(wrapper.get('.score-num').text()).toBe('2');
    expect(wrapper.get('.score-max').text()).toBe('/ 97 分');
    expect(text).toContain('2.06%');      // 得分率 2 ÷ 97
    expect(text).toContain('00:17');      // 用时
    expect(text).toContain('2 / 95 题');  // 正确 / 错误（错误含未答）
    expect(text).toContain('50%');        // 答对率（按已答）2 ÷ 4
    expect(text).toContain('已答 4 / 97 题');
    expect(text).toContain('未答 93 题（未答按错计）');
  });

  it('逐题回顾默认收起，点开后条数 = details 条数', async () => {
    installAuth(recordPayload());
    const wrapper = await mountPage();

    expect(wrapper.findAll('.qitem')).toHaveLength(0);
    expect(wrapper.get('.review-head').text()).toContain('逐题回顾（97 题）');

    await wrapper.get('.review-head').trigger('click');
    const items = wrapper.findAll('.qitem');
    expect(items).toHaveLength(97);
    expect(items[0].text()).toContain('第 1 题');
    expect(items[0].text()).toContain('✓ 正确');
    expect(items[96].text()).toContain('第 97 题');
    expect(items[96].text()).toContain('未答');
  });

  it('接口失败时显示「加载失败（HTTP 500）」，不白屏', async () => {
    installAuth(recordPayload());
    (window as any).__VTJ_AUTH__.apiFetch = vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }));
    const wrapper = await mountPage();
    expect(wrapper.get('.state--error').text()).toBe('加载失败（HTTP 500）');
    expect(wrapper.findAll('.qitem')).toHaveLength(0);
  });

  it('三个动作按钮接到新路由', async () => {
    installAuth(recordPayload());
    const wrapper = await mountPage();

    const btns = wrapper.findAll('.actions .btn');
    expect(btns.map((b) => b.text())).toEqual(['再考一次', '查看错题', '回首页']);

    await btns[1].trigger('click');
    expect(push).toHaveBeenCalledWith('/mobile/wrong-questions');
    await btns[2].trigger('click');
    expect(push).toHaveBeenCalledWith('/mobile/home');
  });
});
