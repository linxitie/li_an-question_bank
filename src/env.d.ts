/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module '*/*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module '*/*/*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module '*/vue/*.vue' {
  import type { DefineComponent } from 'vue';
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare namespace NodeJS {
  interface ProcessEnv {
    [key: string]: any;
  }
}

declare global {
  interface Window {
    __VTJ_AUTH__: {
      getState: () => any;
      isTokenExpired: (state: any) => boolean;
      ensureAuth: () => Promise<boolean>;
      refreshAccessToken: () => Promise<boolean>;
      login: (username: string, password: string, clientType?: string) => Promise<{ success: boolean; message: string }>;
      loginWithToken: (accessToken: string, refreshToken?: string, username?: string) => { success: boolean; message: string };
      logout: () => void;
      getAuthHeaders: () => { Authorization?: string };
      getJsonHeaders: () => Record<string, string>;
      apiFetch: (url: string, options?: any) => Promise<Response>;
      getUsername: () => string | null;
      isLoggedIn: () => boolean;
      getUserRole: () => string | null;
      hasRole: (role: string) => boolean;
      hasPermission: (permission: string) => boolean;
      getPermissions: () => string[];
      getRoleLevel: () => number;
      parseUserInfo: () => { role: string | null; roleLevel: number; permissions: string[]; userId?: number | null };
      initSyncSocket: () => void;
      closeSyncSocket: () => void;
    };
  }
}

declare module 'vue' {
  interface ComponentCustomProperties {
    $uploader: any;
    $reqeust: any;
    $apis: any;
    $libs: any;
  }
}

export {};

/** 构建时由 vite.config.ts 注入的 git 短 SHA 与构建时间（全局，供 main.ts 做版本自检） */
declare global {
  const __BUILD_SHA__: string;
  const __BUILD_TIME__: string;

  interface Window {
    /** 前端构建版本；backend 为后端 /health 返回的 revision */
    __APP_BUILD__?: { sha: string; time: string; backend?: string };
    /** 前后端版本不一致时存在，便于排查「功能开发中」这类旧产物问题 */
    __VERSION_MISMATCH__?: { frontend: string; backend: string };
  }
}
