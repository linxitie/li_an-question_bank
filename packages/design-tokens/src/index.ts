export const tokens = {
  colors: {
    primary: '#1A365D',
    primaryHover: '#152C4A',
    primaryActive: '#0F2035',
    accent: '#D4A843',
    accentHover: '#C49A35',
    accentActive: '#B08C2A',
    success: '#52C41A',
    warning: '#FAAD14',
    error: '#FF4D4F',
    info: '#1890FF',
    xingce: '#3B82F6',
    shenlun: '#10B981',
    gongzhuan: '#F59E0B',
  },
  spacing: {
    unit: 4,
    xs: 8,
    sm: 12,
    md: 16,
    lg: 20,
    xl: 24,
    '2xl': 32,
    '3xl': 40,
    '4xl': 48,
  },
  borderRadius: {
    xs: 4,
    sm: 8,
    md: 10,
    lg: 12,
    xl: 16,
    '2xl': 20,
    full: 9999,
  },
  breakpoints: {
    mobile: 768,
    tablet: 1024,
    desktop: 1280,
  },
} as const

export type Tokens = typeof tokens
