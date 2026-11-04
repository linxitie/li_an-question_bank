-- B2：分享与领取（复制语义）
-- 2026-10-27
CREATE TABLE IF NOT EXISTS material_share (
  share_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  material_id   INTEGER NOT NULL,               -- 源卡片
  owner_id      INTEGER NOT NULL,               -- 分享者
  scope         TEXT    DEFAULT 'public',       -- public | org（预留）
  status        INTEGER DEFAULT 1,              -- 1 可领取 / 0 已撤回
  adopted_count INTEGER DEFAULT 0,              -- 被领取次数
  create_time   DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_material_share_material ON material_share (material_id);
CREATE INDEX IF NOT EXISTS idx_material_share_owner ON material_share (owner_id);

CREATE TABLE IF NOT EXISTS material_adopt_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  share_id    INTEGER NOT NULL,
  user_id     INTEGER NOT NULL,
  created_id  INTEGER NOT NULL,                 -- 复制出的新卡
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_adopt_share_user ON material_adopt_log (share_id, user_id);
