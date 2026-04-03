# Vigil Database Migrations

## Migration Strategy

Vigil uses a file-based migration strategy designed for **Neon PostgreSQL's serverless architecture**. Each migration file is:

- **Idempotent**: Safe to run multiple times without side effects.
- **Non-blocking**: Uses `CONCURRENTLY` for index creation to avoid table locks.
- **Sequentially numbered**: `001_`, `002_`, etc. for clear execution order.
- **Self-documenting**: Each file includes comments explaining purpose and impact.

## Migration Files

| File | Description |
|------|-------------|
| `001_neon_optimizations.sql` | Index strategy for Neon serverless performance |

## How to Run Migrations

### Prerequisites
- `DATABASE_URL` environment variable set to your Neon PostgreSQL connection string
- `psql` client installed (or use Neon's web console)

### Running a Migration

```bash
# Run a specific migration
psql "$DATABASE_URL" -f migrations/001_neon_optimizations.sql

# Or via Neon's web console: copy-paste the SQL content
```

### Running All Pending Migrations

```bash
# Simple loop to run all migrations in order
for f in migrations/*.sql; do
  echo "Running $f..."
  psql "$DATABASE_URL" -f "$f"
done
```

### Programmatic Migration (from Python)

```python
import asyncpg
import os

async def run_migration(filepath: str):
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    async with pool.acquire() as conn:
        sql = open(filepath).read()
        await conn.execute(sql)
    await pool.close()
```

## Rollback Procedures

### General Principles
1. **Indexes**: Drop the index to rollback an index migration.
   ```sql
   DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_symbol_timestamp;
   ```
2. **Schema Changes**: Use `ALTER TABLE ... DROP COLUMN` or `DROP TABLE` for structural changes.
3. **Data Changes**: Maintain backups before running data migrations.

### Rollback for 001_neon_optimizations.sql

```sql
-- Drop all indexes created by migration 001
DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_symbol_timestamp;
DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_severity;
DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_regime;
DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_edge_score;
DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_outcome_result;
DROP INDEX CONCURRENTLY IF EXISTS idx_alerts_created_at;
```

## Verification

After running migrations, verify indexes exist:

```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'alerts' 
ORDER BY indexname;
```

## Best Practices for Neon

1. **Always use `CONCURRENTLY`** for index creation to avoid blocking.
2. **Use `IF NOT EXISTS`** for idempotency.
3. **Partial indexes** (with `WHERE` clauses) reduce storage and improve query performance.
4. **Monitor index usage** with `pg_stat_user_indexes` to identify unused indexes.
5. **Connection pooling**: Neon handles connection pooling at the platform level. The application uses `asyncpg` with a local pool for efficient connection reuse.
