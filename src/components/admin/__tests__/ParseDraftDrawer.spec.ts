// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

/**
 * P3「导题确认」抽屉：只验四条主干（细节规则全在后端 pytest 23 例里）
 *   1. 打开会拉草稿并按题渲染（题号/题型/选项/标记）；
 *   2. 「只看有标记的」过滤；
 *   3. 删掉一题后保存，提交的 items 少了那一题；
 *   4. 卷里已有题（后端 409 含「已有」）→ 二次确认后带 replace=true 重试。
 *
 * 为什么不测后端校验：题号重复/题干为空/题型非法都是服务端 400，前端只负责把错误弹出来，
 * 在这里复制一份规则等于两处实现，迟早漂移。
 */
vi.mock('@/modules/library/api', async (orig) => {
  const actual = await orig<typeof import('@/modules/library/api')>();
  return {
    ...actual,
    fetchParseDraft: vi.fn(),
    saveParseDraftItems: vi.fn(),
    confirmParseDraft: vi.fn(),
    discardParseDraft: vi.fn()
  };
});

vi.mock('element-plus', async (orig) => {
  const actual = await orig<typeof import('element-plus')>();
  const message = Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn()
  });
  return {
    ...actual,
    ElMessage: message,
    ElMessageBox: { confirm: vi.fn(async () => 'confirm') }
  };
});

import {
  confirmParseDraft,
  fetchParseDraft,
  saveParseDraftItems,
  type ParseDraftDetail
} from '@/modules/library/api';
import ParseDraftDrawer from '../ParseDraftDrawer.vue';

function detail(over: Partial<ParseDraftDetail> = {}): ParseDraftDetail {
  return {
    draft_id: 11,
    material_id: 128,
    paper_id: 5,
    status: 'pending',
    source_ext: 'docx',
    item_count: 2,
    message: null,
    created_at: '2026-11-09 16:00:00',
    expires_at: '2026-12-09 16:00:00',
    title: '2016江西招警考试《人民警察基础知识》真题（部分）',
    paper_code: 'GZ-2016-JX-T',
    warnings: [],
    can_edit: true,
    items: [
      {
        no: 1,
        type: '单选',
        stem: '所谓法的渊源是指（　　）。',
        options: { A: '宪法的表现形式', B: '行政法', C: '民法', D: '税法' },
        shared: '',
        section: 0,
        images: [],
        flags: []
      },
      {
        no: 2,
        type: '多选',
        stem: '人民警察的纪律包括（　　）。',
        options: { A: '政治纪律', B: '组织纪律', C: '执法纪律', D: '保密纪律' },
        shared: '某市发生一起盗窃案。',
        section: 1,
        images: [{ name: 'docx_1.jpeg', width: 592, height: 201 }],
        flags: ['有图待核对']
      }
    ],
    ...over
  };
}

function mountDrawer(props: Record<string, unknown> = {}) {
  return mount(ParseDraftDrawer, {
    props: { open: true, draftId: 11, materialId: 128, ...props },
    global: { stubs: { Teleport: true } }
  });
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('ParseDraftDrawer', () => {
  it('渲染题号/题型/选项/标记与体检提示', async () => {
    (fetchParseDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      detail({ warnings: ['依赖图/表 1 题（确认前请核对图片是否抽到）：[2]'] })
    );
    const w = mountDrawer();
    await nextTick();
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();

    expect(fetchParseDraft).toHaveBeenCalledWith(11);
    const html = w.text();
    expect(html).toContain('GZ-2016-JX-T');
    // 题干在 <textarea> 里，`w.text()` 取不到；直接读控件值
    const stems = w.findAll('.pd-stem').map((el) => (el.element as HTMLTextAreaElement).value);
    expect(stems[0]).toContain('所谓法的渊源');
    expect(html).toContain('某市发生一起盗窃案');     // 情境材料
    expect(html).toContain('有图待核对');
    expect(html).toContain('docx_1.jpeg');
    expect(html).toContain('依赖图/表 1 题');
    expect(w.findAll('.pd-item')).toHaveLength(2);
  });

  it('「只看有标记的」只留 flagged 题', async () => {
    (fetchParseDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(detail());
    const w = mountDrawer();
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();
    expect(w.findAll('.pd-item')).toHaveLength(2);

    await w.find('.pd-check input').setValue(true);
    await nextTick();
    expect(w.findAll('.pd-item')).toHaveLength(1);
    const stems = w.findAll('.pd-stem').map((el) => (el.element as HTMLTextAreaElement).value);
    expect(stems).toHaveLength(1);
    expect(stems[0]).toContain('人民警察的纪律');
  });

  it('删一题后保存，提交的 items 少一题', async () => {
    (fetchParseDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(detail());
    (saveParseDraftItems as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(detail());
    const w = mountDrawer();
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();

    await w.findAll('.pd-del')[0].trigger('click');
    await nextTick();
    expect(w.findAll('.pd-item')).toHaveLength(1);

    const saveBtn = w.findAll('.pd-foot .adm-btn').find((b) => b.text().includes('保存修改'));
    await saveBtn!.trigger('click');
    await new Promise((r) => setTimeout(r, 0));

    expect(saveParseDraftItems).toHaveBeenCalledTimes(1);
    const [draftId, items] = (saveParseDraftItems as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(draftId).toBe(11);
    expect(items).toHaveLength(1);
    expect(items[0].no).toBe(2);
  });

  it('卷里已有题 → 二次确认后带 replace=true 重试', async () => {
    (fetchParseDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(detail());
    (saveParseDraftItems as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(detail());
    (confirmParseDraft as unknown as ReturnType<typeof vi.fn>)
      .mockRejectedValueOnce(new Error('这张卷已有 100 道题；要重新导入请勾选「覆盖已有题目」'))
      .mockResolvedValueOnce({ ok: true, paper_id: 5, created: 2, replaced: 100, question_ids: [1, 2] });

    const w = mountDrawer();
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();

    const confirmBtn = w.findAll('.pd-foot .adm-btn').find((b) => b.text().includes('确认入库'));
    await confirmBtn!.trigger('click');
    await new Promise((r) => setTimeout(r, 10));

    expect(confirmParseDraft).toHaveBeenCalledTimes(2);
    expect((confirmParseDraft as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1]).toEqual({});
    expect((confirmParseDraft as unknown as ReturnType<typeof vi.fn>).mock.calls[1][1]).toEqual({
      replace: true
    });
    expect(w.emitted('confirmed')?.[0]?.[0]).toMatchObject({ draftId: 11, created: 2 });
  });

  it('解析失败的草稿显示原因且不让编辑', async () => {
    (fetchParseDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      detail({ status: 'failed', can_edit: false, items: [], message: '没有拆出题目' })
    );
    const w = mountDrawer();
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();
    expect(w.text()).toContain('没有拆出题目');
    const confirmBtn = w.findAll('.pd-foot .adm-btn').find((b) => b.text().includes('确认入库'));
    expect(confirmBtn!.attributes('disabled')).toBeDefined();
  });
});
