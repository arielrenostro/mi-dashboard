## Context

The label function tests `x == 1`; the top bar tests `data.value == 1`. The graph range of the signal is already 0 to 2.

## Goals / Non-Goals

**Goals:** make value `2` read as a closed state everywhere it is shown.

**Non-Goals:** changing graph range, alarms, or the VE lambda dot rule.

## Decisions

- Label text `Closed+Corr` follows the wording used when the value was defined (closed + automatic correction). It is a single place in the label function, so it can be renamed cheaply.
- Green for both closed values; the label distinguishes them.

## Risks / Trade-offs

- [Wider label may not fit the large top-bar card] -> check on the VE screen at full size.
