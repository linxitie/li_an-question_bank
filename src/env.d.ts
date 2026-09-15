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
