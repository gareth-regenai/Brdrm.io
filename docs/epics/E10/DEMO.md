# E10 Hardening and beta: demo

**Done when:** the success measures in BRD chapter 1 are met on the beta set.

E10 lands in parts. This page grows with each.

## Part 1: staff support access (FR-11.6)

**Accept:** a support session appears in the customer's audit view and expires.

### Run it

As in `docs/epics/E5/DEMO.md`, then `alembic upgrade head` for migration 0010. Make a staff account a platform admin (staff only, never through the app):

```sql
UPDATE identity.users SET is_platform_admin = true WHERE email = 'staff@boardroom.example.com';
```

### What to show (about 3 minutes)

1. As staff, open a session with a reason:

   ```bash
   curl -X POST localhost:8000/admin/support/$TENANT_ID \
     -H "Authorization: Bearer $STAFF_TOKEN" -H "Content-Type: application/json" \
     -d '{"reason": "Checking why the September file is stuck"}'
   ```

2. Staff sign in and see the company under their account. A notice says they are reading it as BoardRoom support, can change nothing, every page they open is logged, and when access ends. They see what the company sees, including updates awaiting approval. Every button that changes something is refused.
3. As the Owner, open the company: a notice names who from BoardRoom support can see it, why and until when, with **End support access now**. The audit log shows "BoardRoom support opened read-only access" with the reason, and each page support viewed.
4. Choose **End support access now**: staff lose access on their next click.
5. Left alone, a session ends after `SUPPORT_SESSION_MINUTES` (60 by default). The database enforces the end as well as the API.

### Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-11.6 | Done | Support reads the company, including what is not shared yet, and every endpoint that changes anything refuses it. A test checks that no action open to support is used by a changing endpoint. Each page is in the company's audit log; the company sees who, why and until when, and can end it. An expired session reads nothing, in the API and in the database. Support never appears in the team, investors, tagging or invitations |
