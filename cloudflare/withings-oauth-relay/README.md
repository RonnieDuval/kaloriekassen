# Withings OAuth relay

This Worker gives Withings the public HTTPS callback it requires and redirects
the short-lived authorization response to the local OAuth listener at
`http://localhost:8081/`. It stores no data and contains no Withings secrets.

Deploy it from the Cloudflare dashboard by replacing the starter Worker code
with `src/index.js`, or from this directory with:

```powershell
npx wrangler deploy
```

Register the exact deployed URL with Withings, including the path:

```text
https://kaloriekassen-withings-oauth.<account-subdomain>.workers.dev/oauth/callback
```

The same exact URL must be used as `redirect_uri` in the local Withings client
configuration.
