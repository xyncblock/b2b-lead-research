# Deployment Setup

## Environments

| Environment | URL | Purpose | Auto-Deploy |
|------------|-----|---------|-------------|
| **Dev** | https://dev-b2b-leads.akzain.com | Development, testing | ✅ Yes |
| **Staging** | https://staging-b2b-leads.akzain.com | Pre-production, review | ⚠️ Requires approval |

## Quick Start

```bash
# Run on your server
sudo ./deploy/setup-environments.sh
```

## Manual Setup

```bash
# Start both environments
docker-compose -f deploy/docker-compose.yml up -d

# View logs
docker logs -f b2b-dev-dashboard
docker logs -f b2b-staging-dashboard

# Restart
docker-compose -f deploy/docker-compose.yml restart
```

## Staging Approval

Staging deployments require manual approval from Ak.

### How it works:
1. Code is pushed to `staging` branch
2. CI/CD sends Telegram message to Ak
3. Ak replies `approve staging` or `deny staging`
4. If approved, deployment proceeds
5. If denied or timeout (30 min), deployment is cancelled

### Approve from Telegram:
```
approve staging
```

### Deny from Telegram:
```
deny staging
```

## Domain Setup

Point these subdomains to your server IP:
- `dev-b2b-leads.akzain.com`
- `staging-b2b-leads.akzain.com`

## SSL (Let's Encrypt)

```bash
# Install certbot
apt install certbot python3-certbot-nginx

# Get certificates
certbot --nginx -d dev-b2b-leads.akzain.com -d staging-b2b-leads.akzain.com
```

## Environment Variables

Create `.env` files:

```bash
# .env.dev & .env.staging
GOOGLE_PLACES_API_KEY=your_key
COMPANIES_HOUSE_API_KEY=your_key
```

## Ports

| Service | Dev | Staging |
|---------|-----|---------|
| Dashboard | 8501 | 8502 |
| API | 8000 | 8001 |
| Nginx | 80/443 | 80/443 |
