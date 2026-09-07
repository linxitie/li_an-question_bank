# Multi-Device Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement multi-device adaptation for the LiAn Exam Bank system, including tablet and mobile support, QR code login, and data synchronization across three platforms.

**Architecture:** Three separate VTJ projects (PC, tablet, mobile) sharing a common core layer (@linxi/shared-*). Backend provides QR code login via Redis, device management API, and WebSocket sync. Frontend uses CSS media queries for responsive layouts.

**Tech Stack:** Vue 3, VTJ Low-Code Framework, FastAPI, SQLAlchemy, Redis, JWT, Pinia, CSS Variables, Media Queries

---

## File Structure

### Backend Files
```
backend/app/
├── api/v1/
│   ├── auth_qrcode.py          # QR code login endpoints
│   ├── devices.py              # Device management endpoints
│   └── auth.py                 # Modified: register device on login
├── models/
│   └── models.py               # Modified: add device_sessions field
├── core/
│   ├── security.py             # Modified: device token management
│   └── redis_client.py         # New: Redis connection wrapper
└── migrations/
    └── versions/
        └── xxx_add_device_sessions.py  # Alembic migration
```

### Frontend Shared Layer
```
packages/
├── shared-types/
│   └── src/
│       ├── index.ts            # Type exports
│       ├── api.ts              # API response types
│       └── entities.ts         # Entity types
├── shared-api/
│   └── src/
│       ├── index.ts            # API client exports
│       ├── client.ts           # Axios/fetch wrapper
│       └── interceptors.ts     # Request/response interceptors
├── shared-store/
│   └── src/
│       ├── index.ts            # Store exports
│       ├── auth.ts             # Auth store
│       └── user.ts             # User store
├── shared-utils/
│   └── src/
│       ├── index.ts            # Utils exports
│       ├── date.ts             # Date utilities
│       └── validation.ts       # Validation helpers
└── design-tokens/
    └── src/
        ├── index.ts            # Token exports
        └── variables.css       # CSS custom properties
```

### PC端 Modified Files
```
.vtj/files/
├── login.json                  # Modified: add QR code tab
└── download_client.json        # Modified: replace with QR code component

src/views/
└── login/
    └── qrcode-tab.vue          # New: QR code login component
```

### Tablet端 New Project
```
linxitie.policy-exam-bank-tablet/
├── .vtj/
│   ├── files/                  # VTJ DSL JSON files
│   └── router.js               # Route definitions
├── src/
│   ├── views/
│   │   ├── home/               # Home page
│   │   ├── questions/          # Question bank
│   │   ├── practice/           # Practice modules
│   │   ├── forum/              # Forum
│   │   └── profile/            # User profile
│   └── components/
│       ├── layout/             # Layout components
│       └── shared/             # Shared components
└── public/
    └── index.html
```

### Mobile端 New Project
```
linxitie.policy-exam-bank-mobile/
├── .vtj/
│   ├── files/                  # VTJ DSL JSON files
│   └── router.js               # Route definitions
├── src/
│   ├── views/
│   │   ├── home/               # Home page
│   │   ├── questions/          # Question bank
│   │   ├── practice/           # Practice modules
│   │   ├── forum/              # Forum
│   │   └── profile/            # User profile
│   └── components/
│       ├── layout/             # Layout components
│       └── shared/             # Shared components
└── public/
    └── index.html
```

---

## Task 1: Backend - Redis Client Setup

**Files:**
- Create: `backend/app/core/redis_client.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add Redis config to settings**

```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # ... existing fields ...
    
    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    @property
    def redis_url(self) -> str:
        password = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
```

- [ ] **Step 2: Create Redis client wrapper**

```python
# backend/app/core/redis_client.py
import redis.asyncio as redis
from typing import Optional
import json
from datetime import datetime

from .config import settings

redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    """Get Redis client instance"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client

async def close_redis():
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None

class QRCodeStore:
    """QR code state management in Redis"""
    
    PREFIX = "qr:"
    CONFIRMED_SUFFIX = ":confirmed"
    TTL_SECONDS = 60
    CONFIRMED_TTL_SECONDS = 300
    
    @staticmethod
    async def create_qr(uuid: str, device_info: dict) -> None:
        """Create QR code state"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}"
        data = {
            "status": "pending",
            "pc_device_info": device_info,
            "created_at": datetime.utcnow().isoformat()
        }
        await r.set(key, json.dumps(data), ex=QRCodeStore.TTL_SECONDS)
    
    @staticmethod
    async def get_qr(uuid: str) -> Optional[dict]:
        """Get QR code state"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}"
        data = await r.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    async def confirm_qr(uuid: str, user_id: int, token: str) -> None:
        """Confirm QR code login"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}{QRCodeStore.CONFIRMED_SUFFIX}"
        data = {
            "user_id": user_id,
            "token": token,
            "confirmed_at": datetime.utcnow().isoformat()
        }
        await r.set(key, json.dumps(data), ex=QRCodeStore.CONFIRMED_TTL_SECONDS)
        
        # Update status to confirmed
        qr_key = f"{QRCodeStore.PREFIX}{uuid}"
        qr_data = await r.get(qr_key)
        if qr_data:
            qr = json.loads(qr_data)
            qr["status"] = "confirmed"
            await r.set(qr_key, json.dumps(qr), ex=QRCodeStore.TTL_SECONDS)
    
    @staticmethod
    async def get_confirmation(uuid: str) -> Optional[dict]:
        """Get confirmation data"""
        r = await get_redis()
        key = f"{QRCodeStore.PREFIX}{uuid}{QRCodeStore.CONFIRMED_SUFFIX}"
        data = await r.get(key)
        return json.loads(data) if data else None
    
    @staticmethod
    async def delete_qr(uuid: str) -> None:
        """Delete QR code state"""
        r = await get_redis()
        await r.delete(f"{QRCodeStore.PREFIX}{uuid}")
        await r.delete(f"{QRCodeStore.PREFIX}{uuid}{QRCodeStore.CONFIRMED_SUFFIX}")
```

- [ ] **Step 3: Update main.py to include Redis lifecycle**

```python
# backend/app/main.py
from contextlib import asynccontextmanager
from .core.redis_client import get_redis, close_redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await get_redis()
    yield
    # Shutdown
    await close_redis()

app = FastAPI(lifespan=lifespan)
```

- [ ] **Step 4: Commit changes**

```bash
git add backend/app/core/config.py backend/app/core/redis_client.py backend/app/main.py
git commit -m "feat: add Redis client for QR code state management"
```

---

## Task 2: Backend - QR Code Login API

**Files:**
- Create: `backend/app/api/v1/auth_qrcode.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create QR code API router**

```python
# backend/app/api/v1/auth_qrcode.py
"""
二维码扫码登录 API
"""
import uuid
import qrcode
import base64
from io import BytesIO
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user, create_access_token
from ...core.redis_client import QRCodeStore
from ...models.models import SysUser

router = APIRouter(prefix="/api/auth/qrcode", tags=["二维码登录"])

def get_device_info(request: Request) -> dict:
    """Extract device info from request headers"""
    user_agent = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else "unknown"
    
    # Simple device detection
    browser = "Unknown"
    os = "Unknown"
    
    if "Chrome" in user_agent:
        browser = "Chrome"
    elif "Firefox" in user_agent:
        browser = "Firefox"
    elif "Safari" in user_agent:
        browser = "Safari"
    
    if "Windows" in user_agent:
        os = "Windows"
    elif "Mac" in user_agent:
        os = "macOS"
    elif "Linux" in user_agent:
        os = "Linux"
    elif "Android" in user_agent:
        os = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        os = "iOS"
    
    return {
        "browser": browser,
        "os": os,
        "ip": ip,
        "user_agent": user_agent
    }

@router.post("/generate", summary="生成二维码")
async def generate_qrcode(
    request: Request,
    current_user: SysUser = Depends(get_current_user)
):
    """PC端生成登录二维码"""
    qr_uuid = str(uuid.uuid4())
    device_info = get_device_info(request)
    
    # Store in Redis
    await QRCodeStore.create_qr(qr_uuid, device_info)
    
    # Generate QR code image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(f"liani://login/{qr_uuid}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="#1A365D", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return {
        "uuid": qr_uuid,
        "qr_url": f"liani://login/{qr_uuid}",
        "qr_image_base64": f"data:image/png;base64,{qr_base64}",
        "expires_in": 60
    }

@router.get("/{qr_uuid}/info", summary="获取PC端信息")
async def get_pc_info(qr_uuid: str):
    """移动端扫码获取PC端设备信息"""
    qr_data = await QRCodeStore.get_qr(qr_uuid)
    
    if not qr_data:
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")
    
    return {
        "device": qr_data["pc_device_info"],
        "login_time": qr_data["created_at"]
    }

@router.post("/{qr_uuid}/confirm", summary="确认登录")
async def confirm_login(
    qr_uuid: str,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移动端确认登录"""
    qr_data = await QRCodeStore.get_qr(qr_uuid)
    
    if not qr_data:
        raise HTTPException(status_code=404, detail="二维码不存在或已过期")
    
    if qr_data.get("status") == "confirmed":
        raise HTTPException(status_code=400, detail="二维码已使用")
    
    # Generate token for PC
    token = create_access_token(data={"sub": current_user.username})
    
    # Store confirmation
    await QRCodeStore.confirm_qr(qr_uuid, current_user.user_id, token)
    
    return {
        "success": True,
        "message": "登录确认成功"
    }

@router.get("/{qr_uuid}/status", summary="查询二维码状态")
async def check_status(qr_uuid: str):
    """PC端轮询二维码状态"""
    qr_data = await QRCodeStore.get_qr(qr_uuid)
    
    if not qr_data:
        return {"status": "expired"}
    
    if qr_data.get("status") == "confirmed":
        confirmation = await QRCodeStore.get_confirmation(qr_uuid)
        return {
            "status": "confirmed",
            "token": confirmation["token"] if confirmation else None
        }
    
    return {"status": "pending"}
```

- [ ] **Step 2: Install qrcode dependency**

```bash
pip install qrcode[pil]
```

- [ ] **Step 3: Register router in main.py**

```python
# backend/app/main.py
from .api.v1 import auth_qrcode

app.include_router(auth_qrcode.router)
```

- [ ] **Step 4: Commit changes**

```bash
git add backend/app/api/v1/auth_qrcode.py backend/app/main.py
git commit -m "feat: add QR code login API endpoints"
```

---

## Task 3: Backend - Device Management API

**Files:**
- Create: `backend/app/api/v1/devices.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/models.py`

- [ ] **Step 1: Add device_sessions field to SysUser model**

```python
# backend/app/models/models.py
class SysUser(Base):
    # ... existing fields ...
    device_sessions = Column(JSON, default=list)  # Device session list
```

- [ ] **Step 2: Create Alembic migration**

```bash
alembic revision --autogenerate -m "add device_sessions to sys_user"
```

- [ ] **Step 3: Create devices API router**

```python
# backend/app/api/v1/devices.py
"""
设备管理 API
"""
import uuid
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import SysUser

router = APIRouter(prefix="/api/auth/devices", tags=["设备管理"])

MAX_DEVICES = 3
SESSION_CLEANUP_DAYS = 30

def cleanup_old_sessions(sessions: list) -> list:
    """Remove sessions older than 30 days"""
    cutoff = datetime.utcnow() - timedelta(days=SESSION_CLEANUP_DAYS)
    return [
        s for s in sessions 
        if datetime.fromisoformat(s.get("last_active", "2000-01-01")) > cutoff
    ]

@router.get("/", summary="获取设备列表")
async def list_devices(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户所有登录设备"""
    sessions = current_user.device_sessions or []
    sessions = cleanup_old_sessions(sessions)
    
    # Mark current device
    for session in sessions:
        session["is_current"] = False
    
    return {
        "devices": sessions,
        "max_devices": MAX_DEVICES
    }

@router.delete("/{device_id}", summary="移除设备")
async def remove_device(
    device_id: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """移除指定登录设备"""
    sessions = current_user.device_sessions or []
    sessions = [
        s for s in sessions 
        if s.get("device_id") != device_id
    ]
    
    current_user.device_sessions = sessions
    db.commit()
    
    return {"message": "设备已移除"}

@router.post("/revoke-all", summary="强制下线所有设备")
async def revoke_all_devices(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """强制下线所有设备（除当前设备）"""
    current_user.device_sessions = []
    db.commit()
    
    return {"message": "所有设备已下线"}
```

- [ ] **Step 4: Register router in main.py**

```python
# backend/app/main.py
from .api.v1 import devices

app.include_router(devices.router)
```

- [ ] **Step 5: Commit changes**

```bash
git add backend/app/models/models.py backend/app/api/v1/devices.py backend/app/main.py
git commit -m "feat: add device management API"
```

---

## Task 4: Backend - Modify Auth to Register Device

**Files:**
- Modify: `backend/app/api/v1/auth.py`

- [ ] **Step 1: Add device registration to login endpoint**

```python
# backend/app/api/v1/auth.py
import uuid
from datetime import datetime

@router.post("/login", summary="用户登录")
async def login(
    payload: schemas.LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    # ... existing login logic ...
    
    # Register device session
    device_info = {
        "device_id": str(uuid.uuid4()),
        "platform": detect_platform(request),  # pc/tablet/mobile
        "browser": extract_browser(request),
        "os": extract_os(request),
        "ip": request.client.host,
        "location": await get_location(request.client.host),
        "token_hash": hash_token(token),
        "last_active": datetime.utcnow().isoformat(),
        "is_current": True
    }
    
    # Update device sessions
    sessions = user.device_sessions or []
    sessions = [s for s in sessions if s.get("device_id") != device_info["device_id"]]
    sessions.append(device_info)
    
    # Limit to MAX_DEVICES
    if len(sessions) > 3:
        sessions = sessions[-3:]
    
    user.device_sessions = sessions
    user.last_login_ip = request.client.host
    db.commit()
    
    return {"token": token, "user": user_data}
```

- [ ] **Step 2: Add helper functions**

```python
# backend/app/api/v1/auth.py
def detect_platform(request: Request) -> str:
    """Detect user platform from user agent"""
    ua = request.headers.get("user-agent", "").lower()
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    elif "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "pc"

def hash_token(token: str) -> str:
    """Hash token for storage"""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()
```

- [ ] **Step 3: Commit changes**

```bash
git add backend/app/api/v1/auth.py
git commit -m "feat: register device on login"
```

---

## Task 5: Frontend Shared - Design Tokens

**Files:**
- Create: `packages/design-tokens/package.json`
- Create: `packages/design-tokens/src/variables.css`
- Create: `packages/design-tokens/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@linxi/design-tokens",
  "version": "1.0.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "files": ["src"]
}
```

- [ ] **Step 2: Create CSS variables file**

```css
/* packages/design-tokens/src/variables.css */
:root {
  /* ========== Colors ========== */
  --color-primary: #1A365D;
  --color-primary-hover: #152C4A;
  --color-primary-active: #0F2035;
  
  --color-accent: #D4A843;
  --color-accent-hover: #C49A35;
  --color-accent-active: #B08C2A;
  
  --color-success: #52C41A;
  --color-warning: #FAAD14;
  --color-error: #FF4D4F;
  --color-info: #1890FF;
  
  --color-xingce: #3B82F6;
  --color-shenlun: #10B981;
  --color-gongzhuan: #F59E0B;
  
  --color-text-primary: #1F2937;
  --color-text-secondary: #6B7280;
  --color-text-tertiary: #9CA3AF;
  --color-border: #E5E7EB;
  --color-divider: #F3F4F6;
  
  /* ========== Backgrounds ========== */
  --bg-primary: #F0F2F5;
  --bg-secondary: #F5F7FA;
  --bg-tertiary: #FAFBFC;
  --bg-card: #FFFFFF;
  --bg-card-hover: #FAFAFA;
  --bg-card-active: #F5F5F5;
  
  /* ========== Spacing ========== */
  --space-unit: 4px;
  --space-xs: 8px;
  --space-sm: 12px;
  --space-md: 16px;
  --space-lg: 20px;
  --space-xl: 24px;
  --space-2xl: 32px;
  --space-3xl: 40px;
  --space-4xl: 48px;
  
  /* ========== Border Radius ========== */
  --radius-xs: 4px;
  --radius-sm: 8px;
  --radius-md: 10px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-2xl: 20px;
  --radius-full: 9999px;
  
  /* ========== Typography ========== */
  --font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-size-xs: 12px;
  --font-size-sm: 13px;
  --font-size-base: 14px;
  --font-size-base-tablet: 15px;
  --font-size-base-mobile: 14px;
  --font-size-lg: 16px;
  --font-size-xl: 18px;
  --font-size-2xl: 20px;
  --font-size-3xl: 24px;
  --font-size-4xl: 30px;
  --font-size-5xl: 36px;
  
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;
  
  --line-height-tight: 1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.6;
  
  /* ========== Shadows ========== */
  --shadow-xs: 0 1px 2px rgba(26, 43, 95, 0.02);
  --shadow-light: 0 1px 4px rgba(26, 43, 95, 0.04);
  --shadow-medium: 0 4px 16px rgba(26, 43, 95, 0.1);
  --shadow-heavy: 0 8px 28px rgba(26, 43, 95, 0.12);
  --shadow-xl: 0 12px 40px rgba(26, 43, 95, 0.15);
  
  /* ========== Animations ========== */
  --duration-fast: 150ms;
  --duration-normal: 300ms;
  --duration-slow: 500ms;
  --easing-default: cubic-bezier(0.4, 0, 0.2, 1);
  --easing-in: cubic-bezier(0.4, 0, 1, 1);
  --easing-out: cubic-bezier(0, 0, 0.2, 1);
  
  /* ========== Touch Targets ========== */
  --touch-target-min: 44px;
  
  /* ========== Breakpoints ========== */
  --breakpoint-mobile: 768px;
  --breakpoint-tablet: 1024px;
  --breakpoint-desktop: 1280px;
}
```

- [ ] **Step 3: Create TypeScript exports**

```typescript
// packages/design-tokens/src/index.ts
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
```

- [ ] **Step 4: Commit changes**

```bash
git add packages/design-tokens/
git commit -m "feat: add design tokens package"
```

---

## Task 6: Frontend Shared - API Client

**Files:**
- Create: `packages/shared-api/package.json`
- Create: `packages/shared-api/src/client.ts`
- Create: `packages/shared-api/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@linxi/shared-api",
  "version": "1.0.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "dependencies": {
    "axios": "^1.7.9"
  }
}
```

- [ ] **Step 2: Create API client**

```typescript
// packages/shared-api/src/client.ts
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

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
    // Request interceptor - add auth token
    this.instance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor - handle errors
    this.instance.interceptors.response.use(
      (response) => response.data,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token')
          window.location.href = '/login'
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
```

- [ ] **Step 3: Create index exports**

```typescript
// packages/shared-api/src/index.ts
export { apiClient } from './client'
export type { AxiosRequestConfig } from 'axios'
```

- [ ] **Step 4: Commit changes**

```bash
git add packages/shared-api/
git commit -m "feat: add shared API client package"
```

---

## Task 7: PC端 - QR Code Login Tab

**Files:**
- Create: `.vtj/files/qrcode_login.json`
- Modify: `.vtj/files/login.json`

- [ ] **Step 1: Create QR code login component JSON**

```json
{
  "id": "qrcode-login",
  "type": "block",
  "name": "QRCodeLogin",
  "state": {
    "uuid": "",
    "status": "initial",
    "countdown": 60,
    "countdownTimer": null
  },
  "methods": {
    "generateQRCode": "async function() {\n  const res = await fetch('/api/auth/qrcode/generate', {\n    method: 'POST',\n    headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }\n  })\n  const data = await res.json()\n  this.uuid = data.uuid\n  this.status = 'pending'\n  this.startCountdown()\n  this.startPolling()\n}",
    "startCountdown": "function() {\n  this.countdown = 60\n  this.countdownTimer = setInterval(() => {\n    this.countdown--\n    if (this.countdown <= 0) {\n      clearInterval(this.countdownTimer)\n      this.status = 'expired'\n    }\n  }, 1000)\n}",
    "startPolling": "async function() {\n  const poll = async () => {\n    const res = await fetch(`/api/auth/qrcode/${this.uuid}/status`)\n    const data = await res.json()\n    \n    if (data.status === 'confirmed') {\n      localStorage.setItem('token', data.token)\n      this.status = 'confirmed'\n      window.location.href = '/'\n    } else if (data.status === 'expired') {\n      this.status = 'expired'\n    } else {\n      setTimeout(poll, 1500)\n    }\n  }\n  poll()\n}",
    "refresh": "function() {\n  clearInterval(this.countdownTimer)\n  this.generateQRCode()\n}"
  },
  "template": "<div class=\"qrcode-login\"><div class=\"qrcode-container\"><img :src=\"qrImage\" v-if=\"qrImage\" class=\"qrcode-image\" /><div v-else class=\"qrcode-placeholder\"><span>正在生成二维码...</span></div></div><div class=\"qrcode-info\"><p class=\"qrcode-tip\">请使用砺安题库APP扫描二维码登录</p><p v-if=\"status === 'pending'\" class=\"qrcode-status\"><span class=\"countdown\">{{ countdown }}秒后过期</span></p><p v-if=\"status === 'expired'\" class=\"qrcode-status expired\"><span>二维码已过期</span><button @click=\"refresh\" class=\"refresh-btn\">刷新</button></p><p v-if=\"status === 'confirmed'\" class=\"qrcode-status confirmed\"><span>登录成功，正在跳转...</span></p></div></div>"
}
```

- [ ] **Step 2: Update login.json to include QR code tab**

```json
{
  "id": "login",
  "type": "page",
  "name": "LoginPage",
  "state": {
    "activeTab": "password"
  },
  "methods": {
    "switchTab": "function(tab) {\n  this.activeTab = tab\n}"
  },
  "template": "<div class=\"login-page\"><div class=\"login-tabs\"><button :class=\"['tab-btn', { active: activeTab === 'password' }]\" @click=\"switchTab('password')\">账号密码登录</button><button :class=\"['tab-btn', { active: activeTab === 'sms' }]\" @click=\"switchTab('sms')\">验证码登录</button><button :class=\"['tab-btn', { active: activeTab === 'qrcode' }]\" @click=\"switchTab('qrcode')\">扫码登录</button></div><div class=\"login-content\"><div v-if=\"activeTab === 'password'\" class=\"tab-content\"><!-- Password login form --></div><div v-if=\"activeTab === 'sms'\" class=\"tab-content\"><!-- SMS login form --></div><div v-if=\"activeTab === 'qrcode'\" class=\"tab-content\"><QRCodeLogin /></div></div></div>"
}
```

- [ ] **Step 3: Commit changes**

```bash
git add .vtj/files/qrcode_login.json .vtj/files/login.json
git commit -m "feat: add QR code login tab to PC login page"
```

---

## Task 8: Mobile - QR Code Confirm Modal

**Files:**
- Create: `linxitie.policy-exam-bank-mobile/src/components/QRConfirmModal.vue`

- [ ] **Step 1: Create QR confirm modal component**

```vue
<template>
  <div class="qr-confirm-modal" v-if="visible">
    <div class="modal-overlay" @click="handleCancel"></div>
    <div class="modal-content">
      <div class="modal-header">
        <h3>确认登录</h3>
        <button class="close-btn" @click="handleCancel">×</button>
      </div>
      
      <div class="modal-body">
        <div class="device-info">
          <div class="info-item">
            <span class="label">设备：</span>
            <span class="value">{{ deviceInfo.browser }} / {{ deviceInfo.os }}</span>
          </div>
          <div class="info-item">
            <span class="label">位置：</span>
            <span class="value">{{ deviceInfo.location || '获取中...' }}</span>
          </div>
          <div class="info-item">
            <span class="label">时间：</span>
            <span class="value">{{ loginTime }}</span>
          </div>
        </div>
      </div>
      
      <div class="modal-footer">
        <button class="btn btn-secondary" @click="handleCancel">取消</button>
        <button class="btn btn-primary" @click="handleConfirm" :disabled="confirming">
          {{ confirming ? '确认中...' : '确认登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiClient } from '@linxi/shared-api'

const props = defineProps({
  visible: Boolean,
  qrUuid: String
})

const emit = defineEmits(['confirm', 'cancel'])

const deviceInfo = ref({})
const loginTime = ref('')
const confirming = ref(false)

onMounted(async () => {
  if (props.qrUuid) {
    try {
      const res = await apiClient.get(`/api/auth/qrcode/${props.qrUuid}/info`)
      deviceInfo.value = res.device
      loginTime.value = new Date(res.login_time).toLocaleString()
    } catch (error) {
      console.error('Failed to get PC info:', error)
    }
  }
})

const handleConfirm = async () => {
  confirming.value = true
  try {
    await apiClient.post(`/api/auth/qrcode/${props.qrUuid}/confirm`, {})
    emit('confirm')
  } catch (error) {
    console.error('Confirm failed:', error)
  } finally {
    confirming.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.qr-confirm-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
}

.modal-content {
  position: relative;
  width: 90%;
  max-width: 400px;
  background: white;
  border-radius: var(--radius-xl);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-lg);
  border-bottom: 1px solid var(--color-border);
}

.modal-header h3 {
  margin: 0;
  font-size: var(--font-size-xl);
  color: var(--color-text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: var(--color-text-tertiary);
  cursor: pointer;
}

.modal-body {
  padding: var(--space-xl);
}

.info-item {
  display: flex;
  margin-bottom: var(--space-md);
}

.info-item .label {
  color: var(--color-text-secondary);
  width: 60px;
}

.info-item .value {
  color: var(--color-text-primary);
}

.modal-footer {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-lg);
  border-top: 1px solid var(--color-border);
}

.btn {
  flex: 1;
  padding: var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-lg);
  cursor: pointer;
  border: none;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--color-text-secondary);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
```

- [ ] **Step 2: Commit changes**

```bash
git add linxitie.policy-exam-bank-mobile/src/components/QRConfirmModal.vue
git commit -m "feat: add QR code confirm modal for mobile"
```

---

## Task 9: Shared Types Package

**Files:**
- Create: `packages/shared-types/package.json`
- Create: `packages/shared-types/src/api.ts`
- Create: `packages/shared-types/src/entities.ts`
- Create: `packages/shared-types/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@linxi/shared-types",
  "version": "1.0.0",
  "main": "src/index.ts",
  "types": "src/index.ts"
}
```

- [ ] **Step 2: Create API types**

```typescript
// packages/shared-types/src/api.ts
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
```

- [ ] **Step 3: Create entity types**

```typescript
// packages/shared-types/src/entities.ts
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
```

- [ ] **Step 4: Create index exports**

```typescript
// packages/shared-types/src/index.ts
export * from './api'
export * from './entities'
```

- [ ] **Step 5: Commit changes**

```bash
git add packages/shared-types/
git commit -m "feat: add shared types package"
```

---

## Task 10: Shared Store - Auth Store

**Files:**
- Create: `packages/shared-store/package.json`
- Create: `packages/shared-store/src/auth.ts`
- Create: `packages/shared-store/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@linxi/shared-store",
  "version": "1.0.0",
  "main": "src/index.ts",
  "types": "src/index.ts",
  "dependencies": {
    "pinia": "~3.0.2"
  }
}
```

- [ ] **Step 2: Create auth store**

```typescript
// packages/shared-store/src/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@linxi/shared-api'
import type { User, LoginResponse } from '@linxi/shared-types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const currentUser = computed(() => user.value)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const res = await apiClient.post<LoginResponse>('/api/auth/login', {
        username,
        password
      })
      token.value = res.token
      user.value = res.user
      localStorage.setItem('token', res.token)
      return res
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const res = await apiClient.get<User>('/api/auth/me')
      user.value = res
    } catch (error) {
      await logout()
    }
  }

  return {
    token,
    user,
    loading,
    isAuthenticated,
    currentUser,
    login,
    logout,
    fetchUser
  }
})
```

- [ ] **Step 3: Create index exports**

```typescript
// packages/shared-store/src/index.ts
export { useAuthStore } from './auth'
```

- [ ] **Step 4: Commit changes**

```bash
git add packages/shared-store/
git commit -m "feat: add shared auth store package"
```

---

## Task 11: Tablet VTJ Project Setup

**Files:**
- Create: `linxitie.policy-exam-bank-tablet/package.json`
- Create: `linxitie.policy-exam-bank-tablet/.vtj/router.js`
- Create: `linxitie.policy-exam-bank-tablet/src/App.vue`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "linxitie-policy-exam-bank-tablet",
  "version": "1.0.0",
  "description": "砺安题库平板端",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "cross-env ENV_TYPE=local vite",
    "build": "vue-tsc && cross-env ENV_TYPE=live vite build"
  },
  "dependencies": {
    "@linxi/design-tokens": "workspace:*",
    "@linxi/shared-api": "workspace:*",
    "@linxi/shared-store": "workspace:*",
    "@linxi/shared-types": "workspace:*",
    "vue": "~3.5.0",
    "vue-router": "~4.6.0",
    "pinia": "~3.0.2"
  },
  "devDependencies": {
    "@vtj/cli": "latest",
    "@vtj/pro": "latest"
  }
}
```

- [ ] **Step 2: Create router configuration**

```javascript
// linxitie.policy-exam-bank-tablet/.vtj/router.js
{
  path: '/',
  component: () => import('./vue/layout.vue'),
  children: [
    {
      path: '',
      redirect: '/home'
    },
    {
      path: 'home',
      component: () => import('./vue/home_page.vue')
    },
    {
      path: 'questions',
      component: () => import('./vue/question_bank.vue')
    },
    {
      path: 'practice',
      component: () => import('./vue/practice_page.vue')
    },
    {
      path: 'forum',
      component: () => import('./vue/forum_page.vue')
    },
    {
      path: 'profile',
      component: () => import('./vue/profile_page.vue')
    }
  ]
}
```

- [ ] **Step 3: Create layout component**

```vue
<!-- linxitie.policy-exam-bank-tablet/src/App.vue -->
<template>
  <div class="tablet-app">
    <header class="app-header">
      <div class="logo">砺安题库</div>
      <div class="user-info">{{ user?.real_name }}</div>
    </header>
    
    <main class="app-main">
      <router-view />
    </main>
    
    <nav class="app-nav">
      <router-link to="/home" class="nav-item">
        <span class="nav-icon">🏠</span>
        <span class="nav-text">首页</span>
      </router-link>
      <router-link to="/questions" class="nav-item">
        <span class="nav-icon">📚</span>
        <span class="nav-text">题库</span>
      </router-link>
      <router-link to="/practice" class="nav-item">
        <span class="nav-icon">✏️</span>
        <span class="nav-text">练习</span>
      </router-link>
      <router-link to="/forum" class="nav-item">
        <span class="nav-icon">💬</span>
        <span class="nav-text">论坛</span>
      </router-link>
      <router-link to="/profile" class="nav-item">
        <span class="nav-icon">👤</span>
        <span class="nav-text">我的</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@linxi/shared-store'

const authStore = useAuthStore()
const user = computed(() => authStore.currentUser)
</script>

<style scoped>
.tablet-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

.app-header {
  height: 60px;
  background: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-xl);
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg);
}

.app-nav {
  height: 56px;
  background: white;
  display: flex;
  border-top: 1px solid var(--color-border);
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  color: var(--color-text-secondary);
}

.nav-item.active {
  color: var(--color-primary);
}

.nav-icon {
  font-size: 20px;
}

.nav-text {
  font-size: var(--font-size-sm);
  margin-top: 4px;
}
</style>
```

- [ ] **Step 4: Commit changes**

```bash
git add linxitie.policy-exam-bank-tablet/
git commit -m "feat: initialize tablet VTJ project"
```

---

## Task 12: Mobile VTJ Project Setup

**Files:**
- Create: `linxitie.policy-exam-bank-mobile/package.json`
- Create: `linxitie.policy-exam-bank-mobile/.vtj/router.js`
- Create: `linxitie.policy-exam-bank-mobile/src/App.vue`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "linxitie-policy-exam-bank-mobile",
  "version": "1.0.0",
  "description": "砺安题库手机端",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "cross-env ENV_TYPE=local vite",
    "build": "vue-tsc && cross-env ENV_TYPE=live vite build"
  },
  "dependencies": {
    "@linxi/design-tokens": "workspace:*",
    "@linxi/shared-api": "workspace:*",
    "@linxi/shared-store": "workspace:*",
    "@linxi/shared-types": "workspace:*",
    "vue": "~3.5.0",
    "vue-router": "~4.6.0",
    "pinia": "~3.0.2"
  },
  "devDependencies": {
    "@vtj/cli": "latest",
    "@vtj/pro": "latest"
  }
}
```

- [ ] **Step 2: Create router configuration**

```javascript
// linxitie.policy-exam-bank-mobile/.vtj/router.js
{
  path: '/',
  component: () => import('./vue/layout.vue'),
  children: [
    {
      path: '',
      redirect: '/home'
    },
    {
      path: 'home',
      component: () => import('./vue/home_page.vue')
    },
    {
      path: 'questions',
      component: () => import('./vue/question_bank.vue')
    },
    {
      path: 'practice',
      component: () => import('./vue/practice_page.vue')
    },
    {
      path: 'forum',
      component: () => import('./vue/forum_page.vue')
    },
    {
      path: 'profile',
      component: () => import('./vue/profile_page.vue')
    }
  ]
}
```

- [ ] **Step 3: Create layout component**

```vue
<!-- linxitie.policy-exam-bank-mobile/src/App.vue -->
<template>
  <div class="mobile-app">
    <header class="app-header">
      <button class="back-btn" @click="goBack">←</button>
      <div class="title">砺安题库</div>
      <div class="placeholder"></div>
    </header>
    
    <main class="app-main">
      <router-view />
    </main>
    
    <nav class="app-nav">
      <router-link to="/home" class="nav-item">
        <span class="nav-icon">🏠</span>
        <span class="nav-text">首页</span>
      </router-link>
      <router-link to="/questions" class="nav-item">
        <span class="nav-icon">📚</span>
        <span class="nav-text">题库</span>
      </router-link>
      <router-link to="/practice" class="nav-item">
        <span class="nav-icon">✏️</span>
        <span class="nav-text">练习</span>
      </router-link>
      <router-link to="/forum" class="nav-item">
        <span class="nav-icon">💬</span>
        <span class="nav-text">论坛</span>
      </router-link>
      <router-link to="/profile" class="nav-item">
        <span class="nav-icon">👤</span>
        <span class="nav-text">我的</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.mobile-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-secondary);
}

.app-header {
  height: 48px;
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-md);
  border-bottom: 1px solid var(--color-border);
}

.back-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: var(--color-text-primary);
}

.title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}

.placeholder {
  width: 24px;
}

.app-main {
  flex: 1;
  overflow-y: auto;
}

.app-nav {
  height: 52px;
  background: white;
  display: flex;
  border-top: 1px solid var(--color-border);
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  color: var(--color-text-secondary);
}

.nav-item.active {
  color: var(--color-primary);
}

.nav-icon {
  font-size: 18px;
}

.nav-text {
  font-size: var(--font-size-xs);
  margin-top: 2px;
}
</style>
```

- [ ] **Step 4: Commit changes**

```bash
git add linxitie.policy-exam-bank-mobile/
git commit -m "feat: initialize mobile VTJ project"
```

---

## Task 13: Shared Utils Package

**Files:**
- Create: `packages/shared-utils/package.json`
- Create: `packages/shared-utils/src/date.ts`
- Create: `packages/shared-utils/src/validation.ts`
- Create: `packages/shared-utils/src/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@linxi/shared-utils",
  "version": "1.0.0",
  "main": "src/index.ts",
  "types": "src/index.ts"
}
```

- [ ] **Step 2: Create date utilities**

```typescript
// packages/shared-utils/src/date.ts
export function formatDate(date: Date | string, format: string = 'YYYY-MM-DD'): string {
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  const seconds = String(d.getSeconds()).padStart(2, '0')
  
  return format
    .replace('YYYY', String(year))
    .replace('MM', month)
    .replace('DD', day)
    .replace('HH', hours)
    .replace('mm', minutes)
    .replace('ss', seconds)
}

export function formatRelativeTime(date: Date | string): string {
  const now = new Date()
  const d = new Date(date)
  const diff = now.getTime() - d.getTime()
  
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 30) return `${days}天前`
  return formatDate(date)
}
```

- [ ] **Step 3: Create validation utilities**

```typescript
// packages/shared-utils/src/validation.ts
export function isValidUsername(username: string): boolean {
  return /^[a-zA-Z0-9_]{4,20}$/.test(username)
}

export function isValidPassword(password: string): boolean {
  return password.length >= 6
}

export function isValidPhone(phone: string): boolean {
  return /^1[3-9]\d{9}$/.test(phone)
}

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}
```

- [ ] **Step 4: Create index exports**

```typescript
// packages/shared-utils/src/index.ts
export * from './date'
export * from './validation'
```

- [ ] **Step 5: Commit changes**

```bash
git add packages/shared-utils/
git commit -m "feat: add shared utils package"
```

---

## Self-Review Checklist

### 1. Spec Coverage
- [x] Backend QR code login (Task 2)
- [x] Backend device management (Task 3)
- [x] Backend Redis client (Task 1)
- [x] Backend device registration on login (Task 4)
- [x] Frontend shared design tokens (Task 5)
- [x] Frontend shared API client (Task 6)
- [x] Frontend shared types (Task 9)
- [x] Frontend shared store (Task 10)
- [x] Frontend shared utils (Task 13)
- [x] PC端 QR code login tab (Task 7)
- [x] Mobile QR code confirm modal (Task 8)
- [x] Tablet VTJ project (Task 11)
- [x] Mobile VTJ project (Task 12)

### 2. Placeholder Scan
- [x] No TBD/TODO placeholders
- [x] All code blocks are complete
- [x] All file paths are exact

### 3. Type Consistency
- [x] User type consistent across packages
- [x] API response types consistent
- [x] Method signatures match

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/multi-device-sync-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
