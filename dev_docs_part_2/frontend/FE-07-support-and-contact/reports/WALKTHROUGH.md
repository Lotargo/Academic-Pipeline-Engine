# FE-07 Walkthrough

## Closed tasks

- `FE-07-T002`: voluntary YooMoney form with presets `150`, `500`, `1000`, and `5000` rubles, plus a validated custom amount.
- `FE-07-T006`: this walkthrough.

Previously completed tasks `T001`, `T003`, `T004`, and `T005` remain valid.

## Delivered

- `/support` is public and separates voluntary support from the Telegram cooperation contact.
- The form posts directly to `https://yoomoney.ru/quickpay/confirm` in a new protected tab.
- It sends only the public wallet identifier (`receiver`), donation type, purpose, and selected amount. It does not use an API key, OAuth token, payment backend, payment history, or entitlement logic.
- The wallet identifier is configured with `NEXT_PUBLIC_SUPPORT_YOOMONEY_RECEIVER`; its absence renders a neutral unavailable state.
- All interface text states that a transfer does not provide services, subscriptions, priority, limits, queue access, or other benefits.

## Deliberate deviation

The original `T002` mentioned an SBP link and QR. The mandatory clarification in `dev_docs_part_2/README.md` takes precedence: SBP/QR are optional and are not acceptance requirements. The implemented YooMoney HTML form is the required support flow.

## Verification

- `pnpm test:support` — passed, 3 tests.
- `pnpm lint` — passed with 0 errors and 161 pre-existing project warnings.
- `pnpm build` — passed; `/support` was generated successfully.
- Browser visual verification was not run, as required by the repository work rules; it remains user-controlled.

## Result

FE-07 is complete. No payment is linked to an account, status, function, limit, or queue behavior.
