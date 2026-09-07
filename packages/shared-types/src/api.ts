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

export interface LoginResponse {
  token: string
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
