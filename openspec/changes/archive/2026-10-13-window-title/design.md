## Context

`AppWindow` is created full-screen without a title; the title is only visible in task switchers and similar.

## Goals / Non-Goals

**Goals:** set the title once at window creation.

**Non-Goals:** per-screen titles or a configurable title.

## Decisions

- Hardcode the title in `AppWindow`, consistent with the other fixed UI strings.
