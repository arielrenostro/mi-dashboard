## Why

On connect the serial source requests only VE rows `#F01` to `#F15`. The highest-MAP row (row index 15) is never loaded from the ECU, so on real hardware the table and the interpolation for high MAP use zeros, and a reset or edit there would write wrong data. The mock loads all 16 rows, which hides the defect. Known issue K1. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- The connect and synchronize sequence requests all 16 VE rows (`#F01` to `#F16`).

## Capabilities

### New Capabilities

### Modified Capabilities

- `ecu-connection`: the sequence requests all 16 VE rows, with a scenario for the highest-MAP row.

## Impact

- `app/ecu_connection/serial.py` (`_fetch_ve_map` loop bound). No new dependencies, no config change.
