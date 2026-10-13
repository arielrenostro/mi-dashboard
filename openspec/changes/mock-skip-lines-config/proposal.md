## Why

The mock source skips the first 12249 data lines through a hardcoded debug offset, used to reach an interesting region of a long log. With any shorter file it emits nothing at first, and the value cannot be changed without editing code. Known issue K12 (offset part). See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- New setting `connection.mock_skip_lines` (default `0`): number of data lines the mock skips on its first pass.
- The hardcoded offset is removed.
- **BREAKING (dev only):** existing setups relying on the implicit 12249-line skip must set `connection.mock_skip_lines` to `12249`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `app-configuration`: new `connection.mock_skip_lines` setting.
- `ecu-connection`: "Mock replay" skips the configured number of lines on the first pass.

## Impact

- `app/config.py`, `app/ecu_connection/mock_log.py`, `main.py` (constructor argument), `README.md` configuration table, personal `config.json`.
