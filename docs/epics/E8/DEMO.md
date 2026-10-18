# E8 Billing entitlements: demo

**Done when:** entitlements are enforced as configured.

Pricing is under commercial review, so there are no real plans. The plans below are made up for the demo. Nothing in the code holds a price or a limit.

## Run it

As in `docs/epics/E5/DEMO.md`, then `alembic upgrade head` for migration 0008.

Make yourself a platform admin (staff only, never through the app):

```sql
UPDATE identity.users SET is_platform_admin = true WHERE email = 'you@example.com';
```

## What to show (about 4 minutes)

1. **No plans, no limits.** Sign in as a company Owner and open **Settings**. Under **Plan**: "No plan chosen", and every limit says "No limit". Invite as many investors as you like.
2. **Set a plan with no deploy.** As the platform admin:

   ```bash
   curl -X PUT localhost:8000/admin/billing/plans/starter \
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"name": "Starter", "is_default": true, "entitlements": {"viewers": 1, "uploads_per_month": 5, "max_file_mb": 10}}'
   ```

   Reload Settings: the plan is Starter, and once one investor is invited the investors row shows 1 used of 1.
3. **Warn (the default).** Invite a second investor. The invitation goes and a notice says "Your plan includes 1 investor. This went through. The Owner or CEO can change the plan." The Investors row shows **Over**. The audit log has "Went past a plan limit".
4. **Block.** Restart the API with `LIMIT_BEHAVIOUR=block` and invite a third: refused with "Your plan includes 1 investor. The Owner or CEO can change the plan in Settings." Nothing is saved.
5. **Change the value.** Run the `curl` again with `"viewers": 5`. The third invitation now goes, with the API still running.
6. **Approval is the same on every plan.** Set every limit to 0 and approve an update: it is shared as normal.
7. **Pay with Stripe (test mode).** Set `STRIPE_SECRET_KEY` (a `sk_test_` key) and `STRIPE_WEBHOOK_SECRET`, create a price in Stripe and give it to a plan as `"stripe_price_id"`. Forward Stripe's events with the Stripe CLI: `stripe listen --forward-to localhost:8000/billing/stripe/webhook`. In Settings choose the plan, pay with card 4242 4242 4242 4242, and come back: the plan changes once Stripe's event arrives. **Manage billing** opens Stripe's portal. Cancel there and the company falls back to the default plan.
8. **Replays change nothing.** In the Stripe dashboard, resend any event: the API answers `{"outcome": "duplicate"}` and nothing moves.

## Requirements covered

| FR | Status | Proved by |
|---|---|---|
| FR-9.1 | Done | Changing `viewers` from 1 to 2 in the running app lets the second investor in. Only platform admins set plans, and only known keys. The size and files-a-month keys are checked where files are added, including a file bigger than it said it was |
| FR-9.2 | Done | Checkout and the portal go to Stripe for the right company; a plan with no price cannot be bought; without Stripe set up the page says so. Webhooks are signature-checked; replaying events, in any order, changes no row and writes no audit entry; an older event arriving late cannot undo a newer one |
| FR-9.3 | Done | Approval succeeds with no plan, with every limit at 0, and on a paid plan. No approval code imports billing |
| FR-9.4 | Done, open | Warn lets the action through with the warning and an audit entry; block refuses it and keeps nothing. The choice is `LIMIT_BEHAVIOUR`, listed in OPEN.md |
