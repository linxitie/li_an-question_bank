-- F5 图投影（可重建，不是第二事实源）
-- 节点/边全部由 knowledge_point、question_knowledge、question_bank 重新生成；
-- 业务层不得直接写这两张表，只允许 GraphStore / 回填脚本写入。
CREATE TABLE IF NOT EXISTS foundation_graph_node (
    label      TEXT NOT NULL,
    key        TEXT NOT NULL,
    props      TEXT NOT NULL DEFAULT '{}',
    version    INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (label, key)
);
CREATE TABLE IF NOT EXISTS foundation_graph_edge (
    rel       TEXT NOT NULL,
    src_label TEXT NOT NULL,
    src_key   TEXT NOT NULL,
    dst_label TEXT NOT NULL,
    dst_key   TEXT NOT NULL,
    props     TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (rel, src_label, src_key, dst_label, dst_key)
);
CREATE INDEX IF NOT EXISTS ix_graph_edge_src ON foundation_graph_edge(src_label, src_key);
CREATE INDEX IF NOT EXISTS ix_graph_edge_dst ON foundation_graph_edge(dst_label, dst_key);
