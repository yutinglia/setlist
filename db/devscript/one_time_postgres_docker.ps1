# Development-only, disposable PostgreSQL + Flyway + interactive psql.
$ErrorActionPreference = "Stop"

$containerName = "vks-temp-postgres"
$networkName = "vks-temp-network"
$dbName = "vks_db"
$dbUser = "vks_db_user"
$dbPassword = "vks_db_pwd"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$migrationsPath = Join-Path $projectRoot "db\migrations"
$startedContainer = $false
$createdNetwork = $false

if (-not (Test-Path -LiteralPath $migrationsPath)) {
    throw "Migrations directory not found: $migrationsPath"
}

$existingContainer = docker ps -a --filter "name=^/${containerName}$" --format "{{.Names}}"
if ($existingContainer) {
    throw "Container '$containerName' already exists; refusing to reuse or remove it."
}

$existingNetwork = docker network ls --filter "name=^${networkName}$" --format "{{.Name}}"
if ($existingNetwork) {
    throw "Network '$networkName' already exists; refusing to reuse or remove it."
}

try {
    docker network create $networkName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not create Docker network." }
    $createdNetwork = $true

    docker run --rm --name $containerName `
        --network $networkName `
        -e "POSTGRES_PASSWORD=$dbPassword" `
        -e "POSTGRES_USER=$dbUser" `
        -e "POSTGRES_DB=$dbName" `
        -p "127.0.0.1:5432:5432" `
        -d postgres:18-bookworm | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not start PostgreSQL container." }
    $startedContainer = $true

    Write-Host "Waiting for PostgreSQL..." -ForegroundColor Cyan
    $ready = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        docker exec $containerName pg_isready -U $dbUser -d $dbName 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw "PostgreSQL did not become ready in 30 seconds." }

    docker run --rm `
        --network $networkName `
        -v "${migrationsPath}:/flyway/sql:ro" `
        flyway/flyway:11-alpine `
        "-url=jdbc:postgresql://${containerName}:5432/${dbName}" `
        "-user=${dbUser}" `
        "-password=${dbPassword}" `
        "-locations=filesystem:/flyway/sql" `
        -connectRetries=5 `
        migrate
    if ($LASTEXITCODE -ne 0) { throw "Flyway migration failed." }

    Write-Host "PostgreSQL is available at 127.0.0.1:5432/$dbName." -ForegroundColor Green
    Write-Host "Exit psql with \q; the disposable container will then be removed." -ForegroundColor Yellow
    docker exec -it $containerName psql -U $dbUser -d $dbName
}
finally {
    if ($startedContainer) {
        docker stop $containerName 2>&1 | Out-Null
    }
    if ($createdNetwork) {
        docker network rm $networkName 2>&1 | Out-Null
    }
}
