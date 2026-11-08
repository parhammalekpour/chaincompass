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

3. Start Docker Desktop from the Start menu and wait until it reports that Docker
   is running. Docker Desktop is used for PostgreSQL and Mailpit; develop the app
   natively on Windows.

4. If Docker Hub downloads are slow or unavailable, connect to a trusted VPN
   before starting or using Docker Desktop. Depending on your network, you may
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

Docker Desktop must be running for the Docker command to return a server version.
If Docker reports a WSL issue, run `wsl --update` from Administrator PowerShell
and restart Windows.

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
