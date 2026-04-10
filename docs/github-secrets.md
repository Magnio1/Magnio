# GitHub Secrets Setup

## Workload Identity Federation (Recommended)

This project uses **Workload Identity Federation** instead of service account keys for enhanced security. No service account keys are needed!

### How It Works

1. GitHub Actions authenticates using OpenID Connect (OIDC)
2. Google Cloud verifies the GitHub repository identity
3. The repository is granted permission to impersonate a service account
4. No long-lived credentials are stored in GitHub

### Required GitHub Secrets

Only one secret is needed:

#### `VITE_API_BASE_URL`
- **Purpose:** API endpoint for the frontend build
- **Value:** `https://magnio-api-903156424574.us-central1.run.app`

### How to Add the Secret

1. Go to your GitHub repository
2. Click **Settings** tab
3. Click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter name: `VITE_API_BASE_URL`
6. Enter value: `https://magnio-api-903156424574.us-central1.run.app`
7. Click **Add secret**

## Workload Identity Configuration

The following resources have been created:

### Workload Identity Pool
- **Name:** `github-pool`
- **Location:** Global
- **Purpose:** Groups GitHub Actions identities

### Workload Identity Provider
- **Name:** `github-provider`
- **Issuer:** `https://token.actions.githubusercontent.com`
- **Attribute Condition:** `assertion.repository_owner=='Magnio1'`
- **Purpose:** Verifies GitHub repository identity

### Service Account Permissions
- **Service Account:** `magnio-deploy@magnio-rtdb.iam.gserviceaccount.com`
- **Role:** `roles/iam.workloadIdentityUser`
- **Principal:** `principalSet://iam.googleapis.com/projects/903156424574/locations/global/workloadIdentityPools/github-pool/attribute.repository/Magnio1/magnio`

## Verification

After pushing changes, the workflows will automatically authenticate using Workload Identity Federation:
- Frontend changes → `deploy-frontend.yml` runs
- Backend changes → `deploy-backend.yml` runs

No manual secret configuration is needed beyond the `VITE_API_BASE_URL`!
