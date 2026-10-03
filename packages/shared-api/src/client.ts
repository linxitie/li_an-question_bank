import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'

/**
 * axios baseURL。
 * 注意：baseURL 已是 '/api'，因此调用方传入的路径必须**不含** '/api' 前缀，
 * 否则会拼出 '/api/api/xxx'。
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

/** 后端统一响应包络（见 packages/shared-types/src/api.ts ApiResponse） */
export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

class ApiClient {
  private instance: AxiosInstance

  constructor() {
    this.instance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    this.setupInterceptors()
  }

  private setupInterceptors() {
    // 请求拦截器 - 添加认证token
    this.instance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        // 发送 FormData 时必须让浏览器自行设置 boundary，
        // 手工声明 x-www-form-urlencoded / json 会导致后端收不到表单。
        if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
          if (config.headers) delete config.headers['Content-Type']
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // 响应拦截器 - 拆包 + 处理错误
    this.instance.interceptors.response.use(
      // 拆出后端统一响应包络的 data 层；非包络结构（裸对象）原样返回。
      (response) => {
        const body: any = response.data
        if (body && typeof body === 'object' && 'code' in body && 'data' in body) {
          return body.data
        }
        return body
      },
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token')
          // 本项目使用 Hash 路由（createWebHashHistory），登录页为 /#/login
          window.location.href = '/#/login'
        }
        return Promise.reject(error)
      }
    )
  }

  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.get(url, config)
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.post(url, data, config)
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.put(url, data, config)
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return this.instance.delete(url, config)
  }
}

export const apiClient = new ApiClient()
