# SQLite 直写审计

> **生成时间**：2026-06-13 23:47:36 UTC
> **范围**：`backend/` 内 `_conn.execute` / `sqlite3.connect`
> **排除**：`backend/common/store.py`、`backend/store/`

共 **4** 处直写（供 2.4 PG 迁移 / 2.5 group_manager 收拢输入）。

## _conn.execute（2）

- `backend/common/tests/test_store.py:187` — `c = store._conn.execute(`
- `backend/common/tests/test_store.py:192` — `assert store._conn.execute(`

## sqlite3.connect（2）

- `backend/common/tests/test_process.py:1199` — `conn = sqlite3.connect(str(tmp_path / "state.db"))`
- `backend/common/tests/test_regression_archive.py:22` — `conn = sqlite3.connect(str(db))`

