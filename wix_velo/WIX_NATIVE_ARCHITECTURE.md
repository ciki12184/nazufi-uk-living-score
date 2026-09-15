# Nazufi UK Living Score — Wix native integration

Nazufi's existing Wix site has Velo enabled, so the preferred frontend architecture is:

Visitor browser
→ Wix page code
→ Velo backend web method
→ Nazufi Living Score API
→ validated public/open datasets

This avoids browser CORS issues and keeps the public page code lightweight.

Current Wix documentation recommends backend calls for external APIs where possible, and modern web modules use `.web.js` files rather than deprecated `.jsw` modules.

## Deployment sequence

1. Deploy the Nazufi backend container to an HTTPS host with persistent storage.
2. Replace `API_BASE` in `livingScore.web.js`.
3. Add `livingScore.web.js` under the Wix backend.
4. Add the page elements listed in `ELEMENT_IDS.md`.
5. Paste `page-code.js` into the UK Living Score page.
6. Preview with real postcodes.
7. Confirm source attribution, unavailable states, and mobile layout.
8. Publish only after validation.

## Data behaviour

The Wix layer does not score or estimate anything.
It displays only what the backend returns.

If the backend returns:
- `unavailable`
- `update_pending`
- `refresh_failed`

the page keeps the value unavailable.

No AI fallback is present in the Wix code.
