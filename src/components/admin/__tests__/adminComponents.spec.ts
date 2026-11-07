// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import AdminTag from '../AdminTag.vue';
import AdminStatCard from '../AdminStatCard.vue';
import AdminPageHeader from '../AdminPageHeader.vue';
import AdminToolbar from '../AdminToolbar.vue';
import AdminTable from '../AdminTable.vue';
import AdminFormItem from '../AdminFormItem.vue';

/**
 * A0 组件库的契约测试。
 *
 * 只测"渲染契约"（类名 / 文案 / 插槽 / 空值 / 语义色），不测像素：
 * 像素由 E1/E2 的走查截图负责（`/admin/dev/style` 是唯一基准页）。
 */

describe('AdminTag', () => {
  it('type 映射到资料类型类名，内容是中文名', () => {
    const w = mount(AdminTag, { props: { type: 'paper' }, slots: { default: '试卷' } });
    expect(w.classes()).toContain('is-type-paper');
    expect(w.text()).toBe('试卷');
  });

  it('tone 映射到状态类名，支持 text 传文案', () => {
    const w = mount(AdminTag, { props: { tone: 'ok', text: '已上架' } });
    expect(w.classes()).toContain('is-tone-ok');
    expect(w.text()).toBe('已上架');
  });

  it('都不传时只有基础类（不误染语义色）', () => {
    const w = mount(AdminTag, { slots: { default: '纯文本' } });
    expect(w.classes()).toEqual(['adm-tag']);
  });

  it('6 类资料都有独立类名（讲义/试卷是新类型）', () => {
    for (const t of ['video_intro', 'video_advanced', 'article', 'card', 'lecture', 'paper'] as const) {
      const w = mount(AdminTag, { props: { type: t }, slots: { default: t } });
      expect(w.classes()).toContain(`is-type-${t}`);
    }
  });
});

describe('AdminStatCard', () => {
  it('渲染数值 + 标签', () => {
    const w = mount(AdminStatCard, { props: { label: '总资料数', value: 119 } });
    expect(w.find('.adm-stat__value').text()).toBe('119');
    expect(w.find('.adm-stat__label').text()).toBe('总资料数');
  });

  it('千分位（1199 → 1,199）', () => {
    const w = mount(AdminStatCard, { props: { label: 'x', value: 1199 } });
    expect(w.find('.adm-stat__value').text()).toBe('1,199');
  });

  it('空值显示 —，不假装是 0', () => {
    for (const v of [null, undefined, ''] as const) {
      const w = mount(AdminStatCard, { props: { label: 'x', value: v as never } });
      expect(w.find('.adm-stat__value').text()).toBe('—');
    }
  });

  it('E3 裁定：保留 emoji 图标；不传 icon 就不占位', () => {
    const withIcon = mount(AdminStatCard, { props: { label: '试卷', value: 3, icon: '📄' } });
    expect(withIcon.find('.adm-stat__icon').text()).toBe('📄');
    const noIcon = mount(AdminStatCard, { props: { label: '试卷', value: 3 } });
    expect(noIcon.find('.adm-stat__icon').exists()).toBe(false);
  });

  it('语义色只挂在数值上', () => {
    const w = mount(AdminStatCard, { props: { label: '待补全', value: 1, tone: 'danger' } });
    expect(w.classes()).toContain('is-tone-danger');
  });
});

describe('AdminPageHeader', () => {
  it('标题 + 说明 + 操作插槽', () => {
    const w = mount(AdminPageHeader, {
      props: { title: '画风组件库', desc: 'A0 基座' },
      slots: { actions: '<button class="adm-btn">刷新</button>' }
    });
    expect(w.find('.adm-ph__title').text()).toBe('画风组件库');
    expect(w.find('.adm-ph__desc').text()).toBe('A0 基座');
    expect(w.find('.adm-ph__actions .adm-btn').exists()).toBe(true);
  });

  it('没有 actions 插槽时不渲染操作区', () => {
    const w = mount(AdminPageHeader, { props: { title: 't' } });
    expect(w.find('.adm-ph__actions').exists()).toBe(false);
    expect(w.find('.adm-ph__desc').exists()).toBe(false);
  });
});

describe('AdminToolbar', () => {
  it('左侧默认插槽 + 右侧 actions 插槽', () => {
    const w = mount(AdminToolbar, {
      slots: { default: '<select class="adm-select"></select>', actions: '<button class="adm-btn">搜索</button>' }
    });
    expect(w.find('.adm-tb__left .adm-select').exists()).toBe(true);
    expect(w.find('.adm-tb__right .adm-btn').exists()).toBe(true);
  });

  it('没有 actions 时不渲染右侧容器', () => {
    const w = mount(AdminToolbar, { slots: { default: '<span>only</span>' } });
    expect(w.find('.adm-tb__right').exists()).toBe(false);
  });
});

describe('AdminTable', () => {
  const table = '<table><thead><tr><th>ID</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>';

  it('默认插槽里的 table 原样渲染（壳不重写列）', () => {
    const w = mount(AdminTable, { slots: { default: table } });
    expect(w.find('.adm-table__body table').exists()).toBe(true);
    expect(w.find('th').text()).toBe('ID');
  });

  it('empty=true 显示空态文案，默认文案可被覆盖', () => {
    const a = mount(AdminTable, { props: { empty: true } });
    expect(a.find('.adm-empty').text()).toBe('暂无数据');
    const b = mount(AdminTable, { props: { empty: true, emptyText: '换个筛选条件试试' } });
    expect(b.find('.adm-empty').text()).toBe('换个筛选条件试试');
  });

  it('empty=false 不渲染空态', () => {
    const w = mount(AdminTable, { slots: { default: table } });
    expect(w.find('.adm-empty').exists()).toBe(false);
  });

  it('title / dense / footer 分别生效', () => {
    const w = mount(AdminTable, { props: { title: '资料列表', dense: true }, slots: { footer: '共 3 条' } });
    expect(w.find('.adm-table__title').text()).toBe('资料列表');
    expect(w.classes()).toContain('is-dense');
    expect(w.find('.adm-table__foot').text()).toBe('共 3 条');
  });
});

describe('AdminFormItem', () => {
  it('label + 必填星号 + 提示', () => {
    const w = mount(AdminFormItem, { props: { label: '试卷标题', required: true, hint: '可留空' } });
    expect(w.text()).toContain('试卷标题');
    expect(w.find('.adm-fi__req').exists()).toBe(true);
    expect(w.find('.adm-fi__hint').text()).toBe('可留空');
  });

  it('错误优先于提示，并给容器加 has-error', () => {
    const w = mount(AdminFormItem, { props: { label: '题量', hint: 'h', error: '必须是 1–300' } });
    expect(w.find('.adm-fi__error').text()).toBe('必须是 1–300');
    expect(w.find('.adm-fi__hint').exists()).toBe(false);
    expect(w.classes()).toContain('has-error');
  });

  it('默认非必填（与 D32「元数据全字段非必填」一致）', () => {
    const w = mount(AdminFormItem, { props: { label: '年份' } });
    expect(w.find('.adm-fi__req').exists()).toBe(false);
    expect(w.classes()).not.toContain('has-error');
  });
});
