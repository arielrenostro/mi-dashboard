## Context

See proposal.md for why. Facts that shape the approach:

- The app reads `config.json` from the working directory (or `MI_DASHBOARD_CONFIG_FILE`) and `config.json` points at sounds as `resources/alarm.wav`, `resources/closed.wav`, ... relative to the working directory. Only `app/config.py` reads the file and nothing in `app/` or `main.py` builds a path from `__file__`, so no source edit is needed as long as `config.json`, `resources/` and the working directory stay together.
- `pytest.ini` uses `testpaths = tests` and `pythonpath = .`, both relative to the file.
- `.venv` and `.venv-wsl` are git-ignored (no tracked venv files); `.venv-wsl/` is listed in `.gitignore`.
- Only `app-configuration` and `settings-screen` specs mention `config.json`, always as "the current working directory". No spec cites a repository path.
- `log_stream.csv` is used by no test; `tests/helpers.py` only cites it as the origin of `SAMPLE_FRAME`.
- The Arduino firmware does not exist on this machine yet. The inclinometer protocol is specified in `openspec/specs/gyro-connection/spec.md` and documented in the README section "Inclinometer (optional)".

## Goals / Non-Goals

**Goals:**
- One folder per project (`dashboard/`, `inclinometer/`), shared things (docs, OpenSpec, Claude config) at the root.
- A root README that explains the system and links to the details, and a README per project.
- No behavior change, no edit to anything under `app/` or `main.py`.
- The full suite passes from `dashboard/` and every relative link in the READMEs resolves.

**Non-Goals:**
- Writing or importing the Arduino firmware.
- Splitting `openspec/` per project or changing any spec requirement.
- Making `pytest` or the app runnable from the repository root (no wrapper scripts, no root-level `pytest.ini`).
- Reworking the content of the documentation beyond moving and re-linking it.

## Decisions

**1. `config.json` and `resources/` move into `dashboard/`, and the app runs from `dashboard/`.**
Alternative: keep `config.json` at the root and set `MI_DASHBOARD_CONFIG_FILE`, or rewrite the sound paths. Rejected: it spreads the app's files over two places and changes a file the app writes. Moving them together keeps every relative path valid with zero code edits.

**2. `openspec/`, `CLAUDE.md` and `.claude/` stay at the root.**
Decided with the user. The specs already cover the Arduino side (`gyro-connection`), so the Arduino project can get specs later without moving anything. `CLAUDE.md` and `openspec/config.yaml` are updated to say that commands run from `dashboard/`.

**3. `assets/` becomes `docs/`.**
Only the root README uses the images; `dashboard/README.md` reaches them with `../docs/...`. Alternative: leave `assets/` and keep the name. Rejected: the user asked for a documentation folder and `docs/` is the conventional name.

**4. `git mv` for every move, in one commit separate from the README rewrite.**
Keeps rename detection and history. A moves-only commit is easy to review (all renames, no content edits); the doc and reference edits follow in a second commit.

**5. README split by audience.**
- Root: title, demo image/video, the general features list (the bullets as they are today, shortened where they only repeat screen detail), a repository layout block, links to `dashboard/README.md` and `inclinometer/README.md`, and the OpenSpec note.
- `dashboard/README.md`: the sections from "VE map calibration", "Ignition tuning", "Requirements" through "Keyboard shortcuts" and "Specifications", with the inclinometer section reduced to the app side (setup, manual zero, when the analysis samples, the inclination box) plus a link to the inclinometer README for the device and protocol.
- `inclinometer/README.md`: the device (Arduino with MPU-6500, 115200 8N1, 100 Hz), the line protocol table (`#D`, `#H`, `#M`, `#Z`, `#C`), the zero and recalibration semantics from the device's point of view, and a note that the firmware code is not in the repository yet.

**6. Mixed content stays in one place.** The inclination box table is app behavior and stays in `dashboard/README.md`; the protocol table is device behavior and moves to `inclinometer/README.md`. Neither is duplicated; each links to the other.

**7. `log_stream.csv` goes to `dashboard/tests/data/`.**
Alternative: delete it. Moving keeps the provenance of `SAMPLE_FRAME` at the cost of a 17 KB file; `tests/helpers.py` comment is updated to name the new path.

**8. Virtual environments are recreated by the user, not moved by the change.**
They are git-ignored and absolute-path-sensitive (a venv breaks when moved). `.gitignore` gets `dashboard/.venv*`, and the README and `CLAUDE.md` say to create the environment inside `dashboard/`.

## Risks / Trade-offs

- [Broken relative links in the READMEs and a stale path in `CLAUDE.md`] → a task greps for `assets/`, `resources/`, `tests/`, `main.py` and `requirements` outside `dashboard/` and checks that every markdown link target exists.
- [`pytest` run from the root silently collects nothing or fails on imports] → document "run from `dashboard/`" in `CLAUDE.md`, `openspec/config.yaml` and `dashboard/README.md`; the suite is verified from `dashboard/`.
- [Existing venvs stop working after the move] → called out in the README and in the migration steps; nothing tracked is affected.
- [Windows launch shortcuts or scripts outside the repo that call `.venv\Scripts\python main.py` from the root] → not visible from here; the user updates them (listed in Migration Plan).
- [Stale `__pycache__` or `.pytest_cache` after the move masking results] → delete them after moving (already a rule in `CLAUDE.md`).
- [`.claude/skills` and `.claude/commands` mention `tests/` or root paths] → a task greps them and fixes only references that name moved paths.

## Migration Plan

1. Do the moves with `git mv` in one commit, then fix references and docs in a second commit.
2. In each working copy: `cd dashboard`, recreate `.venv` (Windows) or `.venv-wsl` (WSL) with the commands in `dashboard/README.md`, then run the suite.
3. Update any launcher or shortcut outside the repository to start from `dashboard/`.
4. Rollback: `git revert` the two commits (moves are renames, so the revert restores the old layout); recreate the old venvs.
