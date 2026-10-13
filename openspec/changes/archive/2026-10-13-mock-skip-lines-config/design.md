## Context

`EcuConnectionMock.run` counts data lines in `self.line`, which keeps growing across replays, and skips lines while the counter is below a literal. Because the counter is never reset, the skip applies to the first pass only; later replays start from the first data line.

## Goals / Non-Goals

**Goals:** make the skip configurable and default to no skip.

**Non-Goals:** fixing the dead own-format branch (format check and timestamp pacing) or the canned breakpoint replies in the mock; those remain part of K12 and are left for a separate change.

## Decisions

- Keep "first pass only" semantics, because it preserves current behavior and only replaces the literal with a setting. Alternative considered: apply the skip on every restart so the loop always replays the interesting region; deferred, easy to add later.
- Default `0`, so a fresh checkout replays the whole file.
- Key name `connection.mock_skip_lines`, next to `connection.mock`.

## Risks / Trade-offs

- [Personal config relies on the old implicit skip] -> mention it in the proposal and set the value in the maintainer's `config.json` when applying.
