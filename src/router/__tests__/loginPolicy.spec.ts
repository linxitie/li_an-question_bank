/**
 * 三端登录准入 · 前端矩阵单测（P2，2026-11-16）
 *
 * 为什么测纯函数：路由守卫里的跳转判定不能靠"手点"验证（要起浏览器、造 3 个角色），
 * 把判定抽成 `src/router/loginPolicy.ts` 的纯函数后，这里可以穷举矩阵；
 * 守卫只负责调用它们（集成验证在 T-5 用真机/浏览器做）。
 *
 * 与后端的对应关系：后端 `app/core/device_policy.py` 是唯一真源，
 * 本文件验证"前端镜像没写反"——尤其 admin 必须被拦、teacher 必须放行。
 */
import { describe, expect, it } from 'vitest'
import {
  REASON_ADMIN_PC_ONLY,
  canRoleUseDevice,
  deviceOfPathPrefix,
  isDeviceDeniedMessage,
  resolveTeacherDevicePath,
  teacherDeviceHome,
  unauthorizedReasonForDevice,
} from '../loginPolicy'

describe('canRoleUseDevice（谁能待在设备端）', () => {
  it('学生与教师三端可用', () => {
    expect(canRoleUseDevice('student')).toBe(true)
    expect(canRoleUseDevice('teacher')).toBe(true)
  })

  it('管理员一律不可用设备端（需求：管理员必须电脑）', () => {
    expect(canRoleUseDevice('admin')).toBe(false)
    expect(canRoleUseDevice('ADMIN')).toBe(false)
  })

  it('空角色/未知角色不放行', () => {
    expect(canRoleUseDevice('')).toBe(false)
    expect(canRoleUseDevice(null)).toBe(false)
    expect(canRoleUseDevice(undefined)).toBe(false)
    expect(canRoleUseDevice('auditor')).toBe(false)
  })
})

describe('unauthorizedReasonForDevice（被拒原因）', () => {
  it('管理员 → admin_pc_only', () => {
    expect(unauthorizedReasonForDevice('admin')).toBe(REASON_ADMIN_PC_ONLY)
  })

  it('教师/学生不被判定为设备受限', () => {
    expect(unauthorizedReasonForDevice('teacher')).toBeNull()
    expect(unauthorizedReasonForDevice('student')).toBeNull()
  })
})

describe('deviceOfPathPrefix（路径属于哪一端）', () => {
  it('识别 /tablet 与 /mobile 前缀', () => {
    expect(deviceOfPathPrefix('/tablet/home')).toBe('tablet')
    expect(deviceOfPathPrefix('/mobile/home')).toBe('mobile')
  })

  it('PC 路径返回 null', () => {
    expect(deviceOfPathPrefix('/login')).toBeNull()
    expect(deviceOfPathPrefix('/teacher/dashboard')).toBeNull()
    expect(deviceOfPathPrefix('/')).toBeNull()
  })
})

describe('教师设备端落地路径', () => {
  it('对外路径为 /<device>/teacher/home', () => {
    expect(teacherDeviceHome('tablet')).toBe('/tablet/teacher/home')
    expect(teacherDeviceHome('mobile')).toBe('/mobile/teacher/home')
  })

  it('学生首页/入口改投教师首页', () => {
    expect(resolveTeacherDevicePath('/tablet/home', 'tablet')).toBe('/tablet/teacher/home')
    expect(resolveTeacherDevicePath('/mobile/home', 'mobile')).toBe('/mobile/teacher/home')
    expect(resolveTeacherDevicePath('/tablet', 'tablet')).toBe('/tablet/teacher/home')
    expect(resolveTeacherDevicePath('/mobile/', 'mobile')).toBe('/mobile/teacher/home')
  })

  it('其它页面不被劫持（论坛/金句照常访问）', () => {
    expect(resolveTeacherDevicePath('/tablet/forum', 'tablet')).toBeNull()
    expect(resolveTeacherDevicePath('/mobile/quotes', 'mobile')).toBeNull()
    expect(resolveTeacherDevicePath('/tablet/teacher/home', 'tablet')).toBeNull()
  })
})

describe('isDeviceDeniedMessage（登录失败文案判定）', () => {
  it('命中设备受限类文案', () => {
    expect(isDeviceDeniedMessage('管理员仅支持电脑端登录，请改用电脑访问')).toBe(true)
    expect(isDeviceDeniedMessage('移动端/平板端仅支持学生登录，教师/管理员请使用电脑端')).toBe(true)
  })

  it('普通失败文案不误判', () => {
    expect(isDeviceDeniedMessage('密码错误，请重新输入')).toBe(false)
    expect(isDeviceDeniedMessage('用户名不存在: xxx')).toBe(false)
    expect(isDeviceDeniedMessage('')).toBe(false)
    expect(isDeviceDeniedMessage(null)).toBe(false)
  })
})
