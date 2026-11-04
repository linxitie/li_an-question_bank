-- S2：徽章档位快照
-- 说明：user_achievement.tier 为历史字段（1 铜 … 5 钻石），语义与新五档不一致；
-- 新增 tier_snapshot 存"获得时的档位索引 0–4"，与 badge_service.TIERS 对齐。
ALTER TABLE user_achievement ADD COLUMN tier_snapshot INTEGER;