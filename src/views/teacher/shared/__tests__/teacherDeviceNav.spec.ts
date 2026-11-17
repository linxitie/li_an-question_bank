/**
 * 教师设备端功能卡配置单测（P3，2026-11-16）
 *
 * 为什么要测配置：设备端的「写操作」口径是 D-19 定的——
 * 统一显示「功能待开发」并预留「上传」位置。文案/状态写在配置里，
 * 一旦有人把 status 改成 ready 却没建对应路由，教师点进去就是 404；
 * 这里用断言把「ready 的项必须有 path 且能映射出设备端路由」锁死。
 */
import { describe, expect, it } from 'vitest'
import {
  TEACHER_NAV_ITEMS,
  TEACHER_NAV_STATUS_LABEL,
  deviceNavPath,
} from '../teacherDeviceNav'

describe('教师设备端功能卡', () => {
  it('每项都有 key/title/desc/status/label', () => {
    for (const item of TEACHER_NAV_ITEMS) {
      expect(item.key).toBeTruthy()
      expect(item.title).toBeTruthy()
      expect(item.desc).toBeTruthy()
      expect(TEACHER_NAV_STATUS_LABEL[item.status]).toBeTruthy()
    }
  })

  it('ready 项必须能映射到设备端路由（否则点了 404）', () => {
    const ready = TEACHER_NAV_ITEMS.filter((i) => i.status === 'ready')
    expect(ready.length).toBeGreaterThan(0)
    for (const item of ready) {
      expect(item.path, `${item.key} 缺少电脑端对照路径`).toBeTruthy()
      expect(deviceNavPath('tablet', item)).toBe(
        `/tablet${String(item.path).replace(/^\/teacher/, '/teacher')}`,
      )
      expect(deviceNavPath('mobile', item)).toContain('/mobile/teacher/')
    }
  })

  it('写操作（组卷/批改/导入）标注「功能待开发」且无设备端路径', () => {
    const writeKeys = ['paper-edit', 'grading', 'import']
    for (const key of writeKeys) {
      const item = TEACHER_NAV_ITEMS.find((i) => i.key === key)
      expect(item, `缺少写操作项 ${key}`).toBeTruthy()
      expect(item!.status).toBe('todo')
      expect(TEACHER_NAV_STATUS_LABEL[item!.status]).toBe('功能待开发')
      expect(deviceNavPath('tablet', item!)).toBeNull()
      expect(item!.reason).toContain('尚未开发')
    }
  })

  it('预留上传位置（D-19）', () => {
    const upload = TEACHER_NAV_ITEMS.find((i) => i.key === 'upload')
    expect(upload, '缺少上传预留位').toBeTruthy()
    expect(upload!.status).toBe('reserved')
    expect(TEACHER_NAV_STATUS_LABEL[upload!.status]).toBe('位置预留')
    expect(deviceNavPath('tablet', upload!)).toBeNull()
  })

  it('同一 key 不重复', () => {
    const keys = TEACHER_NAV_ITEMS.map((i) => i.key)
    expect(new Set(keys).size).toBe(keys.length)
  })
})
