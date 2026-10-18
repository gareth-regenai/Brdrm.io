# Email

BoardRoom.io sends email over SMTP: invitations to join a company, and the one question about an upload. Any SMTP server works, so an existing mailbox can send without signing up for an email service.

## Option 1: a local test inbox (no account, nothing sent)

`docker compose up -d` starts Mailpit with the database. Run the API with:

```bash
MAILER=smtp SMTP_HOST=localhost SMTP_PORT=1025 SMTP_SECURITY=none SMTP_FROM=hello@boardroom.local
```

Every email lands at http://localhost:8025, links included. Use this for demos and testing.

## Option 2: an existing Google mailbox (real email, no new account)

Works with Gmail or Google Workspace, as long as 2-step verification is on.

1. Sign in to the mailbox that will send, ideally a separate BoardRoom address rather than a RegenAI one.
2. Go to https://myaccount.google.com/apppasswords and create an app password called "BoardRoom.io".
3. Set:

```bash
MAILER=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=the-mailbox@yourdomain.com
SMTP_PASSWORD=the 16-letter app password
SMTP_FROM=the-mailbox@yourdomain.com
```

On Render, enter the `SMTP_*` values when the Blueprint asks for them, or later under the service's Environment tab. Google limits how much one mailbox can send per day (500 for Gmail, 2,000 for Workspace), which is plenty for invitations during the beta.

## Microsoft 365

Microsoft has been switching off password sign-in for SMTP, so a Microsoft 365 mailbox will usually refuse these settings. Use a Google mailbox or a sending service instead.

## Later: a sending service

When volume or deliverability matters, move to a sending service with SMTP (for example Postmark, Amazon SES or Resend). Only the `SMTP_*` settings change. That needs an account, and the service becomes a subprocessor to list in the privacy documents.

## What is never logged

The app logs only that an email was sent and the recipient's domain. Addresses, subjects and links stay out of the logs.
