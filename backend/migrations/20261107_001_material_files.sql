-- B1（2026-11-07）：资料原件留档表
--
-- 落地方式说明（勿误以为要手动跑）：
--   `app/main.py` 启动时执行 `Base.metadata.create_all(bind=engine)`，
--   `app/models/models.py` 里的 `MaterialFile` 会**自动建表**；本文件是 DDL 存档，
--   供 DBA/回滚/其它环境（MySQL 出口）对照，也便于 code review 直接看结构。
--
-- 存储口径（用户 2026-11-07 裁定）：
--   · 物理文件放 `<SQLITE_PATH 同级>/material_files/<sha256前2位>/<sha256>.<ext>`；
--     **不在 /uploads 静态目录**，只能经 `GET /api/materials/files/{id}/download` 鉴权下载；
--   · 内容寻址：同一 sha256 只存一份，多条资料可引用同一物理文件；
--   · 删除资料只删本表行，物理文件由清理脚本回收。
--
-- 兼容性：新表，不改既有表；旧代码读不到本表也不受影响（回滚=删表即可，无数据迁移）。
CREATE TABLE IF NOT EXISTS material_file (
    file_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id  INTEGER NOT NULL,
    role         VARCHAR(20)  DEFAULT 'primary',   -- primary=主文件 / attachment=附件
    file_name    VARCHAR(255),
    file_ext     VARCHAR(10),
    mime_type    VARCHAR(100),
    file_size    BIGINT,
    sha256       VARCHAR(64),
    storage_path VARCHAR(500),                     -- 相对 material_files 根目录，禁止绝对路径
    source       VARCHAR(20)  DEFAULT 'import',     -- import / upload
    uploader_id  BIGINT,
    create_time  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES study_material (material_id),
    FOREIGN KEY (uploader_id) REFERENCES sys_user (user_id)
);

CREATE INDEX IF NOT EXISTS idx_material_file_material ON material_file (material_id);
CREATE INDEX IF NOT EXISTS idx_material_file_sha ON material_file (sha256);
-- 同一条资料、同一角色、同一份内容只登记一次
CREATE UNIQUE INDEX IF NOT EXISTS uq_material_file_material_sha_role
    ON material_file (material_id, sha256, role);
