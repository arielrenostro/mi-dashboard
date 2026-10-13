## Context

The label function tests `x == 1`; the top bar tests `data.value == 1`. The graph range of the signal is already 0 to 2.

## Goals / Non-Goals

**Goals:** make value `2` read as a closed state everywhere it is shown.

**Non-Goals:** changing graph range, alarms, or the VE lambda dot rule.

## Decisions

- Label text is `Closed+C` (closed + automatic correction). The first choice, `Closed+Corr`, was measured and rejected: it is about twice as wide as `Closed` and made the seven-card top bar need roughly 245 px more than before, which would not fit screens of 1600 px or less. `Closed+C` roughly halves that extra width (about +120 px over `Closed` instead of about +245 px, measured with a wider fallback font) and still separates value 2 from value 1. It is a single place in the label function, so it can be renamed cheaply.
- Green for both closed values; the label distinguishes them.

## Risks / Trade-offs

- [Wider label may not fit the large top-bar card] -> mitigated by the short label (about +120 px over the `Closed` case). Screens narrower than the existing `Closed` case already needed (about 1400 px estimated with Arial) were not supported before this change either.
