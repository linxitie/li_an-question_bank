/**
 * 设备 × 界面一致性 · 纯函数单测（D-28，2026-11-16）
 *
 * 背景缺陷（实测）：电脑打开 `/#/tablet/home`、`/#/mobile/teacher/papers` 会直接渲染
 * 平板/手机界面；手机/平板打开 `/#/teacher/dashboard` 会直接渲染电脑版教师端。
 * 修复把「该跳去哪」抽成纯函数，这里穷举映射，避免再靠手点验证。
 */
import { describe, expect, it } from 'vitest'
import {
  devicePathForPcPath,
  isDeviceAgnosticPath,
  pcPathForDevicePath,
  swapDevicePrefix
} from '../loginPolicy'

describe('pcPathForDevicePath（电脑上打开了设备端页面）', () => {
  it('平板/手机首页 → 电脑首页', () => {
    expect(pcPathForDevicePath('/tablet/home')).toBe('/home')
    expect(pcPathForDevicePath('/mobile/home')).toBe('/home')
  })

  it('教师设备端四页 → 电脑教师端四页', () => {
    expect(pcPathForDevicePath('/tablet/teacher/home')).toBe('/teacher/dashboard')
    expect(pcPathForDevicePath('/mobile/teacher/home')).toBe('/teacher/dashboard')
    expect(pcPathForDevicePath('/tablet/teacher/questions')).toBe('/teacher/questions')
    expect(pcPathForDevicePath('/mobile/teacher/papers')).toBe('/teacher/papers')
    expect(pcPathForDevicePath('/tablet/teacher/scores')).toBe('/teacher/scores')
  })

  it('末尾斜杠与查询串不影响映射', () => {
    expect(pcPathForDevicePath('/tablet/home/')).toBe('/home')
    expect(pcPathForDevicePath('/tablet/home?x=1')).toBe('/home')
  })

  it('没有等价页时返回 null（调用方兜底到 /）', () => {
    expect(pcPathForDevicePath('/tablet/news/2024')).toBeNull()
    expect(pcPathForDevicePath('/home')).toBeNull()
  })
})

describe('swapDevicePrefix（平板 ↔ 手机互串）', () => {
  it('双向换前缀', () => {
    expect(swapDevicePrefix('/mobile/home', 'tablet')).toBe('/tablet/home')
    expect(swapDevicePrefix('/tablet/teacher/papers', 'mobile')).toBe('/mobile/teacher/papers')
  })

  it('电脑路径没有前缀可换 → null', () => {
    expect(swapDevicePrefix('/home', 'tablet')).toBeNull()
  })

  it('目标前缀与当前相同 → null（不自己跳自己）', () => {
    expect(swapDevicePrefix('/tablet/home', 'tablet')).toBeNull()
  })
})

describe('devicePathForPcPath（手机/平板打开了电脑端页面）', () => {
  it('教师端四页映射到设备端四页', () => {
    expect(devicePathForPcPath('/teacher/dashboard', 'tablet')).toBe('/tablet/teacher/home')
    expect(devicePathForPcPath('/teacher/questions', 'mobile')).toBe('/mobile/teacher/questions')
    expect(devicePathForPcPath('/teacher/papers', 'tablet')).toBe('/tablet/teacher/papers')
    expect(devicePathForPcPath('/teacher/scores', 'mobile')).toBe('/mobile/teacher/scores')
  })

  it('教师端没有设备实现的页 → 回教师设备端首页（不把电脑版塞进手机）', () => {
    expect(devicePathForPcPath('/teacher/classes', 'mobile')).toBe('/mobile/teacher/home')
    expect(devicePathForPcPath('/teacher/analytics', 'tablet')).toBe('/tablet/teacher/home')
  })

  it('题目导入（电脑端工作台）→ 题目管理', () => {
    expect(devicePathForPcPath('/question-import', 'tablet')).toBe('/tablet/teacher/questions')
  })

  it('非教师端路径不接管（避免误伤学生页）', () => {
    expect(devicePathForPcPath('/materials/xingce', 'mobile')).toBeNull()
    expect(devicePathForPcPath('/admin/users', 'tablet')).toBeNull()
  })
})

describe('isDeviceAgnosticPath（设备无关页不参与纠正）', () => {
  it('未授权页/帮助页/登录页可停在任意设备', () => {
    expect(isDeviceAgnosticPath('/unauthorized')).toBe(true)
    expect(isDeviceAgnosticPath('/help')).toBe(true)
    expect(isDeviceAgnosticPath('/materials-preview')).toBe(true)
  })

  it('设备端业务页不算无关页', () => {
    expect(isDeviceAgnosticPath('/tablet/home')).toBe(false)
    expect(isDeviceAgnosticPath('/teacher/dashboard')).toBe(false)
  })
})
