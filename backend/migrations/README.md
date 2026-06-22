# Database migrations

Alembic is the only schema initialization and upgrade path. Run migrations from
the backend directory (or use `app.db.init_db`, which upgrades to `head`).

The revisions `20260609_0001` through `20260609_0003` are frozen snapshots:
they use explicit Alembic DDL and must never import or create from the live ORM
metadata. Revision `20260622_0004` is an additive v0.7 guard for ORM indexes and
uniqueness invariants. It never drops tables, columns, constraints, indexes, or
application data.

SQLite upgrades are online and idempotent at `head`. PostgreSQL SQL can be
reviewed without a server by running an offline upgrade with `--sql`.
