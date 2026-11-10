# Deploy the backend to Google Cloud (Cloud Run) on a shivamio.in subdomain

This deploys **only the backend** (FastAPI + WebSocket live voice). The API will live at:

```
https://sarkari-api.shivamio.in        (REST)
wss://sarkari-api.shivamio.in/ws/live  (live voice)
```

You can pick another name; replace `sarkari-api` everywhere below.

> **Status of this guide.** The commands come from Google's current documentation and standard `gcloud` flags.
> They were **not run** while writing this guide (no `gcloud` on the machine it was written on, and Docker was not
> running). The Python side was checked: a fresh Python 3.12 install of `requirements.txt` starts the app using only
> environment variables, and `/health` returns 200. If a command fails, read the error: most are a missing API,
> permission or wrong variable.

---

## 0. How it fits together

```
 browser ──https/wss──► Global external Application Load Balancer ──► Cloud Run (backend, region asia-south1)
   (frontend)             (your static IP + Google-managed TLS cert)         │
                          sarkari-api.shivamio.in                            ├─► Neon Postgres   (already external)
                                                                             ├─► Upstash Redis   (already external)
                                                                             └─► Gemini / Gnani / myScheme APIs
```

Decisions, and why:

| Decision | Reason |
| --- | --- |
| **Cloud Run** | Runs the container, scales to zero, supports WebSockets. No servers to patch. |
| **Region `asia-south1` (Mumbai)** | Closest to your users and to Gnani/myScheme. |
| **Load balancer for the domain, not "domain mappings"** | Cloud Run domain mappings are **preview, "not recommended for production"** and are **not available in Mumbai** (only asia-east1, asia-northeast1, asia-southeast1 and some US/EU regions). The load balancer works in every region and is Google's recommended route. See the shortcut in section 9 if you only need a demo. |
| **Request timeout 3600 s** | A WebSocket is one long HTTP request. Cloud Run's default (300 s) would cut every live conversation. 3600 s is the maximum. |
| **Load balancer backend timeout 3600 s** | For WebSockets the load balancer's backend timeout is the longest a connection may stay open, **default 30 s**. Left alone, live voice drops after 30 seconds. |
| **CPU always allocated (`--no-cpu-throttling`)** | The backend refreshes its scheme cache in the background every 12 h and saves chat history after replying. By default Cloud Run gives CPU only while a request is running, which starves background work. |
| **Secret Manager** | API keys never go in the image, in Git, or in plain environment settings. |
| **Neon and Upstash stay where they are** | Both are reachable over the internet. No Cloud SQL or VPC needed. |

---

## 1. Prerequisites

1. A Google Cloud project **with billing enabled**. The load balancer's forwarding rule and the static IP have a fixed
   monthly cost even with no traffic, on top of Cloud Run usage. Check current prices on the Google Cloud pricing
   pages before you commit, and see section 9 for a cheaper demo route.
2. [Install the gcloud CLI](https://cloud.google.com/sdk/docs/install) and sign in:
   ```bash
   gcloud auth login
   ```
3. Access to the DNS settings of `shivamio.in` (wherever you bought it).
4. The backend working locally with `backend/.env` filled in (see `backend/.env.example`).

Set shell variables once. Everything below uses them:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-south1"
export SERVICE="sarkari-api"
export REPO="sarkari"
export DOMAIN="sarkari-api.shivamio.in"
export FRONTEND_ORIGIN="https://YOUR-FRONTEND-URL"     # where the website will be served from

gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
```

Enable the APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com
```

---

## 2. Put the secrets in Secret Manager

Each secret from `backend/.env` that is sensitive becomes one Secret Manager secret. Run this from the repo root.
It reads values from `backend/.env` so you never type or paste a key.

```bash
# Names of the settings that are secrets. Add or remove names to match your backend/.env.
SECRETS="DATABASE_URL SECRET_KEY GNANI_API_KEY MYSCHEME_API_KEY GROQ_API_KEY \
UPSTASH_REDIS_REST_URL UPSTASH_REDIS_REST_TOKEN \
GEMINI_API_KEY GEMINI_API_KEY2 GEMINI_API_KEY3 GEMINI_API_KEY4 \
GEMINI_API_KEY5 GEMINI_API_KEY6 GEMINI_API_KEY7 GEMINI_API_KEY8"

for NAME in $SECRETS; do
  VALUE=$(grep -E "^${NAME}=" backend/.env | head -n1 | cut -d= -f2-)
  [ -z "$VALUE" ] && { echo "skip $NAME (empty)"; continue; }
  SECRET_ID=$(echo "$NAME" | tr '[:upper:]_' '[:lower:]-')          # GEMINI_API_KEY2 -> gemini-api-key2
  if gcloud secrets describe "$SECRET_ID" >/dev/null 2>&1; then
    printf '%s' "$VALUE" | gcloud secrets versions add "$SECRET_ID" --data-file=-
  else
    printf '%s' "$VALUE" | gcloud secrets create "$SECRET_ID" --data-file=- --replication-policy=automatic
  fi
done
```

Give the Cloud Run runtime account permission to read them:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"     # default Cloud Run identity

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

> Better, once it works: create a dedicated service account for the service and give only that account access.

---

## 3. Build the image and deploy

Create an Artifact Registry repository once:

```bash
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker --location="$REGION" \
  --description="Sarkari Saathi images"
```

Build in the cloud (no local Docker needed). The build context is the `backend/` folder, which has the `Dockerfile`:

```bash
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:$(git rev-parse --short HEAD)"
gcloud builds submit backend --tag "$IMAGE"
```

Deploy. Plain settings go in `--set-env-vars`, secrets in `--set-secrets`:

```bash
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --timeout=3600 \
  --no-cpu-throttling \
  --min-instances=1 \
  --max-instances=3 \
  --concurrency=80 \
  --memory=1Gi \
  --cpu=1 \
  --set-env-vars="ENVIRONMENT=production,APP_NAME=Sarkari Saathi,FRONTEND_ORIGIN=${FRONTEND_ORIGIN},BACKEND_URL=https://${DOMAIN},GNANI_STT_LANGUAGE=indic-auto,GNANI_EVON_ENABLED=false,MYSCHEME_API_BASE=https://api.myscheme.gov.in,GEMINI_MODEL=gemini-2.5-flash,GEMINI_FALLBACK_MODEL=gemini-3.5-flash,JWT_EXPIRE_HOURS=72" \
  --set-secrets="DATABASE_URL=database-url:latest,SECRET_KEY=secret-key:latest,GNANI_API_KEY=gnani-api-key:latest,MYSCHEME_API_KEY=myscheme-api-key:latest,GROQ_API_KEY=groq-api-key:latest,UPSTASH_REDIS_REST_URL=upstash-redis-rest-url:latest,UPSTASH_REDIS_REST_TOKEN=upstash-redis-rest-token:latest,GEMINI_API_KEY=gemini-api-key:latest,GEMINI_API_KEY2=gemini-api-key2:latest,GEMINI_API_KEY3=gemini-api-key3:latest,GEMINI_API_KEY4=gemini-api-key4:latest,GEMINI_API_KEY5=gemini-api-key5:latest,GEMINI_API_KEY6=gemini-api-key6:latest,GEMINI_API_KEY7=gemini-api-key7:latest,GEMINI_API_KEY8=gemini-api-key8:latest"
```

Notes:

- If you leave some key out of Secret Manager (for example no Groq key), remove it from `--set-secrets`, otherwise
  the deploy fails with "secret not found".
- `--allow-unauthenticated`: the app does its own login (JWT). The site is public.
- `--min-instances=1` keeps one instance warm so the first visitor does not wait for a cold start (which loads the
  scheme cache). It costs a little all month. Use `0` to save money; the first request after idle is then slower.
- `--max-instances=3`: each instance keeps its own in-memory counters for rate-limited Gemini keys. Keep this small
  unless you have configured Upstash Redis for shared caching.
- Do **not** set `PORT`; Cloud Run sets it and the `Dockerfile` reads it.

Check the service. Cloud Run gives it a `*.run.app` address:

```bash
URL=$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')
echo "$URL"
curl -s "$URL/health"
```

You should see `{"status":"ok", ...}`. If the revision fails to start, read the logs:

```bash
gcloud run services logs read "$SERVICE" --region "$REGION" --limit=50
```

---

## 4. Point `sarkari-api.shivamio.in` at it (load balancer)

### 4.1 Reserve a static IP

```bash
gcloud compute addresses create sarkari-api-ip --network-tier=PREMIUM --ip-version=IPV4 --global
export LB_IP=$(gcloud compute addresses describe sarkari-api-ip --global --format='get(address)')
echo "Load balancer IP: $LB_IP"
```

### 4.2 Add the DNS record (do this now: the certificate in 4.4 needs it)

At the DNS provider for `shivamio.in`, create one record:

| Type | Name / Host | Value | TTL |
| --- | --- | --- | --- |
| `A` | `sarkari-api` | the `LB_IP` printed above | 300 |

Check it (can take minutes to hours):

```bash
dig +short sarkari-api.shivamio.in      # must print LB_IP
```

If `shivamio.in` uses CAA records, allow Google's certificate authority: add a CAA record for `pki.goog`.

### 4.3 Create the load balancer pieces

```bash
# Serverless NEG: tells the load balancer which Cloud Run service to send traffic to
gcloud compute network-endpoint-groups create sarkari-api-neg \
  --region="$REGION" --network-endpoint-type=serverless --cloud-run-service="$SERVICE"

# Backend service. --timeout=3600 is REQUIRED for WebSockets (default is 30 seconds)
gcloud compute backend-services create sarkari-api-backend \
  --load-balancing-scheme=EXTERNAL_MANAGED --global
gcloud compute backend-services update sarkari-api-backend --global --timeout=3600
gcloud compute backend-services add-backend sarkari-api-backend --global \
  --network-endpoint-group=sarkari-api-neg --network-endpoint-group-region="$REGION"

# URL map
gcloud compute url-maps create sarkari-api-map --default-service sarkari-api-backend
```

### 4.4 Certificate, proxy and forwarding rule

```bash
# Google-managed TLS certificate for the subdomain
gcloud compute ssl-certificates create sarkari-api-cert --domains="$DOMAIN" --global

gcloud compute target-https-proxies create sarkari-api-https-proxy \
  --ssl-certificates=sarkari-api-cert --url-map=sarkari-api-map

gcloud compute forwarding-rules create sarkari-api-https-rule \
  --load-balancing-scheme=EXTERNAL_MANAGED --network-tier=PREMIUM \
  --address=sarkari-api-ip --target-https-proxy=sarkari-api-https-proxy \
  --global --ports=443
```

Optional: redirect `http://` to `https://`:

```bash
cat > /tmp/redirect.yaml <<'YAML'
kind: compute#urlMap
name: sarkari-api-redirect
defaultUrlRedirect:
  redirectResponseCode: MOVED_PERMANENTLY_DEFAULT
  httpsRedirect: true
YAML
gcloud compute url-maps import sarkari-api-redirect --source=/tmp/redirect.yaml --global
gcloud compute target-http-proxies create sarkari-api-http-proxy --url-map=sarkari-api-redirect
gcloud compute forwarding-rules create sarkari-api-http-rule \
  --load-balancing-scheme=EXTERNAL_MANAGED --network-tier=PREMIUM \
  --address=sarkari-api-ip --target-http-proxy=sarkari-api-http-proxy --global --ports=80
```

### 4.5 Wait for the certificate

```bash
gcloud compute ssl-certificates describe sarkari-api-cert --global \
  --format='value(managed.status,managed.domainStatus)'
```

It shows `PROVISIONING` first and must reach `ACTIVE`. This usually takes 15-60 minutes after the DNS record
resolves, and can take longer. If it stays `FAILED_NOT_VISIBLE`, the DNS record is wrong or has not propagated.

### 4.6 Lock the front door (recommended)

So that people can only reach the service through your domain (and not the raw `run.app` address):

```bash
gcloud run services update "$SERVICE" --region "$REGION" \
  --ingress=internal-and-cloud-load-balancing
```

After this, `curl "$URL/health"` against the `run.app` address returns an error; that is expected. Skip this step
while you are still testing with the `run.app` URL.

---

## 5. Test

```bash
curl -s https://sarkari-api.shivamio.in/health
```

Then test the WebSocket stays open past 30 seconds (this is the check for the timeout setting). With a valid
login token (from `POST /auth/login`) in `TOKEN`:

```bash
npx wscat -c "wss://sarkari-api.shivamio.in/ws/live?token=${TOKEN}"
# leave it connected for 60+ seconds; it must not close
```

---

## 6. Connect the frontend

The frontend reads its own `frontend/.env` at **build** time. For production set:

```
VITE_API_URL=https://sarkari-api.shivamio.in
VITE_WS_URL=wss://sarkari-api.shivamio.in
```

Build and host `frontend/dist` anywhere (Firebase Hosting, Netlify, Vercel, Cloud Storage + CDN...). Then make
sure the backend allows that origin. `FRONTEND_ORIGIN` must be exactly the site's address, with no trailing slash:

```bash
gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars="FRONTEND_ORIGIN=https://your-frontend.example"
```

A wrong `FRONTEND_ORIGIN` shows up in the browser as a CORS error on every request.

> Check `backend/app/main.py`: CORS currently allows `FRONTEND_ORIGIN` plus `http://localhost:5173` and
> `http://127.0.0.1:5173`. That is fine for a first deploy.

---

## 7. Update later

```bash
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:$(git rev-parse --short HEAD)"
gcloud builds submit backend --tag "$IMAGE"
gcloud run deploy "$SERVICE" --image "$IMAGE" --region "$REGION"
```

Change a secret (for example swap a Gemini key), then restart so the new version is read:

```bash
printf '%s' "NEW_KEY_VALUE" | gcloud secrets versions add gemini-api-key3 --data-file=-
gcloud run services update "$SERVICE" --region "$REGION" --update-env-vars="RESTARTED_AT=$(date +%s)"
```

Roll back:

```bash
gcloud run revisions list --service "$SERVICE" --region "$REGION"
gcloud run services update-traffic "$SERVICE" --region "$REGION" --to-revisions=REVISION_NAME=100
```

---

## 8. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| Live voice disconnects after about 30 s | Load balancer backend timeout is still the default. Re-run `gcloud compute backend-services update sarkari-api-backend --global --timeout=3600`. Wait a few minutes. |
| Live voice disconnects after 5 min | Cloud Run request timeout is still 300 s. `gcloud run services update "$SERVICE" --timeout=3600`. |
| Certificate stuck on `PROVISIONING` / `FAILED_NOT_VISIBLE` | The `A` record is missing, wrong, or behind a proxy. `dig +short sarkari-api.shivamio.in` must print the load balancer IP. If the DNS provider has an orange-cloud proxy (Cloudflare), turn the proxy off for this record. |
| `502` or `503` from the domain | The container is not healthy. Read `gcloud run services logs read`. Common causes: a secret name does not exist, `DATABASE_URL` is wrong. |
| Browser shows a CORS error | `FRONTEND_ORIGIN` does not exactly match the site's address (scheme, host, no trailing slash). |
| Replies always sound rule-based, not AI | No LLM key reached the service, or every Gemini key is rate limited. Check the logs for `LLM failed` lines. Keys appear in logs only as `gemini#3`, never as the key. |
| `Permission denied` on a secret | The runtime service account lacks `roles/secretmanager.secretAccessor` (section 2). |
| First request after idle is slow | Cold start with `--min-instances=0`. Use `--min-instances=1`. |

---

## 9. Shortcut for a quick demo (not for production)

If you only need a working HTTPS address for a demo and want to skip the load balancer (and its monthly cost):

- Use the `run.app` address from `gcloud run services describe`. It already has HTTPS and supports WebSockets.
  Set the frontend to `https://<service>-<hash>.<region>.run.app` and `wss://...` of the same host.
- Or map your subdomain with a **Cloud Run domain mapping** in a supported region. Mumbai is not supported, so you
  would deploy in `asia-southeast1` (Singapore) instead. Google marks this feature as preview and not recommended for
  production. Verify ownership of `shivamio.in` first (`gcloud domains verify shivamio.in`), then:
  ```bash
  gcloud beta run domain-mappings create --service "$SERVICE" --domain "$DOMAIN" --region asia-southeast1
  gcloud beta run domain-mappings describe --domain "$DOMAIN" --region asia-southeast1
  ```
  Add the DNS records it prints (usually a `CNAME` to `ghs.googlehosted.com`). The certificate takes about 15
  minutes to 24 hours.

---

## 10. Clean up (stop all charges)

```bash
gcloud compute forwarding-rules delete sarkari-api-https-rule --global -q
gcloud compute forwarding-rules delete sarkari-api-http-rule --global -q       # if created
gcloud compute target-https-proxies delete sarkari-api-https-proxy -q
gcloud compute target-http-proxies delete sarkari-api-http-proxy -q            # if created
gcloud compute url-maps delete sarkari-api-map -q
gcloud compute url-maps delete sarkari-api-redirect -q                         # if created
gcloud compute backend-services delete sarkari-api-backend --global -q
gcloud compute network-endpoint-groups delete sarkari-api-neg --region "$REGION" -q
gcloud compute ssl-certificates delete sarkari-api-cert --global -q
gcloud compute addresses delete sarkari-api-ip --global -q
gcloud run services delete "$SERVICE" --region "$REGION" -q
```

---

## Sources

- Cloud Run and WebSockets: <https://cloud.google.com/run/docs/triggering/websockets>
- Custom domains for Cloud Run (load balancer recommended; domain mappings are preview and region-limited): <https://docs.cloud.google.com/run/docs/mapping-custom-domains>
- Global external Application Load Balancer with a serverless NEG: <https://docs.cloud.google.com/load-balancing/docs/https/setup-global-ext-https-serverless>
- Load balancer timeout for WebSockets: when a connection is upgraded to a WebSocket, the backend service timeout
  is the longest the connection can stay open, whether idle or not, and it defaults to 30 seconds. This is described
  in Google's load balancer documentation and in answers on Stack Overflow quoting it; confirm the current wording
  at <https://cloud.google.com/load-balancing/docs/https> (search "WebSocket").
