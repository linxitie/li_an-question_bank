/**
 * 设备最终裁决 · 纯函数单测（D-39，2026-11-17）
 *
 * 缺陷复现（用户实测）：Windows + Edge，UA 无 Touch、maxTouchPoints=0、
 * innerWidth=882 的**正常电脑窗口**被降级成平板，打开 /#/tablet/home 停在平板登录页。
 * 根因是守卫里「pc 且宽度 ≤1024 → 平板/手机」这句没有指针条件。
 */
import { describe, expect, it } from 'vitest'
import { resolveUiDevice } from '../loginPolicy'

const pc = 'pc' as const

describe('resolveUiDevice（宽窗口电脑，用户的真实场景）', () => {
  it('882 宽 · 无触摸 · 有鼠标 → 仍是电脑', () => {
    expect(
      resolveUiDevice({
        detected: pc,
        innerWidth: 882,
        coarsePointer: false,
        finePointer: true
      })
    ).toBe('pc')
  })

  it('882 宽 · 任何指针信号都缺 → 仍按电脑（不再凭宽度降级）', () => {
    expect(
      resolveUiDevice({
        detected: pc,
        innerWidth: 882,
        coarsePointer: false,
        finePointer: false
      })
    ).toBe('pc')
  })

  it('1024 宽 · 无触摸 → 电脑', () => {
    expect(
      resolveUiDevice({ detected: pc, innerWidth: 1024, coarsePointer: false, finePointer: true })
    ).toBe('pc')
  })
})

describe('resolveUiDevice（移动端仍要能降级）', () => {
  it('900 宽 · 纯手指（coarse 且无 fine）→ 平板', () => {
    expect(
      resolveUiDevice({ detected: pc, innerWidth: 900, coarsePointer: true, finePointer: false })
    ).toBe('tablet')
  })

  it('700 宽 · 纯手指 → 手机', () => {
    expect(
      resolveUiDevice({ detected: pc, innerWidth: 700, coarsePointer: true, finePointer: false })
    ).toBe('mobile')
  })

  it('触屏笔记本：coarse 与 fine 同时存在 → 不降级，仍是电脑', () => {
    expect(
      resolveUiDevice({ detected: pc, innerWidth: 900, coarsePointer: true, finePointer: true })
    ).toBe('pc')
  })
})

describe('resolveUiDevice（触屏笔记本被 UA 判成平板时）', () => {
  it('UA 判平板但只有精细指针 → 纠正回电脑', () => {
    expect(
      resolveUiDevice({
        detected: 'tablet',
        innerWidth: 1440,
        coarsePointer: false,
        finePointer: true
      })
    ).toBe('pc')
  })

  it('真平板（主输入是手指）→ 保持平板', () => {
    expect(
      resolveUiDevice({
        detected: 'tablet',
        innerWidth: 1024,
        coarsePointer: true,
        finePointer: false
      })
    ).toBe('tablet')
  })
})

describe('resolveUiDevice（手机 UA）', () => {
  it('手机判定不被改写', () => {
    expect(
      resolveUiDevice({
        detected: 'mobile',
        innerWidth: 390,
        coarsePointer: true,
        finePointer: false
      })
    ).toBe('mobile')
  })
})
