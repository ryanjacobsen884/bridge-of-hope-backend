# Content still needed from The Bridge of Hope Foundation

Nothing in the codebase invents an organisational fact — every placeholder
below is visible on the live pages (as a highlighted `.fill` span, ported
from the approved HTML) and tracked here per the build spec, rule 9.

## Registration & governance
- [ ] Body that issued registration no. SCH/2026/001
- [ ] Charitable Children's Institution (DCS) registration number
- [ ] Safeguarding lead's full name and email
- [ ] Director's full name, photo, and two-sentence bio
- [ ] Head of care's full name, title, photo, and two-sentence bio
- [ ] Board chair's full name, photo, and two-sentence bio
- [ ] Street/postal address; phone number; contact email domain

## Programme numbers (do not fabricate — leave blank until supplied)
- [ ] Children fed daily
- [ ] Children in full-time school
- [ ] Children covered by medical insurance
- [ ] Caregivers on staff
- [ ] Whether "working with families / reunification" is real — confirm or delete that block entirely
- [ ] Children returned to family (only if the block above is kept)

## Accountability
- [ ] Audited-accounts year and total income (KSh)
- [ ] Real expense breakdown percentages (food/school/medical/salaries/admin) — the current bars are illustrative placeholders
- [ ] PDFs: annual report, audited accounts, child protection policy, certificate of registration

## Give page / FAQ
- [ ] Tax-deductibility answer (honest — likely "not currently" per spec)
- [ ] FX/charging explanation — confirm with the actual payment provider before writing this
- [ ] Real "% reaches children" figure from audited accounts
- [ ] Update cadence (monthly / every two months)

## Updates
- [ ] Three real, dated updates (photos of buildings/staff/place — no children's faces) to replace the seeded `[TEST CONTENT]` posts

## Privacy policy
- [ ] Last-updated date, full address, data-protection contact name/email
- [ ] ODPC (Kenya) registration number, if registered
- [ ] Analytics tool in use, if any (or confirm "none")
- [ ] Cookie list

## Payment credentials (none supplied yet — everything below is stubbed/off)
- [ ] PayPal: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` (sandbox first)
- [ ] M-Pesa Daraja: `MPESA_CONSUMER_KEY`, `MPESA_CONSUMER_SECRET`, `MPESA_SHORTCODE`, `MPESA_PASSKEY`, a public HTTPS callback URL
- [ ] Stripe (when a US/UK entity exists): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, publishable key
- [ ] Bitcoin (post-launch): BTCPay Server instance + API key, or OpenNode/Coinbase Commerce credentials
- [ ] Outbound email: SMTP host/user/password (Google Workspace SMTP), plus SPF/DKIM/DMARC DNS records for the sending domain

## Deploy-time (per the request that created this repo, resolve directly)
- [ ] Confirm the correct Vercel API token — the value pasted for setup was ambiguous between a token and a label.
