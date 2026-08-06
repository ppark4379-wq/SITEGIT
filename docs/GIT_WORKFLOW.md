# Git workflow

Recommended private repository branches:

```text
main        stable demo / presentation
  └─ develop    team integration
       ├─ feature/frontend-shared-sync
       ├─ feature/backend-domain-models
       ├─ feature/isaac-adapter
       ├─ feature/conflict-engine
       └─ feature/cloudflare-deployment
```

Rules:

1. Do not commit `.env`, DB files, Cloudflare credentials, PCD, videos or logs.
2. Commit JSON contracts before independently implementing frontend and adapter changes.
3. Use Pull Requests into `develop`.
4. Merge `develop` into `main` only after local-server and fixed-URL smoke tests.
5. Tag presentation-safe versions, for example `v0.2-demo`.

Initial push:

```powershell
.\ops\scripts\init_git.ps1
git commit -m "chore: initialize SiteGit modular local shared platform"
git branch -M main
git remote add origin <PRIVATE_GITHUB_REPOSITORY_URL>
git push -u origin main
git checkout -b develop
git push -u origin develop
```
