# 🚀 Quick Start Guide

## Step 1: Push to GitHub

Run these commands in the project folder:

```bash
cd ~/.openclaw/workspace/global-news-24h

# Add remote (replace with your repo URL)
git remote add origin https://github.com/fuoweineng/global-news-24h.git

# Push to GitHub
git push -u origin main
```

## Step 2: Enable GitHub Pages

1. Go to: **https://github.com/fuoweineng/global-news-24h/settings/pages**
2. Under **Build and deployment**:
   - **Source**: GitHub Actions
3. Click **Save**

## Step 3: Configure Actions Permissions

1. Go to: **https://github.com/fuoweineng/global-news-24h/settings/actions**
2. Under **Workflow permissions**:
   - ✅ **Read and write permissions**
   - ✅ **Allow GitHub Actions to create and approve pull requests**
3. Click **Save**

## Step 4: Trigger First Update

1. Go to: **https://github.com/fuoweineng/global-news-24h/actions**
2. Click **Update News** workflow
3. Click **Run workflow** → **Run workflow** (green button)
4. Wait ~1-2 minutes for completion

## Step 5: Visit Your Site

After the workflow completes:

**https://fuoweineng.github.io/global-news-24h/**

---

## ⚠️ Troubleshooting

### News not showing?
- Check **Actions** tab for workflow status
- Ensure `data/news.json` was generated
- Wait for first workflow run to complete

### 404 Error?
- GitHub Pages may take 1-2 minutes to deploy
- Refresh the page after a few minutes
- Check **Settings → Pages** for deployment status

### Workflow fails?
- Check the workflow logs for errors
- Ensure RSS URLs in `src/sources.json` are valid
- Verify `requirements.txt` dependencies

---

## 📝 Next Steps

- [ ] Customize news sources in `src/sources.json`
- [ ] Adjust styling in `docs/css/style.css`
- [ ] Add custom domain (optional)
- [ ] Share your site!

---

**Questions?** Check the main [README.md](README.md) or open an issue on GitHub.
