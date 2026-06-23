# SME-GPT local development setup (Windows)
# Run once after cloning: .\setup-dev.ps1
#
# Creates a node_modules/tailwindcss junction at the repo root so Next.js 16
# Turbopack finds tailwindcss without walking up to C:\Users\<you>\package.json.

$repoRoot       = $PSScriptRoot
$frontendTarget = "$repoRoot\frontend\node_modules\tailwindcss"
$repoLink       = "$repoRoot\node_modules\tailwindcss"

if (-not (Test-Path $frontendTarget)) {
    Write-Host "Installing frontend dependencies first..."
    Push-Location "$repoRoot\frontend"; npm ci; Pop-Location
}

$nodeModulesDir = "$repoRoot\node_modules"
if (-not (Test-Path $nodeModulesDir)) {
    New-Item -ItemType Directory -Path $nodeModulesDir | Out-Null
}

if (-not (Test-Path $repoLink)) {
    cmd /c "mklink /J `"$repoLink`" `"$frontendTarget`"" | Out-Null
    Write-Host "Created junction: node_modules/tailwindcss -> frontend/node_modules/tailwindcss"
} else {
    Write-Host "Junction already exists."
}

Write-Host "Setup complete. Run 'cd frontend && npm run dev' to start."
