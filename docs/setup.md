# Setup

Paperflow combines external tools with a locked Python environment. Users must install the
prerequisites themselves; Paperflow does not download, install, or update Git, `uv`, Quarto, or
Microsoft Word automatically. Afterward, `uv` creates and manages the project-specific `.venv`.

## 1. Install the system tools

| Tool | Required | Purpose |
| --- | --- | --- |
| [Git](https://git-scm.com/downloads) | Yes | Version control and review baselines |
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | Yes | Python provisioning, dependency locking, and command execution |
| [Quarto CLI](https://quarto.org/docs/get-started/) | Yes | QMD rendering and DOCX generation |
| Python 3.11+ | Yes | Runs Paperflow; `uv` can provision a compatible version |
| Microsoft Word | No | Needed only to edit or review the generated DOCX files |

Quarto includes a compatible Pandoc version. A separate Pandoc installation is not required.
Install `uv` and Quarto before running the Paperflow setup. A user-level installation is sufficient
when its executable is available on `PATH`; administrator-wide installation is not required.

After installation, open a new terminal and verify the tools:

```bash
git --version
uv --version
quarto --version
```

### Verified Windows setup without administrator rights

This setup was verified from a non-elevated Windows account. Paperflow does not perform any of
these installation steps automatically.

1. Install `uv` with the user-level method from the
   [official installation guide](https://docs.astral.sh/uv/getting-started/installation/). The
   verified installation placed `uv.exe` in `%USERPROFILE%\.local\bin`.
2. Download the Windows ZIP and its checksum file from the
   [official Quarto release page](https://github.com/quarto-dev/quarto-cli/releases). Verify the
   archive checksum before extracting it.
3. Extract Quarto into a user-writable directory. The verified installation used
   `%LOCALAPPDATA%\Programs\Quarto\<version>`.
4. Either add Quarto's `bin` directory to the user `PATH` or enter the existing executable in the
   ignored `.paperflow.local.yml`:

```yaml
executables:
  quarto: "C:/Users/<username>/AppData/Local/Programs/Quarto/<version>/bin/quarto.exe"
```

Close and reopen the terminal after changing the user `PATH`. Then run `uv --version`,
`quarto --version`, and later `uv run paperflow doctor`. No administrator-wide installation is
required.

## 2. Create the locked project environment

From the repository root, run:

```bash
uv sync --frozen --extra dev
```

This creates `.venv` and installs exactly the versions recorded in `uv.lock`. Do not run ad-hoc
`pip install` commands inside this environment.

Paperflow uses the standard Python packaging files:

- `pyproject.toml` declares direct runtime and development dependencies;
- `uv.lock` records the reproducible dependency resolution.

There is intentionally no committed `requirements.in` or `requirements.txt`. If an external tool
temporarily requires requirements format, generate it from the lock file instead of maintaining it
by hand:

```bash
uv export --frozen --format requirements-txt --output-file build/requirements.txt
```

Treat that export as a disposable compatibility artifact unless the project later adopts a
specific integration that requires it.

## 3. Configure machine-specific paths

If Git, `uv`, and Quarto are on `PATH`, no local executable settings are needed. Otherwise, install
them manually and then copy `paperflow.local.example.yml` to `.paperflow.local.yml` to enter the
executable paths. The configuration points to an existing installation; it never installs a tool.

PowerShell:

```powershell
Copy-Item paperflow.local.example.yml .paperflow.local.yml
```

macOS or Linux:

```bash
cp paperflow.local.example.yml .paperflow.local.yml
```

Example:

```yaml
executables:
  quarto: "C:/Program Files/Quarto/bin/quarto.exe"

word:
  reference_docx: "templates/reference.docx"
```

The local configuration, Word templates, generated documents, and review files are ignored by
Git. Do not commit confidential documents or machine-specific paths.

## 4. Validate and build

```bash
uv run paperflow doctor
uv run pytest
uv run paperflow build
```

A successful build creates:

- `build/paper.docx`;
- `build/open_items.md`;
- `build/open_items.docx`.

If `paperflow doctor` cannot find Quarto, restart the terminal after installing Quarto or configure
its executable explicitly in `.paperflow.local.yml`.
