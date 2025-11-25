# !! Please activate conda env first !!
# !! WARNING: This script is intended for development use only. Do NOT use in production! !!

# Database connection info from one_time_postgres_docker.ps1
$dbUser = "vks_db_user"
$dbPassword = "vks_db_pwd"
$dbHost = "localhost"
$dbPort = "5432"
$dbName = "vks_db"
$connectionString = "postgresql://${dbUser}:${dbPassword}@${dbHost}:${dbPort}/${dbName}"

$modelsDir = "..\..\data_updater\db"
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
