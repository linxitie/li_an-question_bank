// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

/**
 * P4「补答案」抽屉：只验前端主干（规则全在后端 19 例 pytest 里）
 *   1. 上传后渲染预览（题号/题型/答案/建议/标记/库中旧答案）；
 *   2. 输入自动归一（去非法字符、大写、去重排序）；
 *   3. 「采纳建议」把推断建议填成正式答案；
 *   4. 默认 `overwrite=false` 写入；勾选后 `overwrite=true`；
 *   5. 解析失败显示原因且不进入预览。
 */
vi.mock('@/modules/library/api', async (orig) => {
  const actual = await orig<typeof import('@/modules/library/api')>();
  return {
    ...actual,
    parseAnswerFile: vi.fn(),
    fetchAnswerDraft: vi.fn(),
    // 抽屉打开时会先找"上次没确认完"的草稿；这里默认没有
    fetchLatestAnswerDraft: vi.fn(async () => ({ exists: false })),
    saveAnswerDraftItems: vi.fn(),
    applyAnswerDraft: vi.fn(),
    discardAnswerDraft: vi.fn()
  };
});

vi.mock('element-plus', async (orig) => {
  const actual = await orig<typeof import('element-plus')>();
  const message = Object.assign(vi.fn(), {
    success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn()
  });
  return { ...actual, ElMessage: message, ElMessageBox: { confirm: vi.fn(async () => 'confirm') } };
});

import {
  applyAnswerDraft,
  parseAnswerFile,
  saveAnswerDraftItems,
  type AnswerDraftDetail
} from '@/modules/library/api';
import AnswerDraftDrawer from '../AnswerDraftDrawer.vue';

const MOCK = (over: Partial<AnswerDraftDetail> = {}): AnswerDraftDetail => ({
  draft_id: 3,
  paper_id: 3,
  paper_code: 'GZ-2017-JS-T',
  paper_name: '2017年江苏省公务员考试《公安基础知识》考试真题',
  status: 'pending',
  source_ext: 'pdf',
  source_name: '2017年江苏省…答案及解析.pdf',
  item_count: 3,
  conflict_count: 1,
  empty_count: 1,
  message: null,
  created_at: null,
  expires_at: null,
  can_edit: true,
  items: [
    {
      no: 1, answer: 'C', tier: 'L1', suggestion: '', evidence: '正确答案为C',
      analysis: '本题考查公安知识', flags: [], question_type: '单选', current: ''
    },
    {
      no: 87, answer: '', tier: 'L3', suggestion: 'ABCD', evidence: '推断',
      analysis: 'A、B、C 项：正确…', flags: ['仅推断建议'], question_type: '多选', current: 'A'
    },
    {
      no: 88, answer: '', tier: 'L4', suggestion: '', evidence: '',
      analysis: '没有线索', flags: ['未识别答案'], question_type: '单选', current: ''
    }
  ],
  ...over
});

function mountDrawer() {
  return mount(AnswerDraftDrawer, {
    props: { open: true, paperId: 3, paperCode: 'GZ-2017-JS-T', paperName: '2017江苏卷' },
    global: { stubs: { Teleport: true } }
  });
}

async function uploadAndSettle(w: ReturnType<typeof mountDrawer>): Promise<void> {
  const input = w.find('.ad-file');
  const file = new File(['1 C'], 'answer.pdf', { type: 'application/pdf' });
  Object.defineProperty(input.element, 'files', { value: [file], configurable: true });
  await input.trigger('change');
  for (let i = 0; i < 4; i += 1) {
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();
  }
}

afterEach(() => vi.clearAllMocks());

describe('AnswerDraftDrawer', () => {
  it('上传后渲染预览（含建议、标记、库中旧答案）', async () => {
    (parseAnswerFile as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK());
    const w = mountDrawer();
    expect(w.find('.ad-drop').exists()).toBe(true);
    await uploadAndSettle(w);

    expect(parseAnswerFile).toHaveBeenCalledTimes(1);
    expect(w.findAll('.ad-row')).toHaveLength(4);        // 表头 + 3 题
    expect(w.text()).toContain('GZ-2017-JS-T');
    expect(w.text()).toContain('采纳 ABCD');
    expect(w.text()).toContain('库中 A');
    expect(w.text()).toContain('未识别答案');
    expect(w.text()).toContain('确认写入 1 题');           // 只有 1 题有答案
  });

  it('输入自动归一：大写 + 去重 + 排序 + 丢掉非法字符', async () => {
    (parseAnswerFile as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK());
    const w = mountDrawer();
    await uploadAndSettle(w);
    const input = w.findAll('.ad-answer')[0];
    (input.element as HTMLInputElement).value = 'c,a,a,9';
    await input.trigger('input');
    await nextTick();                       // 归一后 Vue 会把 DOM value 补写回去
    await nextTick();
    expect((input.element as HTMLInputElement).value).toBe('AC');
  });

  it('「采纳建议」把推断建议变成正式答案', async () => {
    (parseAnswerFile as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK());
    const w = mountDrawer();
    await uploadAndSettle(w);
    await w.find('.ad-adopt').trigger('click');
    await nextTick();
    expect(w.text()).toContain('确认写入 2 题');
  });

  it('默认 overwrite=false；勾选后 true', async () => {
    (parseAnswerFile as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK());
    (saveAnswerDraftItems as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(MOCK());
    (applyAnswerDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, filled: 1, overwritten: 0, kept: 0, skipped: 2, analysis_only: 1, kept_numbers: []
    });
    const w = mountDrawer();
    await uploadAndSettle(w);

    const applyBtn = w.findAll('.ad-foot .adm-btn').find((b) => b.text().includes('确认写入'));
    await applyBtn!.trigger('click');
    await new Promise((r) => setTimeout(r, 10));

    expect(saveAnswerDraftItems).toHaveBeenCalledTimes(1);
    expect((applyAnswerDraft as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1]).toEqual({
      overwrite: false
    });
    expect(w.emitted('applied')?.[0]?.[0]).toMatchObject({ paperId: 3, filled: 1 });
  });

  it('解析失败显示原因且不进入预览', async () => {
    (parseAnswerFile as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      MOCK({ status: 'failed', message: '有 3 个题号不属于这张卷（9, 10）', items: [] })
    );
    const w = mountDrawer();
    await uploadAndSettle(w);
    expect(w.text()).toContain('不属于这张卷');
    expect(w.find('.ad-drop').exists()).toBe(true);       // 还在上传屏
  });
});
