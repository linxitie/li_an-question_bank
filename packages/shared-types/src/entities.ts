import { DeviceInfo } from './api'

export interface User {
  user_id: number
  username: string
  real_name?: string
  role: string
  is_disabled: boolean
  device_sessions: DeviceInfo[]
}

export interface Question {
  question_id: number
  question_content: string
  question_type: string
  options: string[]
  answer: string
  analysis?: string
  category_id: number
}

export interface PracticeRecord {
  record_id: number
  question_id: number
  user_answer: string
  is_correct: boolean
  create_time: string
}

export interface WrongQuestion {
  wrong_id: number
  question_id: number
  wrong_count: number
  last_wrong_time: string
  question?: Question
}

export interface Favorite {
  fav_id: number
  question_id: number
  create_time: string
  question?: Question
}

export interface Note {
  note_id: number
  question_id: number
  note_text: string
  create_time: string
  update_time: string
}
