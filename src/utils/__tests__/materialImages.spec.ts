import { describe, expect, it } from 'vitest';
import { collectCardImages } from '../materialImages';

/**
 * 卡片配图收集：
 * 一轮设计把「一卡两图」分成两处存放 —— 第 1 张 cover_image，第 2 张 content 里的 <img>。
 * 详情页要一次看全，就必须把两处合起来。
 */
describe('collectCardImages', () => {
  it('没有图返回空数组', () => {
    expect(collectCardImages(null)).toEqual([]);
    expect(collectCardImages({})).toEqual([]);
    expect(collectCardImages({ cover_image: '', content: '' })).toEqual([]);
  });

  it('只有封面', () => {
    expect(collectCardImages({ cover_image: '/uploads/a.jpg' })).toEqual(['/uploads/a.jpg']);
  });

  it('封面 + 正文内嵌图，按顺序', () => {
    const urls = collectCardImages({
      cover_image: '/uploads/a.jpg',
      content: '<p>x</p><p><img src="/uploads/b.jpg" alt="配图" /></p>'
    });
    expect(urls).toEqual(['/uploads/a.jpg', '/uploads/b.jpg']);
  });

  it('只有正文图（无封面）也能取到', () => {
    expect(collectCardImages({ content: '<img alt="x" src="/uploads/c.png">' })).toEqual([
      '/uploads/c.png'
    ]);
  });

  it('重复图去重且保序', () => {
    const urls = collectCardImages({
      cover_image: '/uploads/a.jpg',
      content: '<img src="/uploads/a.jpg"><img src="/uploads/b.jpg"><img src="/uploads/b.jpg">'
    });
    expect(urls).toEqual(['/uploads/a.jpg', '/uploads/b.jpg']);
  });

  it('单引号写法也认', () => {
    expect(collectCardImages({ content: "<img src='/uploads/d.webp' />" })).toEqual([
      '/uploads/d.webp'
    ]);
  });

  it('多次调用结果稳定（正则 lastIndex 不串）', () => {
    const card = { content: '<img src="/uploads/x.jpg"><img src="/uploads/y.jpg">' };
    const first = collectCardImages(card);
    const second = collectCardImages(card);
    expect(first).toEqual(second);
    expect(first).toHaveLength(2);
  });

  it('后端给了 image_urls 时优先使用（列表接口没有 content）', () => {
    const urls = collectCardImages({
      cover_image: '/uploads/a.jpg',
      image_urls: ['/uploads/a.jpg', '/uploads/b.jpg']
    });
    expect(urls).toEqual(['/uploads/a.jpg', '/uploads/b.jpg']);
  });

  it('image_urls 去重并忽略空值', () => {
    expect(
      collectCardImages({ image_urls: ['/uploads/a.jpg', '', '/uploads/a.jpg', '/uploads/b.jpg'] })
    ).toEqual(['/uploads/a.jpg', '/uploads/b.jpg']);
  });

  it('image_urls 为空数组时回退到封面/正文解析', () => {
    expect(collectCardImages({ image_urls: [], cover_image: '/uploads/z.jpg' })).toEqual([
      '/uploads/z.jpg'
    ]);
  });
});
