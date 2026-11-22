// @vitest-environment jsdom
/**
 * 能力画像雷达（P1）挂载测试
 *
 * 用户意见：学习计划里的"能力雷达图"和"我的"里的"能力画像"要合成一套、能动态更新。
 * 现在组件优先消费后端 /api/plan/current 的 capability（与学习计划同源），
 * 并展示近 30 天分科正确率；旧后端没有 capability 时回退本地六维计算。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import ProfileRadar from '../ProfileRadar.vue';

const CAPABILITY = {
  dims: [
    { key: 'level', label: '基础水平', value: 60, available: true, source: '画像·当前水平' },
    { key: 'hours', label: '时间投入', value: 50, available: true, source: '画像·每日时长' },
    { key: 'goal', label: '目标清晰', value: 100, available: true, source: '画像·目标' },
    { key: 'weak', label: '弱项认知', value: 50, available: true, source: '画像·薄弱科目' },
    { key: 'intro', label: '自我表达', value: 20, available: true, source: '画像·自我描述' },
    { key: 'plan', label: '计划执行', value: 50, available: true, source: '计划完成率' }
  ],
  avg: 55,
  updated_at: '2026-11-22T20:30:00',
  breakdown: [
    { subject_id: 1, subject: '行测', attempts: 120, accuracy: 55 },
    { subject_id: 2, subject: '申论', attempts: 20, accuracy: 80 }
  ]
};

function stubFetch(profileBody: unknown, planBody: unknown) {
  const fn = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(String(url).includes('/api/plan/current') ? planBody : profileBody)
    })
  );
  vi.stubGlobal('fetch', fn);
  return fn;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('ProfileRadar 与学习计划同源', () => {
  it('优先用后端 capability 的六维与均分', async () => {
    localStorage.setItem('token', 't-demo');
    stubFetch({ has_profile: true, self_level: '零基础' }, { has_plan: true, capability: CAPABILITY });

    const wrapper = mount(ProfileRadar);
    await flushPromises();

    expect(wrapper.find('.radar__sub').text()).toContain('与学习计划同源');
    expect(wrapper.find('.radar__score').text()).toBe('55');
    const names = wrapper.findAll('.radar__name').map((n) => n.text());
    expect(names).toEqual(['基础水平', '时间投入', '目标清晰', '弱项认知', '自我表达', '计划执行']);
    wrapper.unmount();
  });

  it('展示近 30 天分科正确率，低分标红', async () => {
    localStorage.setItem('token', 't-demo');
    stubFetch({ has_profile: true }, { has_plan: true, capability: CAPABILITY });

    const wrapper = mount(ProfileRadar);
    await flushPromises();

    const rows = wrapper.findAll('.radar__breakdown li');
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain('行测');
    expect(rows[0].text()).toContain('55%');
    expect(rows[0].find('.weak').exists()).toBe(true);
    expect(rows[1].find('.weak').exists()).toBe(false);
    wrapper.unmount();
  });

  it('旧后端没有 capability 时回退本地六维计算', async () => {
    localStorage.setItem('token', 't-demo');
    stubFetch(
      { has_profile: true, self_level: '有基础', daily_hours: 4, target_score: 210 },
      { has_plan: true, progress: { percent: 40 } }
    );

    const wrapper = mount(ProfileRadar);
    await flushPromises();

    expect(wrapper.find('.radar__sub').text()).toContain('六维自评');
    expect(wrapper.findAll('.radar__breakdown li')).toHaveLength(0);
    expect(wrapper.findAll('.radar__name')).toHaveLength(6);
    wrapper.unmount();
  });

  it('没有 token 时不发请求，仍能渲染空雷达', async () => {
    const fetchMock = stubFetch({}, {});
    const wrapper = mount(ProfileRadar);
    await flushPromises();

    expect(fetchMock).not.toHaveBeenCalled();
    expect(wrapper.findAll('.radar__name')).toHaveLength(6);
    wrapper.unmount();
  });
});
