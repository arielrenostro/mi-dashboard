## Context

`_fetch_ve_map` iterates `range(1, 16)`, which yields rows 1 to 15. Row N maps to VE map index N-1, so index 15 stays at its initial zeros.

## Goals / Non-Goals

**Goals:** load all 16 rows during synchronization.

**Non-Goals:** changing retry behavior, reconnect behavior or what happens to unsent edits when rows are reloaded (known issue K4).

## Decisions

- Change the loop bound to include row 16. Alternative considered: iterate the enum members of the row commands; rejected as it spreads the row count over two places for no benefit.

## Risks / Trade-offs

- [One more request/response on every connect and reconnect] -> negligible compared with the existing 15.
