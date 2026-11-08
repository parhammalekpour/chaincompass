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
