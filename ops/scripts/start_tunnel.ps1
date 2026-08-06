if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) { throw "cloudflared is not installed or not in PATH." }
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$config = Join-Path $RepoRoot "ops\cloudflare\config.yml"
if (-not (Test-Path $config)) { throw "Create ops/cloudflare/config.yml from config.yml.example first." }
cloudflared tunnel --config $config ingress validate
cloudflared tunnel --config $config run sitegit-local
