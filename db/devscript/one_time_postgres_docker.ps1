# !! DON'T USE IN PRODUCTION !!
Write-Host "WARNING: This script is intended for development use only. Do NOT use in production!" -ForegroundColor Yellow

# Get the absolute path to the migrations directory
$scriptPath = Split-Path -Parent $PSCommandPath
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptPath)
$migrationsPath = Join-Path $projectRoot "db\migrations"

# Verify migrations directory exists
if (-not (Test-Path $migrationsPath)) {
    Write-Host "Migrations directory not found at: $migrationsPath" -ForegroundColor Red
    exit 1
}

Write-Host "Migrations directory: $migrationsPath" -ForegroundColor Cyan

# Start a temporary PostgreSQL Docker container
Write-Host "Starting PostgreSQL Docker container..." -ForegroundColor Cyan
docker run --rm --name temp-postgres `
    -e POSTGRES_PASSWORD=vks_db_pwd `
    -e POSTGRES_USER=vks_db_user `
    -e POSTGRES_DB=vks_db `
    -d -p 5432:5432 `
    postgres:18-bookworm

# Wait for PostgreSQL to be ready
Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

# Test database connection
Write-Host "Testing database connection..." -ForegroundColor Cyan
$maxRetries = 5
$retryCount = 0
$connected = $false

while ($retryCount -lt $maxRetries -and -not $connected) {
    docker exec temp-postgres pg_isready -U vks_db_user -d vks_db 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $connected = $true
        Write-Host "Database is ready!" -ForegroundColor Green
    }
    else {
        $retryCount++
        Write-Host "Waiting for database... ($retryCount/$maxRetries)" -ForegroundColor Yellow
        Start-Sleep -Seconds 3
    }
}

if (-not $connected) {
    Write-Host "Failed to connect to database" -ForegroundColor Red
    docker logs temp-postgres
    exit 1
}

# Run Flyway migrations
Write-Host "Running Flyway migrations..." -ForegroundColor Cyan
docker run --rm `
    --name temp-flyway `
    --network host `
    -v "${migrationsPath}:/flyway/sql:ro" `
    flyway/flyway:11-alpine `
    -url=jdbc:postgresql://localhost:5432/vks_db `
    -user=vks_db_user `
    -password=vks_db_pwd `
    -connectRetries=5 `
    migrate

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database migrations completed successfully!" -ForegroundColor Green
}
else {
    Write-Host "Failed to run database migrations" -ForegroundColor Red
    exit 1
}

# Display connection information
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "PostgreSQL Container Information" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Container Name: temp-postgres" -ForegroundColor Yellow
Write-Host "Host: localhost" -ForegroundColor Yellow
Write-Host "Port: 5432" -ForegroundColor Yellow
Write-Host "Database: vks_db" -ForegroundColor Yellow
Write-Host "User: vks_db_user" -ForegroundColor Yellow
Write-Host "Password: vks_db_pwd" -ForegroundColor Yellow
Write-Host "Connection String: postgresql://vks_db_user:vks_db_pwd@localhost:5432/vks_db" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

# Enter PostgreSQL interactive shell
Write-Host "Entering PostgreSQL interactive shell..." -ForegroundColor Cyan
Write-Host "Type '\q' or 'exit' to quit psql and stop containers`n" -ForegroundColor Yellow

# Setup cleanup function
$cleanupContainers = {
    Write-Host "`n`nCleaning up containers..." -ForegroundColor Cyan
    
    # Stop Flyway container (if still running)
    Write-Host "Stopping Flyway container..." -ForegroundColor Yellow
    docker stop temp-flyway 2>&1 | Out-Null
    
    # Stop PostgreSQL container (will be automatically removed due to --rm flag)
    Write-Host "Stopping temp-postgres container..." -ForegroundColor Yellow
    docker stop temp-postgres 2>&1 | Out-Null
    
    Write-Host "Cleanup completed!" -ForegroundColor Green
}

# Register cleanup on script exit
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanupContainers

# Execute psql in interactive mode
try {
    docker exec -it temp-postgres psql -U vks_db_user -d vks_db
    
    # After exiting psql, cleanup
    & $cleanupContainers
}
catch {
    Write-Host "Error during psql session: $_" -ForegroundColor Red
    & $cleanupContainers
    exit 1
}
finally {
    # Unregister the event
    Unregister-Event -SourceIdentifier PowerShell.Exiting -ErrorAction SilentlyContinue
}

