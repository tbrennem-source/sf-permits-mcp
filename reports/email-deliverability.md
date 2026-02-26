# Email Deliverability Report — sfpermits.ai

**Date:** 2026-02-25
**Scope:** Audit of current SMTP configuration and deliverability posture for sfpermits.ai transactional email

---

## Current SMTP Configuration

### Settings (from `web/auth.py` and `web/email_brief.py`)

| Setting | Value |
|---------|-------|
| `SMTP_HOST` | Railway env var (not hardcoded) |
| `SMTP_PORT` | `587` (STARTTLS — correct) |
| `SMTP_FROM` | `noreply@sfpermits.ai` (default if env var not set) |
| `SMTP_USER` | Railway env var |
| `SMTP_PASS` | Railway env var |

### Connection method

- Uses `smtplib.SMTP(SMTP_HOST, SMTP_PORT)` then `server.starttls()`
- Port 587 with STARTTLS is the correct modern approach (vs. port 465 SSL or port 25 unauthenticated)
- Login is conditional on `SMTP_USER` being set — if not set, email is sent unauthenticated

### Email types sent

1. **Magic link** (`web/auth.py` → `_send_magic_link_sync`) — subject: "Your sfpermits.ai sign-in link"
2. **Beta request confirmation** (`web/auth.py`) — welcome email
3. **Morning brief** (`web/email_brief.py`) — daily digest
4. **Nightly triage** (`web/email_triage.py`) — admin report

---

## Deliverability Analysis

### What's Working Well

**HTML + plain text multipart** — Both `_send_magic_link_sync` and the morning brief send `multipart/alternative` (plain text + HTML). This is a strong signal to spam filters that the sender is a legitimate email client.

**List-Unsubscribe headers** — Magic link emails include:
```
List-Unsubscribe: <mailto:noreply@sfpermits.ai?subject=unsubscribe>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```
This is required by Gmail and Yahoo for bulk senders (>5K/day). Even for low volume, it's a positive signal.

**STARTTLS on port 587** — Correct. Encrypted in transit.

---

## What Tim Needs to Verify (cannot check DNS from here)

### 1. SPF Record

**What to check:** DNS TXT record for `sfpermits.ai`

```
dig TXT sfpermits.ai
```

**Expected:** Should include your SMTP provider's authorized servers. Example for SendGrid:
```
v=spf1 include:sendgrid.net ~all
```

If you're using Railway's built-in SMTP relay or a custom SMTP provider, add their include directive. If no SPF record exists, Gmail/Outlook will soft-fail or reject the email.

**Risk if missing:** High. Gmail will show "via [relay-server]" warning or send to spam.

---

### 2. DKIM Record

**What to check:** Your SMTP provider should provide a DKIM public key to add as a DNS TXT record.

```
dig TXT [selector]._domainkey.sfpermits.ai
```

DKIM signing requires your SMTP provider to sign outbound emails. Most ESPs (SendGrid, Mailgun, Postmark, AWS SES) handle this automatically once you add their CNAME/TXT records to your DNS.

**Risk if missing:** High. DKIM absence is a strong spam signal for Gmail/Outlook. Without DKIM, your DMARC policy cannot pass.

---

### 3. DMARC Record

**What to check:**

```
dig TXT _dmarc.sfpermits.ai
```

**Recommended minimum:**
```
v=DMARC1; p=none; rua=mailto:dmarc@sfpermits.ai
```

Start with `p=none` (monitor only) and upgrade to `p=quarantine` or `p=reject` after verifying SPF+DKIM alignment.

**Risk if missing:** Medium. DMARC absence won't cause immediate delivery failure but reduces trust score with major providers.

---

### 4. What SMTP Provider Is Actually Configured?

The codebase reads `SMTP_HOST` from Railway env vars — we can't see the actual value in the repo. Check Railway dashboard for the `sfpermits-ai` service:

```bash
railway variable list | grep SMTP
```

**Common options and their deliverability:**

| Provider | Deliverability | Notes |
|----------|---------------|-------|
| SendGrid | Excellent | Free tier: 100 emails/day. SPF/DKIM auto-configured via CNAME |
| Mailgun | Excellent | 100 emails/day free. Requires domain verification |
| Postmark | Excellent | Transactional-only, best inbox rates. $15/mo min |
| AWS SES | Very Good | Requires domain verification + production access request |
| Gmail SMTP | Good for low volume | 500/day limit, requires app password with 2FA |
| Generic/Railway | Unknown | If Railway provides SMTP, may not have shared reputation |

---

## Recommendations (Priority Order)

### Immediate (do this week)

1. **Verify your SMTP provider** — Run `railway variable list | grep SMTP` to confirm what's configured
2. **Add SPF record** — Single DNS TXT record, takes 5 minutes
3. **Enable DKIM** — Requires generating key pair in your ESP dashboard, adding DNS records
4. **Add DMARC (monitor mode)** — `p=none` with a reporting address

### Short-term (within 30 days)

5. **Test with mail-tester.com** — Send a test email to their test address, score should be 9+/10
6. **Use Google Postmaster Tools** — Monitor your domain reputation at postmaster.google.com
7. **Warm up the sending domain** — If this is a new domain (`sfpermits.ai`), start with low volume and ramp up gradually

### The FROM address

`noreply@sfpermits.ai` is standard but reduces reply engagement. Consider:
- `brief@sfpermits.ai` for morning brief emails (users may want to reply)
- Keep `noreply@sfpermits.ai` for magic links (no replies expected)

---

## Gmail-Specific Notes (2024 requirements)

As of February 2024, Gmail requires for senders of >5,000/day:
- SPF OR DKIM (at minimum), DMARC
- One-click unsubscribe (already implemented via `List-Unsubscribe-Post`)

For low-volume senders (under 5K/day, which sfpermits.ai likely is today):
- SPF and DKIM are still strongly recommended but not hard-required
- Missing either will result in warnings or spam folder placement

---

## Code Quality Notes

The email sending code in `web/auth.py` and `web/email_brief.py` is well-structured:
- Graceful fallback when SMTP is not configured (logs the link instead of crashing)
- Background thread for magic links (non-blocking)
- HTML + plain text multipart (correct)
- List-Unsubscribe headers (correct)

No code changes needed for deliverability. The gap is DNS/provider configuration.
