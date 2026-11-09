# Windows setup with WSL 2

The supported Windows route is Ubuntu in WSL 2 with Docker Desktop's WSL 2 engine. `Run.command` is a macOS launcher; use the Bash commands below from Ubuntu on Windows. Git Bash alone is not a validated environment for this project.

## One-time setup

1. Follow [Microsoft's WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install). On a supported Windows version, run `wsl --install` in an administrator PowerShell window, restart if prompted, and create the Ubuntu account.
2. Install and start Docker Desktop. Enable its WSL 2 engine and Ubuntu integration under **Settings → Resources → WSL Integration**, following the [Docker WSL 2 documentation](https://docs.docker.com/desktop/features/wsl/). Use Linux containers.
3. Open the Ubuntu terminal and check `docker info` and `docker compose version`. Keep Docker Desktop running while using the project.
4. Clone inside the Ubuntu home directory when using the WSL 2 engine:

```bash
cd ~
git clone https://github.com/xingsun19/us-macroeconomic-pipeline-dashboard.git
cd us-macroeconomic-pipeline-dashboard
bash scripts/run.sh --prepare-offline
```

## Run the included snapshot

```bash
bash scripts/run.sh --offline
```

Open `http://localhost:8501` in your Windows browser. To find the saved HTML report, run `explorer.exe .` from the project directory and open `reports/offline/eda.html`. Press Return in Ubuntu when finished to stop project services. Docker Desktop itself remains open; quit it separately if no other projects need it.

## Run a live update

After preparation, edit `.env` in Ubuntu with `nano .env`, enter your own FRED API key after `FRED_API_KEY=`, save, and run:

```bash
bash scripts/run.sh
```

This guide uses the WSL 2 engine, not Docker VMM. The project's Linux containers and Bash paths are tested on Linux, but an actual Windows host was not available for end-to-end validation. Follow the upstream documentation for version-specific installation requirements.
