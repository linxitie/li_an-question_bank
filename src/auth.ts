/**
 * 砺安题库 - 共享认证模块
 *
 * 统一管理 JWT token 的存储、刷新、过期检测。
 * 所有 VTJ 组件通过 window.__VTJ_AUTH__ 访问。
 *
 * 使用方式（在任意组件的 mounted/methods 中）：
 *   const auth = window.__VTJ_AUTH__;
 *   await auth.ensureAuth();           // 确保有有效 token
 *   const headers = auth.getJsonHeaders();  // 获取带认证的请求头
 *   fetch('/api/...', { headers }).then(...)
 */

(function () {
  'use strict';

  var STORAGE_KEY = '__VTJ_AUTH_STATE__';
  // token 到期前 10 分钟就开始尝试刷新
  var REFRESH_BUFFER_MS = 10 * 60 * 1000;
  // 自上次登录后超过此时间也强制检查
  var MAX_LOGIN_AGE_MS = 7 * 60 * 60 * 1000;

  /**
   * 从 localStorage 读取认证状态
   */
  function getState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { token: null, refreshToken: null, username: null, loginTime: null };
      return JSON.parse(raw);
    } catch (e) {
      return { token: null, refreshToken: null, username: null, loginTime: null };
    }
  }

  /**
   * 保存认证状态到 localStorage
   */
  function setState(state:any) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  /**
   * 判断 token 是否已过期或接近过期
   * 返回: true = 需要刷新, false = 仍然有效
   */
  function isTokenExpired(state:any) {
    if (!state.token || !state.loginTime) return true;

    // 方法1: 解析 JWT payload 中的 exp 字段
    try {
      var parts = state.token.split('.');
      if (parts.length === 3) {
        // 修复 base64 URL-safe 编码
        var payloadStr = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        // 补齐 padding
        while (payloadStr.length % 4 !== 0) payloadStr += '=';
        var payload = JSON.parse(atob(payloadStr));
        if (payload.exp) {
          var expMs = payload.exp * 1000;
          return Date.now() > expMs - REFRESH_BUFFER_MS;
        }
      }
    } catch (e) {
      // 解析失败, 使用 fallback
    }

    // 方法2: 根据登录时间判断
    return Date.now() - state.loginTime > MAX_LOGIN_AGE_MS;
  }

  /**
   * 正在进行的认证 Promise（防止重复请求）
   */
  var _authPromise: Promise<boolean> | null = null;

  /**
   * 确保用户已认证且有有效 token
   * 如果 token 过期，尝试用 refreshToken 刷新
   * 返回: true = 认证成功, false = 需要重新登录
   */
  async function ensureAuth() {
    // 如果正在认证中，复用同一个 Promise
    if (_authPromise) return _authPromise;

    var state = getState();

    // token 存在且未过期 → 直接返回
    if (state.token && !isTokenExpired(state)) {
      return true;
    }

    // token 过期但有 refreshToken → 尝试刷新
    if (state.refreshToken) {
      _authPromise = refreshAccessToken().then(function (ok) {
        _authPromise = null;
        return ok;
      }).catch(function () {
        _authPromise = null;
        return false;
      });
      return _authPromise;
    }

    // 无任何凭据
    return false;
  }

  /**
   * 使用 refreshToken 换取新的 accessToken
   */
  async function refreshAccessToken() {
    var state = getState();
    if (!state.refreshToken) return false;

    try {
      var res = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: state.refreshToken })
      });

      if (!res.ok) {
        logout();
        return false;
      }

      var data = await res.json();
      state.token = data.access_token;
      state.loginTime = Date.now();
      // 如果后端也返回了新的 refreshToken，则更新
      if (data.refresh_token) {
        state.refreshToken = data.refresh_token;
      }
      setState(state);
      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * 用户登录
   * @param {string} username 用户名
   * @param {string} password 密码
   * @returns {Promise<{success: boolean, message: string}>}
   */
  async function login(username: string, password: string, clientType?: string) {
    try {
      // 使用 OAuth2 标准格式（clientType 用于三端分离：web/mobile/tablet，移动/平板端仅学生可登录）
      var formBody = new URLSearchParams();
      formBody.append('username', username);
      formBody.append('password', password);
      if (clientType) formBody.append('client_type', clientType);

      var res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formBody.toString()
      });

      if (!res.ok) {
        var errData = null;
        try { errData = await res.json(); } catch (e) {}
        return {
          success: false,
          message: (errData && errData.detail) ? errData.detail : '登录失败 (HTTP ' + res.status + ')'
        };
      }

      var data = await res.json();
      setState({
        token: data.access_token,
        refreshToken: data.refresh_token || '',
        username: username,
        loginTime: Date.now()
      });
      initSyncSocket();
      return { success: true, message: '登录成功' };
    } catch (e: any) {
      return { success: false, message: '网络错误: ' + (e.message || '连接失败') };
    }
  }

  /**
   * 扫码登录：直接用后端返回的 token 建立本地登录态。
   * PC 端轮询二维码状态拿到 confirmed 的 token 后调用此方法，
   * 避免前端手写 localStorage（否则 token 键不一致会导致登录态不生效）。
   */
  function loginWithToken(accessToken: string, refreshToken?: string, username?: string) {
    setState({
      token: accessToken,
      refreshToken: refreshToken || '',
      username: username || '',
      loginTime: Date.now()
    });
    initSyncSocket();
    return { success: true, message: '登录成功' };
  }

  /**
   * 退出登录
   */
  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    _authPromise = null;
    closeSyncSocket();
  }

  var _syncSocket: WebSocket | null = null;
  var _syncReconnectTimer: number | null = null;
  var _syncHeartbeatTimer: number | null = null;
  var _reconnectDelay = 5000; // 重连延迟，指数退避，封顶 60s

  /**
   * 建立 WebSocket 同步连接（三端实时同步）
   * 后端数据更新（爬取完成）后广播 sync 事件，前端监听后触发 __VTJ_SYNC__ 全局事件，
   * 各页面监听该事件刷新数据。
   */
  function initSyncSocket() {
    var state = getState();
    if (!state.token || isTokenExpired(state)) return;
    if (_syncSocket && (_syncSocket.readyState === 0 || _syncSocket.readyState === 1)) return;

    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var url = proto + '//' + window.location.host + '/ws/connect?token=' + encodeURIComponent(state.token);

    try {
      _syncSocket = new WebSocket(url);
    } catch (e) {
      _syncSocket = null;
      return;
    }

    _syncSocket.onopen = function () {
      _reconnectDelay = 5000; // 连接成功，重置退避
      startSyncHeartbeat();
    };

    _syncSocket.onmessage = function (ev: any) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg && msg.type === 'sync') {
          window.dispatchEvent(new CustomEvent('__VTJ_SYNC__', { detail: msg }));
        }
      } catch (e) { /* 忽略非 JSON 消息 */ }
    };

    _syncSocket.onclose = function () {
      _syncSocket = null;
      stopSyncHeartbeat();
      if (_syncReconnectTimer) clearTimeout(_syncReconnectTimer);
      _syncReconnectTimer = window.setTimeout(function () {
        if (isLoggedIn()) initSyncSocket();
      }, _reconnectDelay);
      _reconnectDelay = Math.min(_reconnectDelay * 2, 60000); // 指数退避，封顶 60s
    };

    _syncSocket.onerror = function () { /* onclose 会随之触发 */ };
  }

  function startSyncHeartbeat() {
    stopSyncHeartbeat();
    _syncHeartbeatTimer = window.setInterval(function () {
      if (_syncSocket && _syncSocket.readyState === 1) {
        try { _syncSocket.send(JSON.stringify({ type: 'heartbeat' })); } catch (e) {}
      }
    }, 30000); // 30s 心跳保活
  }

  function stopSyncHeartbeat() {
    if (_syncHeartbeatTimer) { clearInterval(_syncHeartbeatTimer); _syncHeartbeatTimer = null; }
  }

  function closeSyncSocket() {
    if (_syncReconnectTimer) { clearTimeout(_syncReconnectTimer); _syncReconnectTimer = null; }
    stopSyncHeartbeat();
    if (_syncSocket) {
      try { _syncSocket.close(); } catch (e) {}
      _syncSocket = null;
    }
  }

  /**
   * 获取认证请求头（仅 Authorization）
   * 会自动检查 token 是否过期，过期则清除并返回空
   */
  function getAuthHeaders() {
    var state = getState();
    if (state.token) {
      // 检查是否已过期
      if (isTokenExpired(state)) {
        // token 过期，清除并返回空
        logout();
        return {};
      }
      return { 'Authorization': 'Bearer ' + state.token };
    }
    return {};
  }

  /**
   * 获取 JSON 请求头（Content-Type + Authorization）
   * 会自动检查 token 过期
   */
  function getJsonHeaders() {
    var state = getState();
    var headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (state.token && !isTokenExpired(state)) {
      headers['Authorization'] = 'Bearer ' + state.token;
    }
    return headers;
  }

  /**
   * 带认证的 fetch 封装
   * 自动携带 token，遇到 401 尝试刷新后重试一次，仍然 401 则跳转登录
   *
   * @param {string} url
   * @param {object} options fetch 选项
   * @returns {Promise<Response>}
   */
  async function apiFetch(url: string, options?: any): Promise<Response> {
    options = options || {};
    var state = getState();

    // 自动添加认证头（仅当 token 未过期）
    if (state.token && !isTokenExpired(state)) {
      options.headers = options.headers || {};
      options.headers['Authorization'] = 'Bearer ' + state.token;
    }

    var res = await fetch(url, options);

    // 如果是 401 且有 refreshToken，尝试刷新后重试
    if (res.status === 401 && state.refreshToken) {
      var refreshed = await refreshAccessToken();
      if (refreshed) {
        state = getState();
        options.headers = options.headers || {};
        options.headers['Authorization'] = 'Bearer ' + state.token;
        res = await fetch(url, options);
      }
    }

    // 重试后仍然 401 → 清除凭据并跳转登录
    if (res.status === 401) {
      logout();
      // 跳转到登录页（使用 replace 避免返回）
      try {
        var currentPath = window.location.hash.replace('#', '') || '/';
        window.location.href = '/#/login?redirect=' + encodeURIComponent(currentPath);
      } catch(e) {
        window.location.href = '/#/login';
      }
    }

    return res;
  }

  /**
   * 获取当前用户名（如果已登录）
   */
  function getUsername() {
    return getState().username;
  }

  /**
   * 是否已登录且有有效 token
   * 三端分离：Token 必须含 user_type 字段，旧格式自动失效
   */
  function isLoggedIn() {
    var state = getState();
    if (!state.token || isTokenExpired(state)) return false;
    // 校验 token 格式：必须含 user_type
    var info = parseUserInfo();
    if (!info.role) return false;
    return true;
  }

  // ====== 三端分离架构：角色与权限 ======

  /**
   * 从 JWT payload 解析用户角色和权限信息
   * 返回: { role, roleLevel, permissions[] }
   */
  function parseUserInfo() {
    var state = getState();
    if (!state.token) return { role: null, roleLevel: 0, permissions: [] };
    try {
      var parts = state.token.split('.');
      if (parts.length === 3) {
        var payloadStr = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        while (payloadStr.length % 4 !== 0) payloadStr += '=';
        var payload = JSON.parse(atob(payloadStr));
        return {
          role: payload.user_type || null,
          roleLevel: payload.role_level || 0,
          permissions: payload.permissions || [],
          userId: payload.user_id || null,
        };
      }
    } catch (e) {}
    return { role: null, roleLevel: 0, permissions: [] };
  }

  /**
   * 获取当前用户角色
   */
  function getUserRole() {
    return parseUserInfo().role;
  }

  /**
   * 检查当前用户是否拥有指定角色
   */
  function hasRole(role: string) {
    var info = parseUserInfo();
    if (info.role === 'admin' && info.roleLevel >= 2) return true;
    return info.role === role;
  }

  /**
   * 检查当前用户是否有指定权限
   */
  function hasPermission(permission: string) {
    var info = parseUserInfo();
    return info.permissions.indexOf(permission) !== -1;
  }

  /**
   * 获取用户角色级别 (0=学生, 1=教师, 2=管理员, 3=超级管理员)
   */
  function getRoleLevel() {
    return parseUserInfo().roleLevel;
  }

  // ====== 挂载到全局 ======
  window.__VTJ_AUTH__ = {
    getState: getState,
    isTokenExpired: isTokenExpired,
    ensureAuth: ensureAuth,
    refreshAccessToken: refreshAccessToken,
    login: login,
    loginWithToken: loginWithToken,
    logout: logout,
    getAuthHeaders: getAuthHeaders,
    getJsonHeaders: getJsonHeaders,
    apiFetch: apiFetch,
    getUsername: getUsername,
    isLoggedIn: isLoggedIn,
    // 三端分离新增
    getUserRole: getUserRole,
    hasRole: hasRole,
    hasPermission: hasPermission,
    getRoleLevel: getRoleLevel,
    parseUserInfo: parseUserInfo,
    // 三端实时同步
    initSyncSocket: initSyncSocket,
    closeSyncSocket: closeSyncSocket,
  };

  // 页面加载时若已登录，自动建立同步连接
  if (isLoggedIn()) {
    initSyncSocket();
  }

})();

export {};
