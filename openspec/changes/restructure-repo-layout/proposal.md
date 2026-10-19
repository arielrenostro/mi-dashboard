## Why

The repository root mixes the Python app (`app/`, `main.py`, `tests/`, `requirements*.txt`, `pytest.ini`, `config.json`, `resources/`), the documentation and media (`README.md`, `assets/`), the OpenSpec workflow and a stray sample CSV. The inclinometer firmware (Arduino) is a separate project that is about to live in the same repository, and one 26 KB README describes only the Python side. Splitting the repository by project now keeps each project self-contained and gives the Arduino project a place to land.

## What Changes

- Create `dashboard/` and move into it, with `git mv`: `main.py`, `app/`, `tests/`, `resources/`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini` and `config.json`. The virtual environments (`.venv`, `.venv-wsl`) are recreated inside `dashboard/`.
- Create `inclinometer/` with a `README.md` only: the inclinometer hardware, serial protocol, commands and calibration. The firmware code is not in this change.
- Rename `assets/` to `docs/` (`demo.png`, `demo.mp4`, `ve_calibration.png`, `ignition_tuning.png`).
- Split the README in three:
  - `README.md` (root): what the system is, the demo, the general features, the repository layout and links to the two projects.
  - `dashboard/README.md`: requirements, installation, running, tests, configuration, screens, keyboard shortcuts.
  - `inclinometer/README.md`: the inclinometer device (hardware, protocol, commands, calibration).
- Keep `openspec/`, `CLAUDE.md` and `.claude/` at the root. Update `CLAUDE.md` (run and test commands, "Code layout", venv paths), `openspec/config.yaml` (`context` and `rules` that cite `tests/` and `python -m pytest`), `.gitignore` and the comment in `tests/helpers.py`.
- Move `log_stream.csv` (a sample cited only by a comment) to `dashboard/tests/data/`.
- The app and the tests must now be started from `dashboard/` (`pytest.ini` and the working-directory `config.json` and `resources/...` paths depend on it).

No application behavior changes and no source file under `app/` is edited.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `app-configuration` and `settings-screen` mention `config.json` in "the current working directory", which stays true when the app runs from `dashboard/`. The change sets `skip_specs: true`.

## Impact

- Paths: every file listed above moves; Windows users run `cd dashboard` before `.venv\Scripts\python main.py`.
- Docs: the three READMEs, `CLAUDE.md`, `openspec/config.yaml`.
- Local environments: `.venv` and `.venv-wsl` are git-ignored and must be recreated (or moved) under `dashboard/`.
- Tooling: `pytest` only works from `dashboard/`.
- Git history is preserved for moved files (`git mv`).
