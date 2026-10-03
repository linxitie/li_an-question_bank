import type { User } from './entities'

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginatedResponse<T> {
  total: number
  page: number
  page_size: number
  items: T[]
}

export interface LoginRequest {
  username: string
  password: string
}

/**
 * 登录响应。
 * 字段严格对齐后端 LoginResponse（backend/app/api/v1/auth.py:206-211），
 * 实际返回 access_token / refresh_token / token_type / user。
 * 历史上此处误声明为 `token`，与实现不一致导致 typecheck 报错。
 */
export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface QRCodeGenerateResponse {
  uuid: string
  qr_url: string
  qr_image_base64: string
  expires_in: number
}

export interface QRCodeStatusResponse {
  status: 'pending' | 'confirmed' | 'expired'
  token?: string
}

export interface DeviceInfo {
  device_id: string
  platform: 'pc' | 'tablet' | 'mobile'
  browser: string
  os: string
  ip: string
  location?: string
  last_active: string
  is_current: boolean
}
