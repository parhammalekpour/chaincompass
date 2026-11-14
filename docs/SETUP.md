# Windows setup

1. Open PowerShell as Administrator, go to the ChainCompass folder, and run:

   ```powershell
   .\scripts\setup-windows.ps1
   ```

   The script checks for Git, Node.js LTS, Python 3.12, Docker Desktop, and Ollama
   before installing missing tools with `winget`. It also enables WSL without a
   Linux distribution and creates `%USERPROFILE%\.wslconfig` if it does not exist.

2. Reboot Windows if the script says a reboot is needed. A reboot is needed after
   WSL installation.

3. If you choose the optional Docker PostgreSQL setup, start Docker Desktop from
   the Start menu and wait until it reports that Docker is running. PostgreSQL
   can instead run natively on Windows; develop the app natively either way.

4. If you use Docker and Docker Hub downloads are slow or unavailable, connect
   to a trusted VPN before pulling images. Depending on your network, you may
   need to restart Docker Desktop after connecting.

5. Open a new PowerShell window and verify the tools:

   ```powershell
   node -v
   python --version
   docker --version
   ollama --version
   ```

## Manual installation (if winget is unavailable)

Install these tools from their official download sources:

- **Node.js LTS >= 20.9** (Node.js 22 recommended): download the Windows `.msi` from [nodejs.org](https://nodejs.org/).
- **Python 3.12:** download from [python.org](https://www.python.org/downloads/).
- **Git:** download from [git-scm.com](https://git-scm.com/download/win).
- **Docker Desktop** with the WSL 2 backend: download from [docker.com](https://www.docker.com/products/docker-desktop/).
- **Ollama** (optional until the AI agent step): download from [ollama.com](https://ollama.com/download).

After installing Node.js, close and reopen all PowerShell windows and VS Code so
they load the updated PATH.

### Verify

Run these commands in a new PowerShell window:

```powershell
node -v
npm -v
python --version
git --version
docker info --format "{{.ServerVersion}}"
```

Docker Desktop is only required for the optional container setup. If Docker
reports a WSL issue, run `wsl --update` from Administrator PowerShell and
restart Windows.

### Optional WSL resource limits

Create `%USERPROFILE%\.wslconfig` with:

```ini
[wsl2]
memory=6GB
processors=4
```

Then apply the configuration with:

```powershell
wsl --shutdown
```

The `scripts/setup-windows.ps1` script is optional and requires `winget`.

## Native PostgreSQL on Windows

Docker is optional. For a native installation, install PostgreSQL 16 for
Windows from [postgresql.org](https://www.postgresql.org/download/windows/).
Install the **Microsoft Visual C++ Redistributable 2015–2022 (x64)** required by
the PostgreSQL binaries. Keep PostgreSQL's `bin` directory available by using
full paths in PowerShell if it is not in `PATH`:

```powershell
$pgBin = 'C:\Program Files\PostgreSQL\16\bin'
Get-Service postgresql*
& "$pgBin\postgres.exe" --version
& "$pgBin\psql.exe" --version
& "$pgBin\pg_isready.exe" -h localhost -p 5432
```

If the service is stopped, open Administrator PowerShell and start the service
reported by `Get-Service` (commonly `postgresql-x64-16`):

```powershell
Start-Service postgresql-x64-16
```

Create the project role and database. These commands prompt for the existing
`postgres` superuser password without putting it into command history. At the
`psql` prompt, set a project password using letters and digits only:

```powershell
$pgBin = 'C:\Program Files\PostgreSQL\16\bin'
& "$pgBin\psql.exe" -W -U postgres -h localhost -d postgres
```

In the interactive `psql` session:

```sql
CREATE ROLE chaincompass LOGIN;
\password chaincompass
CREATE DATABASE chaincompass OWNER chaincompass;
\connect chaincompass
GRANT USAGE, CREATE ON SCHEMA public TO chaincompass;
\quit
```

If the role or database already exists, omit its `CREATE` statement; use
`\password chaincompass` to set the project's local password. Verify the project
login interactively:

```powershell
& "$pgBin\psql.exe" -W -U chaincompass -h localhost -d chaincompass -c "select 1"
```

Set the root `.env` (never commit it) with matching values. Replace the example
password with the same project password entered above:

```dotenv
POSTGRES_USER=chaincompass
POSTGRES_PASSWORD=YOUR_LETTERS_AND_DIGITS_PASSWORD
POSTGRES_DB=chaincompass
DATABASE_URL=postgresql+asyncpg://chaincompass:YOUR_LETTERS_AND_DIGITS_PASSWORD@localhost:5432/chaincompass
```

Exit code `-1073741515` from `postgres.exe` indicates a missing Visual C++
runtime. Install the x64 Visual C++ Redistributable; do not copy DLLs into the
PostgreSQL installation directory.

## Optional Docker PostgreSQL

Docker Desktop is optional. To use its PostgreSQL 16 container, create the root
`.env` from `.env.example` and set local database credentials first. If Docker
Hub is slow or unreachable, connect to a trusted VPN before pulling the image.

```powershell
docker compose --env-file .env -f infra/docker-compose.yml up -d
```

## Getting Started

Run the following commands in PowerShell from the repository root. Choose either
native PostgreSQL above or the optional Docker service.

Create the ignored local environment file once, then replace the database and
JWT placeholders with local-only values. Keep the URL credentials matched to
the PostgreSQL variables:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Create the backend virtual environment and install its pinned runtime and
development dependencies:

```powershell
Set-Location backend
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the baseline migration, then start the API. Keep this PowerShell window open:

```powershell
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If port 8000 is already in use, run Uvicorn with `--port 8010` and use port
8010 when calling the API. Keep the port consistent with the backend target in
the Next.js rewrite (`frontend/next.config.ts`). The current Next.js config does
not define an API rewrite yet; if one is added, set its target to the same port.
There is not currently a single shared port setting, so update the Uvicorn
command and rewrite target together when changing ports.

Verify the API in another PowerShell window:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
```

For an API started on port 8010, use:

```powershell
Invoke-RestMethod http://localhost:8010/api/v1/health
```

In a separate PowerShell window, start the frontend from the `frontend`
directory (the repository root does not define npm scripts):

```powershell
Set-Location frontend
npm ci
npm run dev
```

## CI

GitHub Actions runs three jobs: frontend lint, typecheck, tests, and build;
backend migrations and schema-drift check plus Ruff, formatting, mypy, and
pytest against a temporary PostgreSQL 16 service; and Gitleaks secret scanning.
Ruff lint targets the application and tests; formatting checks the full backend,
including Alembic migrations.
Database-dependent backend tests skip locally when PostgreSQL is unavailable,
but fail in CI so a missing database cannot produce a green run without
exercising them.
