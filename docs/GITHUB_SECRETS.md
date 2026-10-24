# GitHub Secrets Configuration

This document explains how to configure GitHub secrets for the CI/CD pipeline.

## Required Secrets

These are the secrets referenced by the workflows in `.github/workflows/`. Add them to your GitHub repository:

### Go to: Settings → Secrets and variables → Actions → Repository secrets

## Releases (`release-please.yml`)

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `RELEASE_PLEASE_TOKEN` | Fine-grained PAT for this repository with **Contents**, **Issues** and **Pull requests** read/write (Issues: release-please labels the release PR). Not `GITHUB_TOKEN`: PRs and releases created with it trigger no workflows, so the release PR would get no CI and the release would never deploy | `github_pat_...` |

## Backend Deployment (`deploy.yml`)

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `FLY_API_TOKEN` | Fly.io API token for deployment | `your-fly-api-token` |

## Frontend Deployment (`deploy.yml`)

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `VERCEL_TOKEN` | Vercel access token used by `vercel --prod` | `your-vercel-token` |
| `VERCEL_ORG_ID` | Vercel team/organization ID | `team_...` |
| `VERCEL_PROJECT_ID` | Vercel project ID | `prj_...` |

## Backend CI (`backend-ci.yml`, optional)

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `OPENAI_API_KEY` | Passed to the pytest step. Optional: tests mock OpenAI and `tests/conftest.py` overrides this variable with a test value | `sk-proj-...` |

`GITHUB_TOKEN` (used by `deploy.yml` to push the image to GHCR, and by `dependabot-auto-merge.yml` to merge) is provided automatically by GitHub Actions.

## Runtime Configuration (not GitHub secrets)

No workflow reads `DATABASE_URL`, `REDIS_URL`, `AWS_ENDPOINT_URL_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`, `AWS_REGION` or `TELEGRAM_BOT_TOKEN` from GitHub secrets. Backend CI uses hardcoded test values for these, and `fly.toml` only sets `USE_WEBHOOK`, `WEBHOOK_URL` and `ENABLE_WORKER`, so production values must be configured on the Fly.io app itself (e.g. `fly secrets set DATABASE_URL=...`).

## How to Add Secrets

1. Go to your GitHub repository
2. Click on **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter the secret name and value
6. Click **Add secret**

## Local Development

For local development, create a `.env` file in `backend/` (loaded by `services/config.py`) with the runtime variables listed above:

```bash
# Create .env from the template
cp backend/.env.example backend/.env

# Edit .env with your actual values
nano backend/.env
```

## CI/CD Pipeline Behavior

### Backend CI
- Runs on pull requests and pushes to `main` that touch `backend/**` (or the workflow file)
- Ruff lint, ruff format check, pyright, and the full pytest suite
- External services are mocked; no real service credentials required

### Frontend CI
- `frontend-ci.yml` runs on pull requests and pushes to `main` that touch `frontend/**`, plus manual dispatch

### Releases and Deploys
- Pushes to `main` do not deploy. `release-please.yml` keeps a release PR open; merging it publishes a `vX.Y.Z` release (requires `RELEASE_PLEASE_TOKEN`)
- `deploy.yml` runs on that release, waits for Backend CI and Frontend CI to pass on the release commit, pushes `ghcr.io/<owner>/<repo>:vX.Y.Z` (and `:latest`), deploys it to Fly.io, and deploys the frontend to Vercel
- To redeploy or roll back, run `deploy.yml` manually with an existing release tag
- Requires `FLY_API_TOKEN`, `VERCEL_TOKEN`, `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` secrets

## Security Notes

- Never commit `.env` files to the repository
- GitHub secrets are encrypted and only accessible during CI/CD runs
- Use different credentials for development, staging, and production
- Rotate secrets regularly
- Use least-privilege access for service accounts

## Troubleshooting

### Tests Failing
- Backend tests do not need real services; reproduce locally with `cd backend && make test`
- Check the ruff, ruff format and pyright steps, which run before pytest

### Deployment Failing
- Verify `FLY_API_TOKEN` (backend) or the `VERCEL_*` secrets (frontend) are set correctly
- Check Fly.io app configuration
- Ensure Docker image builds successfully

### Local Development Issues
- Copy `backend/.env.example` to `backend/.env`
- Fill in actual values in `.env` file
- Run `make dev` (from the repository root or `backend/`) to start the development server
