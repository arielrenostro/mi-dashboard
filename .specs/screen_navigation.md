# Spec: Screen Navigation

Describes the multi-screen architecture: the main window, the screen base class, the home screen, and navigation rules.

Implementation: `app/ui/window.py`, `app/ui/base/screen.py`, `app/ui/home/screen.py`. Screens are self-registered inside `AppWindow._register_screens()` — no explicit wiring in `main.py` is required.

---

## Overview

The application uses a single full-screen `AppWindow` that contains a `QStackedWidget`. Each functional area (Dashboard, VE Calibration, etc.) is a `Screen` — a `QWidget` subclass — registered in the stack. Only one screen is visible at a time. Navigation is keyboard-driven; the `ESC` key always returns to the home screen from any screen.

---

## AppWindow

**Class:** `AppWindow` (`app/ui/window.py`)

| Property | Value |
|---|---|
| Base class | `QWidget` |
| Display mode | Full-screen (`showFullScreen()`) |
| Internal container | `QStackedWidget` |
| Signals | `key_event(int)`, `key_released(int)` |

### Registration

Screens are registered internally in `AppWindow._register_screens()` — no manual wiring in `main.py` is needed:

```python
# inside AppWindow._register_screens()
self._register_screen("home", HomeScreen(...))
self._register_screen("dashboard", DashboardScreen(...))
self._register_screen("ve_calibration", VeCalibrationScreen(...))
self.show_screen("home")
```

### Key event handling

`AppWindow` overrides `keyPressEvent` and `keyReleaseEvent` and forwards them directly to the currently active screen via `self._screens[self._current_screen_name].keyPressEvent(event)`. Individual screens handle their own keys.

**Intent:** each screen encapsulates its own key handling, keeping `AppWindow` as a thin router. `ESC` and home navigation are handled inside each screen's `keyPressEvent` by calling `self._close_fn()`, which is wired to `app_window.show_screen("home")` at registration time.

### Screen transitions

`show_screen(name)` follows this sequence:
1. Call `on_deactivated()` on the currently visible screen (if any).
2. Switch `QStackedWidget` to the new screen.
3. Store the new screen name as current.
4. Call `on_activated()` on the new screen.

`go_home()` is equivalent to `show_screen("home")`.

---

## Screen base class

**Class:** `Screen` (`app/ui/base/screen.py`)

All application screens inherit from `Screen`. Subclasses may override the lifecycle methods:

| Method | Called when |
|---|---|
| `on_activated()` | Screen becomes visible (after `QStackedWidget` switches to it) |
| `on_deactivated()` | Screen is about to be hidden |

Default implementations are no-ops.

**Intent:** lifecycle callbacks allow screens to start/stop timers, subscribe/unsubscribe from signals, or reset state when shown or hidden — without the `AppWindow` needing to know about screen internals.

---

## HomeScreen

**Class:** `HomeScreen` (`app/ui/home/screen.py`)

| Property | Value |
|---|---|
| Background | Black (`#000000`) |
| Title | `"Master Injection"`, Arial 48 Bold, white, top-centered |
| Menu | Vertical list of items, vertically centered |
| Navigation hint | `"↑↓ Navegar  Enter Selecionar"`, gray, bottom |

### Menu items

| Label | `screen_requested` payload |
|---|---|
| `"Dashboard"` | `"dashboard"` |
| `"Calibração de VE"` | `"ve_calibration"` |

### Navigation

| Key | Effect |
|---|---|
| `↑` | Move selection up (wraps to last item) |
| `↓` | Move selection down (wraps to first item) |
| `Enter` | Emit `screen_requested(name)` for the selected item |

Auto-repeat key events are ignored (only fresh presses after a release change selection).

### Signals

| Signal | Type | When emitted |
|---|---|---|
| `screen_requested` | `str` | User presses Enter on a menu item |

Wiring in `main.py`:
```python
home_screen.screen_requested.connect(app_window.show_screen)
```

### Selected item style

| State | Text color | Border |
|---|---|---|
| Selected | White (`#FFFFFF`) | 1 px solid `#1E90FF` + translucent blue background |
| Unselected | Gray (`#888888`) | None |

---

## Adding a new screen

1. Create a `Screen` subclass in an appropriate module.
2. Register it with `app_window.register_screen("name", screen_instance)` in `main.py`.
3. Add a menu item row to HomeScreen's menu table above.
4. Add the `"name"` string to the HomeScreen item table.
5. Wire any inbound signals (e.g., `signal_processor.emitter`) in `main.py`.
6. Wire any key event handlers via `app_window.key_event.connect(...)`.
