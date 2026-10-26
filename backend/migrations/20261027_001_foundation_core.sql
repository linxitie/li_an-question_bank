-- 20261027_001_foundation_core.sql
-- F1 一致性内核：7 张新表（终态架构 §6.2）。只增不改，任何既有表不动。
-- 幂等：全部 IF NOT EXISTS，可重复执行（apply.py --apply 第二次应 changed=0）。

-- 1) 事务性发件箱：与业务写同事务
CREATE TABLE IF NOT EXISTS foundation_outbox (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id        VARCHAR(32)  NOT NULL UNIQUE,
  event_name      VARCHAR(64)  NOT NULL,
  schema_version  INTEGER      NOT NULL DEFAULT 1,
  aggregate_type  VARCHAR(64)  NOT NULL,
  aggregate_id    VARCHAR(64)  NOT NULL,
  aggregate_ver   INTEGER      NOT NULL DEFAULT 0,
  dedupe_key      VARCHAR(128),
  payload         TEXT         NOT NULL,
  producer        VARCHAR(64)  NOT NULL,
  trace_id        VARCHAR(64),
  occurred_at     DATETIME     NOT NULL,
  status          VARCHAR(16)  NOT NULL DEFAULT 'pending',
  attempts        INTEGER      NOT NULL DEFAULT 0,
  next_retry_at   DATETIME,
  dispatched_at   DATETIME,
  last_error      TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_outbox_dedupe
  ON foundation_outbox(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_outbox_status_id ON foundation_outbox(status, id);
CREATE INDEX IF NOT EXISTS ix_outbox_aggregate
  ON foundation_outbox(aggregate_type, aggregate_id, aggregate_ver);

-- 2) 投影游标：每个投影消费到哪一条
CREATE TABLE IF NOT EXISTS foundation_projection_cursor (
  projection      VARCHAR(64) NOT NULL,
  last_outbox_id  INTEGER     NOT NULL DEFAULT 0,
  updated_at      DATETIME    NOT NULL,
  status          VARCHAR(16) NOT NULL DEFAULT 'idle',
  lag_seconds     INTEGER     NOT NULL DEFAULT 0,
  PRIMARY KEY (projection)
);

-- 3) 已处理事件：跨进程/多实例去重（F2 起启用）
CREATE TABLE IF NOT EXISTS foundation_inbox (
  consumer      VARCHAR(64) NOT NULL,
  event_id      VARCHAR(32) NOT NULL,
  event_name    VARCHAR(64) NOT NULL,
  processed_at  DATETIME    NOT NULL,
  PRIMARY KEY (consumer, event_id)
);

-- 4) 投影状态：按聚合记录已投影版本与校验和
CREATE TABLE IF NOT EXISTS foundation_projection_state (
  projection      VARCHAR(64) NOT NULL,
  aggregate_type  VARCHAR(64) NOT NULL,
  aggregate_id    VARCHAR(64) NOT NULL,
  source_version  INTEGER     NOT NULL,
  checksum        VARCHAR(64),
  updated_at      DATETIME    NOT NULL,
  PRIMARY KEY (projection, aggregate_type, aggregate_id)
);

-- 5) 对账运行记录
CREATE TABLE IF NOT EXISTS foundation_reconcile_run (
  run_id       VARCHAR(32) PRIMARY KEY,
  scope        VARCHAR(64) NOT NULL,
  mode         VARCHAR(16) NOT NULL,
  started_at   DATETIME    NOT NULL,
  finished_at  DATETIME,
  checked      INTEGER     NOT NULL DEFAULT 0,
  drifted      INTEGER     NOT NULL DEFAULT 0,
  repaired     INTEGER     NOT NULL DEFAULT 0,
  report_path  VARCHAR(255),
  status       VARCHAR(16) NOT NULL DEFAULT 'running'
);

-- 6) 回填断点：可续跑、可 dry-run
CREATE TABLE IF NOT EXISTS foundation_backfill_state (
  source      VARCHAR(64) NOT NULL,
  cursor      VARCHAR(128) NOT NULL DEFAULT '',
  total       INTEGER     NOT NULL DEFAULT 0,
  done        INTEGER     NOT NULL DEFAULT 0,
  updated_at  DATETIME    NOT NULL,
  PRIMARY KEY (source)
);

-- 7) 导入预览外置引用：大 JSON 搬出主库，只留指针（§18）
CREATE TABLE IF NOT EXISTS foundation_preview_ref (
  import_id        INTEGER PRIMARY KEY,
  ref_path         VARCHAR(255) NOT NULL,
  bytes            INTEGER     NOT NULL DEFAULT 0,
  sha256           VARCHAR(64),
  questions        INTEGER     NOT NULL DEFAULT 0,
  status_at_purge  VARCHAR(16) NOT NULL,
  purged_at        DATETIME    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_preview_ref_purged
  ON foundation_preview_ref(purged_at);
