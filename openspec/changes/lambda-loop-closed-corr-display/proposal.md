## Why

The ECU reports lambda loop value `2` for "closed with automatic correction", but the UI treats only `1` as closed: the label shows `Open` and the top bar color is orange. Only the VE lambda dot already counts `2` as closed. Known issue K3. See the archived `baseline-existing-system` change (design.md, Known issues) for the full context.

## What Changes

- Display string for value `2` becomes `Closed+Corr` (value `1` stays `Closed`, anything else `Open`).
- The VE calibration top bar paints the lambda loop value green for `1` and `2`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `signal-model`: catalog display column and "Lambda loop values".
- `ve-calibration-screen`: "Top bar" color rule.

## Impact

- `app/masterinjection/signal.py` (`LAMBDA_LOOP` label), `app/ui/ve_calibration/screen.py` (`_update_top_bar`).
