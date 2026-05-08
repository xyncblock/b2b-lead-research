# Easy Deployment Options

## Option 1: Render.com (Recommended - Free)

**Zero config, auto-deploy, free forever.**

### Steps:
1. Push your code to GitHub
2. Go to [render.com](https://render.com) → Sign up with GitHub
3. Click "New +" → "Blueprint"
4. Paste your repo URL
5. Render reads `render.yaml` and creates both environments
6. Done! You get URLs immediately.

### URLs (auto-generated):
- Dev: `https://b2b-leads-dev.onrender.com`
- Staging: `https://b2b-leads-staging.onrender.com`

### Staging Approval:
- Dev auto-deploys on every push
- Staging requires you to click "Deploy" in Render dashboard
- Or I can set up a Telegram approval bot

---

## Option 2: Streamlit Cloud (Free)

**Best for Streamlit apps, super simple.**

### Steps:
1. Push to GitHub
2. Go to [streamlit.io/cloud](https://streamlit.io/cloud)
3. Sign in with GitHub
4. Click "New app"
5. Select repo, branch, and file (`dashboard/app.py`)
6. Deploy!

### Limitations:
- Only hosts the dashboard (not API backend)
- No staging environment (just one app)
- Good for quick demos

---

## Option 3: Railway.app (Free Tier)

**Modern, easy, good free tier.**

### Steps:
1. Push to GitHub
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub repo
4. Add environment variables
5. Deploy

---

## Option 4: Fly.io (Free Allowance)

**More control, still easy.**

### Steps:
1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. `fly launch` in your project
3. `fly deploy`

---

## Recommended: Render.com

Why Render:
- ✅ Free forever (with limits)
- ✅ Auto-deploy from Git
- ✅ Custom domains
- ✅ Environment variables
- ✅ Multiple services
- ✅ Staging + Dev out of the box
- ✅ No credit card required

### Free Tier Limits:
- Web services: 512 MB RAM, 0.1 CPU
- Spins down after 15 min idle (wakes on request)
- 100 GB bandwidth/month
- Perfect for development

### Upgrade Later:
- $7/month gets you always-on, more power
- Still way cheaper than managing a server

---

## Setup Checklist

- [ ] Push code to GitHub
- [ ] Sign up on Render.com with GitHub
- [ ] Deploy blueprint
- [ ] Add API keys in Render dashboard
- [ ] Test both environments
- [ ] Share URLs with team

## Staging Approval on Render

Since Render doesn't have built-in approval gates, you have two options:

### Option A: Manual (Simple)
- Set `autoDeploy: false` in `render.yaml`
- When you want to deploy staging, click "Manual Deploy" in Render dashboard

### Option B: Telegram Bot (Automated)
- I can create a bot that:
  1. Detects push to staging branch
  2. Sends you Telegram message
  3. You reply "approve" or "deny"
  4. Bot triggers Render deploy via API

Want me to set up Option B?
