# Implementation Plan — Obsidian Daily Quote Favorites (每日金句大完善)

> **Branch:** `obsidian-quote-favorite`
> **Spec:** `docs/superpowers/specs/obsidian-quote-favorite/spec.md`
> **DB:** SQLite dev (`backend/.env` → `SQLITE_PATH=./data/question_bank.db`) · MySQL prod (via main.py auto-migration pattern)

## Context

Obsidian daily quotes are read live from the filesystem (`backend/app/api/v1/quotes.py:98` `_read_obsidian_quotes()`), never stored in DB. The frontend `toggleQuoteFavorite()` (`quote_banner.vue:203`) silently exits when `quoteId === 0`, so Obsidian quotes can't be favorited. Also `/api/collection/news-favorites` only surfaces `QuoteFavorite JOIN EssayQuote` rows, so even DB-favorited Obsidian quotes wouldn't show on the favorites page.

**Solution (per spec):** stable filename-based ID (`obsidian_<filename>`), extend `quote_favorite` with `obsidian_source`, new toggle endpoint `POST /api/quotes/obsidian/{obsidian_source}/favorite`, merged favorites list, frontend branching on `obsidianSource`.

### Key deviations from spec (verified against actual code — implementer MUST apply these)

1. **`OBSIDIAN_QUOTE_DIR` is NOT in `settings`.** It is a module constant in `quotes.py:28-32`. `collection.py` must import it + `_parse_obsidian_quote` from `..v1.quotes` (`from .quotes import OBSIDIAN_QUOTE_DIR, _parse_obsidian_quote`) instead of `settings.OBSIDIAN_QUOTE_DIR`.
2. **favorites.vue spec gap:** `removeNewsFavorite(item)` needs `item.fav_type / item.quote_id / item.obsidian_source`, but `viewNewsDetail` (line 218-233) currently builds `newsDetail` without these fields, and the modal button (line 96) passes only `state.newsDetail.id`. The plan fixes both so the obsidian removal path works.
3. **SQLite `NOT NULL` constraint:** dev DB has `quote_id` NOT NULL; SQLite rejects inserting `NULL`. A table-rebuild migration (not a plain `ALTER TABLE ADD COLUMN`) is required. Added as Task B2.
4. **Regex is safe for CJK:** Python 3 `\w` matches CJK ideographs by default, so `^[\w\-\.]+\.md$` accepts `2026-08-14-金句-050.md`. No change needed.
5. **Route ordering:** `/api/quotes/obsidian/{obsidian_source}/favorite` (3 segments) does not collide with `/api/quotes/{quote_id}/favorite` (2 segments). No reordering required.

---

## Task Dependency Graph

| Task | Depends On | Reason |
|------|------------|--------|
| B1: Modify `QuoteFavorite` model | None | New columns/constraints must exist before code or tests use them |
| B2: DB migration (main.py auto-migration) | B1 | Migration must match the model schema |
| B3: Update `get_daily_quote` | B1 | Queries `obsidian_source` column |
| B4: Add `toggle_obsidian_quote_favorite` | B1 | Inserts rows with `obsidian_source` |
| B5: Update `collection.py` merged favorites | B1, B3 | Uses `obsidian_source` column + `_read_obsidian_quote_by_filename` |
| B6: Backend pytest suite (TDD, green) | B3, B4, B5 | Tests exercise the new/updated endpoints |
| F1: Update `quote_banner.vue` | B3, B4 | Consumes `obsidian_id/obsidian_source/source_type` + new endpoint |
| F2: Sync `quote_banner.json` DSL | F1 | DSL must mirror script state/methods + bumped version |
| F3: Update `favorites.vue` | B5 | Consumes merged favorites + obsidian un-favorite endpoint |
| F4: Frontend build verification | F1, F2, F3 | Compiles/type-checks all frontend changes |

## Parallel Execution Graph

```
Wave 1 (start immediately):
└── B1: Modify QuoteFavorite model (models.py)

Wave 2 (after B1):
├── B2: DB migration in main.py
├── B3: get_daily_quote obsidian fields + favorited-by-filename
└── B4: New obsidian favorite toggle endpoint

Wave 3 (after B2, B3):
└── B5: collection.py merged favorites + helper

Wave 4 (after B3, B4, B5 — all backend green before frontend):
├── B6: Backend pytest suite (write tests + run → green)
├── F1: quote_banner.vue (state + refreshQuote + toggleQuoteFavorite)
└── F3: favorites.vue (viewNewsDetail + removeNewsFavorite + modal)

Wave 5 (after F1, F3):
└── F2: Sync quote_banner.json DSL + version bump

Wave 6 (after F1, F2, F3):
└── F4: Frontend build verification (vue-tsc + vite build)

Critical path: B1 → B3/B4 → B6 → F1 → F2 → F4
Parallel speedup: ~40% via Wave 2/4 fan-out
```

---

## Tasks

### Task B1: Extend `QuoteFavorite` model
**Files:** `backend/app/models/models.py:1473-1487`
- `quote_id`: `nullable=False` → `nullable=True`
- Add: `obsidian_source = Column(String(200), nullable=True, comment="Obsidian 金句来源标识（文件名）")`
- Add to `__table_args__`: `UniqueConstraint("user_id", "obsidian_source", name="uq_user_obsidian_fav")`

**Verification:** `python -c "from app.models.models import QuoteFavorite; from sqlalchemy import inspect; print([c.name for c in inspect(QuoteFavorite).columns])"` → contains `obsidian_source`, and `quote_id.nullable is True`.

**Delegation:** Category `quick` · Skills: `[]`

---

### Task B2: Auto-migration for `quote_favorite` in `main.py`
**Files:** `backend/app/main.py` (add block after the `sys_user` auto-migration section, ~line 169)
Add a lifespan auto-migration block using `PRAGMA table_info(quote_favorite)` check for the `quote_id` `notnull` flag. When `obsidian_source` is missing **or** `quote_id` is still NOT NULL, rebuild the table.

**Verification:** Run `python -c "import app.main"` then `PRAGMA table_info(quote_favorite)` shows `quote_id` `notnull=0` and `obsidian_source` present; existing rows preserved.

**Delegation:** Category `quick` · Skills: `[]`

---

### Task B3: Update `get_daily_quote` to return obsidian fields
**Files:** `backend/app/api/v1/quotes.py:154-177` (obsidian branch)
Replace the content-match favorited query (lines 161-167) with an `obsidian_source` query, and add fields: `obsidian_id`, `obsidian_source`, `source_type`.

**Verification:** `GET /api/quotes/quote/daily` returns `obsidian_id`, `obsidian_source`, `source_type:'obsidian'` when vault is reachable.

**Delegation:** Category `quick` · Skills: `[]`

---

### Task B4: Add `toggle_obsidian_quote_favorite` endpoint
**Files:** `backend/app/api/v1/quotes.py` (after `toggle_quote_favorite`, ~line 352)
Add the endpoint exactly per spec §4.1 (regex `^[\w\-\.]+\.md$` → 400; insert/delete `QuoteFavorite` with `quote_id=None`, `obsidian_source=<source>`; requires `get_current_user`).

**Verification:** `POST /api/quotes/obsidian/2026-08-14-金句-050.md/favorite` → `{"favorited": true}`; second call → `false`; invalid source `../../etc/passwd` → 400; no token → 401.

**Delegation:** Category `quick` · Skills: `[]`

---

### Task B5: Merge Obsidian quotes into `/api/collection/news-favorites`
**Files:** `backend/app/api/v1/collection.py`
1. **Imports:** add `from .quotes import OBSIDIAN_QUOTE_DIR, _parse_obsidian_quote, logger` (logical import inside function or at top).
2. **New helper** (before `get_news_favorites`): `_read_obsidian_quote_by_filename(filename)` per spec §4.1, using imported `OBSIDIAN_QUOTE_DIR` and `_parse_obsidian_quote`.
3. **Rewrite quote section** of `get_news_favorites` (lines 196-216): DB branch filters `QuoteFavorite.quote_id.isnot(None)`; add a second branch for `obsidian_source.isnot(None)` resolving content via the helper, emitting `source_type:'obsidian'`, `obsidian_id`, `obsidian_source`.

**Verification:** With a favorited obsidian row + matching file in `OBSIDIAN_QUOTE_DIR`, `GET /api/collection/news-favorites?type=quote` returns both `source_type:'database'` and `source_type:'obsidian'` items.

**Delegation:** Category `unspecified-high` · Skills: `[]`

---

### Task B6: Backend pytest suite (TDD — write first, then make green)
**Files:** new `backend/tests/test_quote_favorite.py`
Cases (per spec §8.1):
1. DB quote favorite → `favorited:true`, row inserted; toggle again → `false`, row removed.
2. Obsidian favorite → `favorited:true`, row has `obsidian_source` set + `quote_id IS NULL`.
3. Obsidian un-favorite → `favorited:false`.
4. Unauthenticated → 401.
5. Invalid `obsidian_source` (`../x.md`) → 400.
6. `/news-favorites` merged response includes obsidian item (monkeypatch `collection._read_obsidian_quote_by_filename` to avoid FS dependency).
7. `/quote/daily` returns `obsidian_id`/`source_type` (monkeypatch `quotes.OBSIDIAN_QUOTE_DIR` to a tmp dir with one fixture `.md`).

**Verification:** `cd backend && python -m pytest tests/test_quote_favorite.py -q` → all pass.

**Delegation:** Category `unspecified-high` · Skills: `["tdd"]`

---

### Task F1: Update `quote_banner.vue`
**Files:** `.vtj/vue/quote_banner.vue` (script only — VTJ compliance: never touch `<template>`)
1. **state** (lines 136-156): add `obsidianId: ''`, `obsidianSource: ''`, `sourceType: 'database'`.
2. **`refreshQuote`** (after line 185): set `obsidianId`, `obsidianSource`, `sourceType` from response.
3. **`toggleQuoteFavorite`** (lines 197-212): replace `if (!this.state.quoteId) return;` with branching — DB endpoint vs obsidian endpoint.
4. Bump `useProvider` version to a new timestamp.

**Verification:** No `<template>`/`<style>` changes; script matches spec; version bumped.

**Delegation:** Category `visual-engineering` · Skills: `[]`

---

### Task F2: Sync `quote_banner.json` DSL
**Files:** `.vtj/files/quote_banner.json`
Add `obsidianId: "''"`, `obsidianSource: "''"`, `sourceType: "'database'"` to `state`; confirm `methods.refreshQuote` / `toggleQuoteFavorite` unchanged; set `__VERSION__` to match the `.vue` version (via `npm run sync:vtj-version` or `vtj_sync_vue_to_dsl`).

**Verification:** `node scripts/sync_vtj_version.mjs` reports no drift; DSL state includes the 3 new fields.

**Delegation:** Category `quick` · Skills: `[]`

---

### Task F3: Update `favorites.vue`
**Files:** `.vtj/vue/favorites.vue`
1. **`viewNewsDetail`** (lines 218-233): when `fav_type === 'quote'`, add to `newsDetail`: `fav_type`, `fav_id`, `quote_id`, `obsidian_source`.
2. **Modal button** (line 96): `@click="removeNewsFavorite(state.newsDetail)"` (pass object, not `.id`).
3. **`removeNewsFavorite`** (lines 250-258): spec §4.2 branching — DB vs obsidian endpoints.

**Verification:** Clicking "取消收藏" on an Obsidian quote deletes the row and refreshes the list; DB quotes still work.

**Delegation:** Category `unspecified-high` · Skills: `[]`

---

### Task F4: Frontend build verification
**Command:** `npm run build:prod` (runs `vue-tsc && vite build`)
**Verification:** Build exits 0; no TS errors.

**Delegation:** Category `quick` · Skills: `[]`

---

## Commit Strategy (atomic, one commit per task)

| Order | Commit | Files |
|---|---|---|
| 1 | `feat(model): quote_favorite 新增 obsidian_source + quote_id 可空` | `backend/app/models/models.py` |
| 2 | `feat(db): quote_favorite 自动迁移（SQLite 表重建）` | `backend/app/main.py` |
| 3 | `feat(api): 每日金句返回 obsidian_id/obsidian_source/source_type` | `backend/app/api/v1/quotes.py` |
| 4 | `feat(api): 新增 Obsidian 金句收藏切换接口` | `backend/app/api/v1/quotes.py` |
| 5 | `feat(api): 收藏页合并返回 Obsidian 金句收藏` | `backend/app/api/v1/collection.py` |
| 6 | `test(api): Obsidian 金句收藏接口测试` | `backend/tests/test_quote_favorite.py` |
| 7 | `feat(frontend): 首页金句支持 Obsidian 收藏` | `.vtj/vue/quote_banner.vue` |
| 8 | `chore(vtj): 同步 quote_banner DSL 版本` | `.vtj/files/quote_banner.json` |
| 9 | `feat(frontend): 收藏页支持 Obsidian 金句取消收藏` | `.vtj/vue/favorites.vue` |

## Risk Assessment

| Risk | Mitigation |
|---|---|
| SQLite can't alter column nullability | Table-rebuild migration (B2); MySQL prod gets spec §5.1 DDL |
| `favorites.vue` removal breaks for obsidian (spec gap) | F3 wires `fav_type`/`obsidian_source` into `newsDetail` + modal passes the object |
| `OBSIDIAN_QUOTE_DIR` not in `settings` (spec bug) | B5 imports from `quotes` module instead |
| VTJ designer overwriting script edits | Only touch script section; sync DSL + version (F2); run sync script |
| DB quote favorites regression | Existing DB branch untouched; B6 tests cover both paths |

## Success Criteria

1. `cd backend && python -m pytest tests/ -q` — all pass (old + new).
2. `npm run build:prod` — exits 0.
3. Manual E2E (spec §8.3): login → favorite Obsidian quote on home → appears in favorites page → un-favorite → list updates; DB quote favorites unaffected.
4. No `<template>` changes in `.vtj/vue/*.vue`; DSL version synced.
5. All 9 atomic commits landed on `obsidian-quote-favorite`.

---

## Execution Instructions

1. **Wave 1**: run B1
2. **Wave 2**: run B2, B3, B4 IN PARALLEL
3. **Wave 3**: run B5
4. **Wave 4**: run B6, F1, F3 IN PARALLEL (commit B6 first so it's green)
5. **Wave 5**: run F2
6. **Wave 6**: run F4 (final QA)
7. Final QA: `pytest` all green + `build:prod` exit 0 + manual E2E per spec §8.3
