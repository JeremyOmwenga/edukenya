<#
Creates the local EduKenya PostgreSQL role and database from the values in .env.
Run once from the project root:  .\scripts\setup_local_db.ps1
psql will ask for the password of the "postgres" superuser (set during install).

LOCAL ONLY: the role gets CREATEDB so Django can create its throwaway test
database. The production role on RDS will NOT have this.
#>
$ErrorActionPreference = "Stop"

$psql = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
if (-not $psql) { throw "psql.exe not found under C:\Program Files\PostgreSQL" }

# Read .env into a hashtable
$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) { throw ".env not found. Copy .env.example to .env first." }
$cfg = @{}
Get-Content $envFile | Where-Object { $_ -match '^\s*([A-Z_]+)\s*=\s*(.*)$' } | ForEach-Object {
    $cfg[$Matches[1]] = $Matches[2].Trim()
}
foreach ($k in "DB_NAME", "DB_USER", "DB_PASSWORD") {
    if (-not $cfg[$k]) { throw "$k is missing in .env" }
}
foreach ($k in "DB_NAME", "DB_USER") {
    if ($cfg[$k] -notmatch '^[a-z_][a-z0-9_]*$') { throw "$k must be a simple lowercase identifier" }
}
if ($cfg["DB_PASSWORD"].Contains("'")) { throw "DB_PASSWORD must not contain single quotes" }

$sql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$($cfg.DB_USER)') THEN
    CREATE ROLE $($cfg.DB_USER) LOGIN CREATEDB PASSWORD '$($cfg.DB_PASSWORD)';
  ELSE
    ALTER ROLE $($cfg.DB_USER) LOGIN CREATEDB PASSWORD '$($cfg.DB_PASSWORD)';
  END IF;
END
`$`$;
SELECT 'CREATE DATABASE $($cfg.DB_NAME) OWNER $($cfg.DB_USER)'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$($cfg.DB_NAME)')\gexec
"@

# Pass SQL on stdin so the password never appears in the process list
$sql | & $psql -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -q
if ($LASTEXITCODE -ne 0) { throw "psql failed (exit $LASTEXITCODE)" }
Write-Host "Role '$($cfg.DB_USER)' and database '$($cfg.DB_NAME)' are ready."
