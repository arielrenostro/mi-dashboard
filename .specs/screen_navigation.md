# Spec: Screen Navigation

Describes the multi-screen architecture: the main window, the screen base class, the home screen, and navigation rules.

Implementation: `app/ui/window.py`, `app/ui/base/screen.py`, `app/ui/home/screen.py`. Screens are self-registered inside `AppWindow._register_screens()` — no explicit wiring in `main.py` is required for screen management.

---

## Overview

The application uses a single full-screen `AppWindow` that contains a `QStackedWidget`. Each functional area (Dashboard, VE Calibration, etc.) is a `Screen` — a `QWidget` subclass — registered in the stack. Only one screen is visible at a time. Navigation is keyboard-driven; the `ESC` key returns to the home screen from any screen.

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

Screens are registered internally in `AppWindow._register_screens()`:

```python
home_screen = HomeScreen(close_fn=lambda: self.close())
ve_calibration_screen = VeCalibrationScreen(close_fn=lambda: self.show_screen("home"))
dashboard_screen = DashboardScreen(close_fn=lambda: self.show_screen("home"), ...)

self._register_screen("home", home_screen)
self._register_screen("dashboard", dashboard_screen)
self._register_screen("ve_calibration", ve_calibration_screen)
```

`AppWindow.__init__` subscribes to `SCREEN_REQUESTED` on the event bus:

```python
event_bus.subscribe(AppEventType.SCREEN_REQUESTED,
                    lambda e: self.show_screen(e.screen_name))
```

### Key event handling

`AppWindow` overrides `keyPressEvent` and `keyReleaseEvent`. It forwards events to the currently active screen and emits `key_event(int)` / `key_released(int)` pyqtSignals for global keyboard handlers (`EventMarker`, `KeyHoldDetector`) wired in `main.py`.

**Intent:** each screen encapsulates its own key handling. `ESC` and home navigation are handled inside each screen's `keyPressEvent` by calling `self.close_fn()`, which is wired to `show_screen("home")` at registration time.

### Screen transitions

`show_screen(name)` follows this sequence:
1. Call `on_deactivated()` on the currently visible screen (if any).
2. Switch `QStackedWidget` to the new screen.
3. Store the new screen name as current.
4. Call `on_activated()` on the new screen.

---

## Screen base class

**Class:** `Screen` (`app/ui/base/screen.py`)

All application screens inherit from `Screen`. Provides bus subscription management:

| Method | Description |
|---|---|
| `_subscribe(event_type, callback)` | Subscribe to the bus and track the token internally |
| `on_activated()` | Called when screen becomes visible. Screens subscribe to bus events here. |
| `on_deactivated()` | Called when screen is hidden. Base implementation auto-unsubscribes all tracked tokens. Subclasses that override must call `super().on_deactivated()`. |

**Intent:** `_subscribe` + `on_deactivated()` ensure that a hidden screen never receives bus events and never leaks callback references.

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

| Label | Screen name published |
|---|---|
| `"Dashboard"` | `"dashboard"` |
| `"Calibração de VE"` | `"ve_calibration"` |

### Navigation

| Key | Effect |
|---|---|
| `↑` | Move selection up (wraps to last item) |
| `↓` | Move selection down (wraps to first item) |
| `Enter` | Publish `ScreenRequestedEvent(screen_name)` to the event bus |

Auto-repeat key events are ignored (only fresh presses after a release change selection).

### Navigation flow

`HomeScreen` publishes a `ScreenRequestedEvent` to the bus; `AppWindow` is subscribed and calls `show_screen(name)`. No direct coupling between `HomeScreen` and `AppWindow`.

### Selected item style

| State | Text color | Border |
|---|---|---|
| Selected | White (`#FFFFFF`) | 1 px solid `#1E90FF` + translucent blue background |
| Unselected | Gray (`#888888`) | None |

---

## Adding a new screen

1. Create a `Screen` subclass in an appropriate module.
2. Register it in `AppWindow._register_screens()` with `self._register_screen("name", screen_instance)`.
3. Add a menu item to `HomeScreen._menu_items`.
4. Subscribe to any needed bus events in the screen's `on_activated()` using `self._subscribe(...)`.
5. Wire any keyboard handlers (global hold actions) in `main.py` via `app_window.key_event.connect(...)`.
