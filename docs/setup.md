# Setup

Paperflow combines operating-system tools with a locked Python environment. Install the system
tools first; `uv` then creates and manages the project-specific `.venv` automatically.

## 1. Install the system tools

| Tool | Required | Purpose |
| --- | --- | --- |
| [Git](https://git-scm.com/downloads) | Yes | Version control and review baselines |
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | Yes | Python provisioning, dependency locking, and command execution |
| [Quarto CLI](https://quarto.org/docs/get-started/) | Yes | QMD rendering and DOCX generation |
| Python 3.11+ | Yes | Runs Paperflow; `uv` can provision a compatible version |
| Microsoft Word | No | Needed only to edit or review the generated DOCX files |

Quarto includes a compatible Pandoc version. A separate Pandoc installation is not required.

After installation, open a new terminal and verify the tools:

```bash
git --version
uv --version
quarto --version
```

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

If Git, `uv`, and Quarto are on `PATH`, no local executable settings are needed. Otherwise, copy
`paperflow.local.example.yml` to `.paperflow.local.yml` and enter the executable paths there.

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
