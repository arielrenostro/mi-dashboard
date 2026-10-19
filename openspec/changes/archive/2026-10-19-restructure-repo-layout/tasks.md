## 1. Baseline

- [x] 1.1 Run the full suite from the current root (`.venv-wsl/bin/python -m pytest`) and record that it passes, so a later failure is known to come from the move
- [x] 1.2 Delete every `__pycache__` outside the venvs and `.pytest_cache`, and verify `git status` is clean before moving anything

## 2. Move the files (one commit, renames only)

- [x] 2.1 Create `dashboard/` and `git mv` into it `main.py`, `app/`, `tests/`, `resources/`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini` and `config.json`; verify `git status` lists only renames and the root no longer holds them
- [x] 2.2 `git mv assets docs`; verify `docs/` holds `demo.png`, `demo.mp4`, `ve_calibration.png`, `ignition_tuning.png`
- [x] 2.3 `git mv log_stream.csv dashboard/tests/data/log_stream.csv`; verify the file exists there and `tests/helpers.py` is the only file that names it
- [x] 2.4 Create `inclinometer/` with an empty placeholder README (filled in group 4); verify the directory is tracked
- [x] 2.5 Recreate the environment inside `dashboard/` (`python3 -m venv .venv-wsl` and the pip line from `CLAUDE.md`), run `.venv-wsl/bin/python -m pytest` from `dashboard/` and verify the suite passes with no source edits

## 3. Fix references

- [x] 3.1 Update `.gitignore`: `.venv-wsl/` and `.venv` become `dashboard/.venv*`; verify `git check-ignore dashboard/.venv-wsl dashboard/.venv` prints both
- [x] 3.2 Update the comment in `dashboard/tests/helpers.py` to name `tests/data/log_stream.csv`; verify the full suite still passes
- [x] 3.3 Update `CLAUDE.md`: run and test commands start with `cd dashboard`, "Code layout" shows the new tree (`dashboard/`, `inclinometer/`, `docs/`, `openspec/`), venv paths and the `config.json`/`resources/` note say "in `dashboard/`"; verify with `grep -n "main.py\|pytest\|requirements" CLAUDE.md` that no command lacks the `dashboard/` context
- [x] 3.4 Update `openspec/config.yaml` (`context` and `rules` mention `tests/`, `tests/test_<capability>.py`, `tests/test_app_configuration.py` and `python -m pytest`) so they name `dashboard/tests/` and run from `dashboard/`; verify `openspec list --specs` still works
- [x] 3.5 Grep `.claude/` (skills and commands) and `openspec/specs/` for paths of moved files (`tests/`, `resources/`, `assets/`, `main.py`, `requirements`) and fix only the ones that point at moved paths; verify the grep shows no stale reference (specs expected to need no change)

## 4. Documentation

- [x] 4.1 Write `inclinometer/README.md`: the device (Arduino with MPU-6500, 115200 8N1, 100 Hz), the line protocol table (`#D`, `#H`, `#M`, `#Z`, `#C`), zero and gyroscope-recalibration semantics from the device side, and a note that the firmware code is not in the repository yet; verify every protocol line matches `openspec/specs/gyro-connection/spec.md`
- [x] 4.2 Write `dashboard/README.md` from the current README sections "Requirements" to "Specifications" plus the app-side feature detail (VE map calibration, ignition tuning, inclinometer setup / zero / sampling rules / inclination box), reaching the images with `../docs/...` and linking `../inclinometer/README.md` for the device and protocol; verify the installation, running and test commands start from `dashboard/`
- [x] 4.3 Rewrite the root `README.md`: title and intro, demo (`docs/demo.png`, `docs/demo.mp4`), the general feature list, a repository layout block and links to `dashboard/README.md`, `inclinometer/README.md` and `openspec/`; verify it holds no installation or screen-by-screen detail
- [x] 4.4 Run a link check over the three READMEs (every relative link and image target exists, anchors point at existing headings) with a small script in the scratchpad and verify it reports zero broken links

## 5. Final verification

- [x] 5.1 Delete every `__pycache__` and `.pytest_cache`, then run `.venv-wsl/bin/python -m pytest` from `dashboard/` and verify the whole suite passes
- [ ] 5.2 Verify manually, on the Windows machine, that after recreating `.venv` in `dashboard/` the app starts from `dashboard/` (`.venv\Scripts\python main.py`), the sounds in `config.json` still resolve, and the Settings screen still saves to `dashboard/config.json` (real hardware, audio and display cannot be unit tested)
- [x] 5.3 Verify `git status` shows the moves as renames (`git status --short | grep '^R'`) and that `git log --follow dashboard/app/config.py` still reaches the pre-move history
- [x] 5.4 Tell the user which launchers, shortcuts or scripts outside the repository must now start from `dashboard/`
