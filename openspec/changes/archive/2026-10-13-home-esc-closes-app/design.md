## Context

`HomeScreen` receives a close callback (`AppWindow.close`) but its key handler only handles up, down and Enter. Other screens call their callback on ESC to return to Home.

## Goals / Non-Goals

**Goals:** ESC on Home exits the app through the existing close callback.

**Non-Goals:** confirmation dialogs; changing ESC on other screens.

## Decisions

- Reuse the existing close callback so shutdown follows the normal path (window closed, event loop ends, threads stopped by `main`).
- Keep the existing early return for auto-repeat events so a held ESC (used to leave another screen) does not exit immediately.

## Risks / Trade-offs

- [Accidental exit while driving] -> ESC from other screens first returns to Home; exit needs a second, separate press.
