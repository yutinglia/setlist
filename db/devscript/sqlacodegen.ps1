$ErrorActionPreference = "Stop"

# Defaults match the disposable/local Compose database; DB_* can override them.
$dbUser = if ($env:DB_USER) { $env:DB_USER } else { "vks_db_user" }
$dbPassword = if ($env:DB_PASSWORD) { $env:DB_PASSWORD } else { "vks_db_pwd" }
$dbHost = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
$dbPort = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }
$dbName = if ($env:DB_NAME) { $env:DB_NAME } else { "vks_db" }
$escapedUser = [uri]::EscapeDataString($dbUser)
$escapedPassword = [uri]::EscapeDataString($dbPassword)
$connectionString = "postgresql://${escapedUser}:${escapedPassword}@${dbHost}:${dbPort}/${dbName}"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$modelsDir = Join-Path $projectRoot "data_updater\db"
$outputFile = Join-Path $modelsDir "models.py"

Write-Host "Generating models from database schema..."
Write-Host "Connection: postgresql://${dbUser}:***@${dbHost}:${dbPort}/${dbName}" -ForegroundColor Cyan
sqlacodegen $connectionString --generator dataclasses --noviews --outfile $outputFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully generated models.py in $modelsDir" -ForegroundColor Green
}
else {
    Write-Host "Failed to generate models" -ForegroundColor Red
    exit $LASTEXITCODE
}
