# Deploying BioAgent to Render

## Quick Start (5 minutes)

### 1. Push to GitHub
```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Create Render Account
- Go to [render.com](https://render.com)
- Sign up with GitHub

### 3. Deploy Using Blueprint
1. Click **New** → **Blueprint**
2. Connect your GitHub repo containing BioAgent
3. Render auto-detects `render.yaml`
4. Click **Apply**

### 4. Set Environment Variables
In Render Dashboard, go to **bioagent-api** → **Environment**:

| Variable | Value | Required |
|----------|-------|----------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | ✅ Yes |
| `NCBI_API_KEY` | Your NCBI key | Optional |
| `NCBI_EMAIL` | your@email.com | Recommended |

**Note:** Storage is consolidated - all uploads, results, and analysis data go to `BIOAGENT_WORKSPACE` (default: `/data/workspace` on Render's persistent disk).

### 5. Wait for Deployment
- Backend: ~5-10 minutes (installs ML dependencies)
- Frontend: ~3-5 minutes
- Database: ~2 minutes

## URLs After Deployment

- **Frontend**: `https://bioagent-web.onrender.com`
- **Backend API**: `https://bioagent-api.onrender.com`
- **API Docs**: `https://bioagent-api.onrender.com/docs`

---

## Cost Estimate

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Backend (API) | Standard | $25 |
| Frontend (Web) | Starter | $7 |
| Database | Basic | $7 |
| **Total** | | **~$39/month** |

*Note: Starter backend ($7) may work but has only 512MB RAM. Standard ($25) with 2GB RAM is recommended for the ML models.*

---

## Manual Deployment (Alternative)

If blueprint doesn't work, deploy manually:

### Backend
1. **New** → **Web Service**
2. Connect repo
3. Settings:
   - **Name**: bioagent-api
   - **Root Directory**: (leave empty)
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt && pip install -r webapp/backend/requirements.txt`
   - **Start Command**: `cd webapp/backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables

### Frontend
1. **New** → **Web Service**
2. Connect repo
3. Settings:
   - **Name**: bioagent-web
   - **Root Directory**: `webapp/frontend`
   - **Runtime**: Node
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `npm start`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `https://bioagent-api.onrender.com/api`

### Database
1. **New** → **PostgreSQL**
2. Name: bioagent-db
3. Copy the **Internal Connection String**
4. Add to backend as `DATABASE_URL`

---

## Troubleshooting

### "Out of Memory" Error
- Upgrade backend to **Standard** plan (2GB RAM)
- Or enable `BIOAGENT_FAST_MODE=true` to disable ML models

### "Module not found" Error
Check build logs - may need to adjust Python path:
```bash
export PYTHONPATH=/opt/render/project/src:$PYTHONPATH
```

### Database Connection Issues
- Ensure `DATABASE_URL` is set (from Render's PostgreSQL)
- Check the URL starts with `postgresql://` (Render auto-provides this)

### Slow Cold Starts
Render free/starter plans spin down after inactivity. First request after sleep takes ~30s.
- Solution: Upgrade to paid plan or use uptime monitoring to ping the service

---

## Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Set `BIOAGENT_FAST_MODE=true` (recommended for cloud)
- [ ] Configure `ALLOWED_ORIGINS` with your actual frontend URL
- [ ] Set up custom domain (optional)
- [ ] Enable Render's DDoS protection
- [ ] Set up health check alerts

---

## Updating

Push to GitHub and Render auto-deploys:
```bash
git add .
git commit -m "Update feature"
git push
```

Render watches your repo and redeploys on every push to main.
