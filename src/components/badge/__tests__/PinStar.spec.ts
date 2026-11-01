// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';
import PinStar from '../PinStar.vue';

/**
 * 精选星标：金色五角星。
 * 关键点是同页多个星标的渐变 id 必须互不相同，否则 SVG 渐变会互相覆盖
 * （一个页面里同时出现 2 枚精选徽章是常态）。
 */
describe('PinStar', () => {
  it('渲染五角星路径与金色渐变', () => {
    const w = mount(PinStar, { props: { size: 42 } });
    const svg = w.find('svg');
    expect(svg.exists()).toBe(true);
    expect(svg.attributes('width')).toBe('42');
    expect(svg.attributes('aria-label')).toBe('精选');
    const path = w.find('path');
    expect(path.attributes('d')).toContain('12 1.9');
    expect(path.attributes('fill')).toMatch(/^url\(#pinStarGold-/);
    const stops = w.findAll('stop');
    expect(stops.map((s) => s.attributes('stop-color'))).toEqual(['#FFE07A', '#F7B733', '#E0930B']);
  });

  it('同一页面两个实例的渐变 id 不同', () => {
    // 同一个 app 内挂两个星标（真实场景：徽章页同时有 2 枚精选）
    const Pair = defineComponent({
      components: { PinStar },
      template: '<div><PinStar /><PinStar :size="42" /></div>'
    });
    const w = mount(Pair);
    const ids = w.findAll('linearGradient').map((g) => g.attributes('id'));
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBeTruthy();
    expect(ids[1]).toBeTruthy();
    expect(ids[0]).not.toBe(ids[1]);
    w.unmount();
  });
});
