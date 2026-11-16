// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

/**
 * Q3/Q4（2026-11-15，导题缺号定位）：抽屉里的缺号 chips + 原卷页弹窗。
 *
 * 只验三条主干（后端错误码/渲染细节在 `backend/tests/test_draft_page_image.py` 9 例里）：
 *   1. 有定位信息 → chips 可点，点开发请求、弹窗里出现 `data:image/png;base64,` 图；
 *   2. 旧草稿（`qno_gaps_available=false`）→ **不发请求**，只提示重新导题；
 *   3. docx 草稿 → 不渲染 chips（原文照旧）。
 */
vi.mock('@/modules/library/api', async (orig) => {
  const actual = await orig<typeof import('@/modules/library/api')>();
  return {
    ...actual,
    fetchParseDraft: vi.fn(),
    fetchDraftPageImage: vi.fn(),
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
  return { ...actual, ElMessage: message, ElMessageBox: { confirm: vi.fn(async () => 'confirm') } };
});

import {
  fetchDraftPageImage,
  fetchParseDraft,
  type ParseDraftDetail
} from '@/modules/library/api';
import ParseDraftDrawer from '../ParseDraftDrawer.vue';

const MISSING = '题号缺号 3 个：[46, 86, 92]';

function detail(over: Partial<ParseDraftDetail> = {}): ParseDraftDetail {
  return {
    draft_id: 11,
    material_id: 128,
    paper_id: 5,
    status: 'pending',
    source_ext: 'pdf',
    item_count: 1,
    message: null,
    created_at: '2026-11-15 20:00:00',
    expires_at: '2026-12-15 20:00:00',
    title: '2025多省联考公安《公安专业》',
    paper_code: 'GZ-2025-LK-T',
    warnings: [
      '这是扫描件 OCR 出来的文字草稿：没有原图，公式/表格/双栏可能错位，请逐题核对',
      MISSING
    ],
    can_edit: true,
    qno_gaps_available: true,
    items: [
      {
        no: 1,
        type: '单选',
        stem: '题干（　　）。',
        options: { A: '甲', B: '乙', C: '丙', D: '丁' },
        shared: '',
        section: 0,
        images: [],
        flags: []
      }
    ],
    ...over
  };
}

function pageImage(no = 46, extra: Record<string, unknown> = {}) {
  return {
    ok: true,
    no,
    page: 16,
    alt_page: 0,
    on_alt_page: false,
    page_count: 41,
    dpi: 150,
    image_w: 1240,
    image_h: 1754,
    image_b64: 'iVBORw0KGgoAAAANSUhEUg==',
    highlight: { x0: 0, y0: 0.6, x1: 0.86, y1: 0.63 },
    file_name: '2025多省联考公安《公安专业》.pdf',
    hint: `第 ${no} 题`,
    ...extra
  };
}

async function mountAndSettle(over: Partial<ParseDraftDetail> = {}) {
  (fetchParseDraft as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(detail(over));
  const w = mount(ParseDraftDrawer, {
    props: { open: true, draftId: 11, materialId: 128 },
    global: { stubs: { Teleport: true } }
  });
  await new Promise((r) => setTimeout(r, 0));
  await nextTick();
  return w;
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('ParseDraftDrawer · 缺号定位', () => {
  it('缺号告警渲染成三个 chip，点「46」会取原卷页并显示图', async () => {
    (fetchDraftPageImage as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(pageImage(46));
    const w = await mountAndSettle();

    const chips = w.findAll('.pd-qno');
    expect(chips.map((c) => c.text())).toEqual(['46', '86', '92']);

    await chips[0].trigger('click');
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();

    expect(fetchDraftPageImage).toHaveBeenCalledWith(11, 46, 150, undefined);
    const img = w.find('.qd-imgwrap img');
    expect(img.exists()).toBe(true);
    expect(img.attributes('src')).toMatch(/^data:image\/png;base64,/);
    expect(w.find('.qd-hl').exists()).toBe(true);
    expect(w.text()).toContain('原卷第 16 页');
  });

  it('旧草稿（qno_gaps_available=false）点 chip 不发请求，只提示重新导题', async () => {
    const w = await mountAndSettle({ qno_gaps_available: false });
    const chip = w.find('.pd-qno');
    expect(chip.classes()).toContain('pd-qno--cold');

    await chip.trigger('click');
    await new Promise((r) => setTimeout(r, 0));

    expect(fetchDraftPageImage).not.toHaveBeenCalled();
    expect(w.find('.qd-root').exists()).toBe(false);
    expect(w.text()).toContain('重新导题后可用');
  });

  it('docx 草稿不渲染 chip（题号以纯文本列出）', async () => {
    const w = await mountAndSettle({ source_ext: 'docx' });
    expect(w.findAll('.pd-qno')).toHaveLength(0);
    // docx 分支把题号拼成纯文本（点击没意义），但仍要让管理员看到缺了哪几题
    expect(w.text()).toContain('题号缺号 3 个：46、86、92');
  });

  it('上一题/下一题在缺号列表里循环', async () => {
    (fetchDraftPageImage as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(pageImage(46));
    const w = await mountAndSettle();

    await w.findAll('.pd-qno')[0].trigger('click');
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();

    const next = w.findAll('.qd-foot button').find((b) => b.text() === '下一题');
    expect(next).toBeTruthy();
    (fetchDraftPageImage as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(pageImage(86));
    await next!.trigger('click');
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();
    expect(fetchDraftPageImage).toHaveBeenLastCalledWith(11, 86, 150, undefined);
  });

  it('跨页缺口能一键翻到备选页（第 86 题那种"在下一页"的情况）', async () => {
    (fetchDraftPageImage as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(pageImage(46, { page: 16, alt_page: 17 }))
      .mockResolvedValueOnce(pageImage(46, { page: 17, alt_page: 16, on_alt_page: true }));
    const w = await mountAndSettle();

    await w.findAll('.pd-qno')[0].trigger('click');
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();

    const flip = w.findAll('.qd-foot button').find((b) => b.text() === '看第 17 页');
    expect(flip).toBeTruthy();
    await flip!.trigger('click');
    await new Promise((r) => setTimeout(r, 0));
    await nextTick();
    expect(fetchDraftPageImage).toHaveBeenLastCalledWith(11, 46, 150, 17);
  });
});
