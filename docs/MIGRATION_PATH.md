# Migration path to cloud PostgreSQL / Supabase

Keep the following stable:

- frontend UI and domain terminology
- FastAPI URL contract
- Work Package / Evidence JSON contracts
- Conflict and Release logic
- Isaac Adapter payloads

Replace later:

```text
SQLite repository  → PostgreSQL repository
External SSD file adapter → object storage adapter
Local FastAPI process → cloud FastAPI deployment
Cloudflare origin localhost → cloud API origin
```

Because the frontend and adapter never open SQLite directly, this is a storage/deployment migration rather than a UI rewrite.
