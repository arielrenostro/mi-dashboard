## ADDED Requirements

### Requirement: AppWindow hosts all screens in a QStackedWidget
`AppWindow` SHALL be a full-screen `QWidget` (`showFullScreen()`) containing a `QStackedWidget`. Only one screen is visible at a time. `AppWindow` MUST subscribe to `SCREEN_REQUESTED` on the event bus and call `show_screen(e.screen_name)` on receipt. `AppWindow` MUST emit `key_event(int)` and `key_released(int)` pyqtSignals forwarded from `keyPressEvent` / `keyReleaseEvent`.

#### Scenario: Screen changes on bus event
- **WHEN** a `ScreenRequestedEvent(screen_name="dashboard")` is published
- **THEN** the dashboard screen SHALL become visible

#### Scenario: Key events are forwarded to global handlers
- **WHEN** a key is pressed
- **THEN** `AppWindow.key_event(int)` SHALL be emitted so global keyboard handlers can observe it

### Requirement: Screen transitions call lifecycle callbacks
`show_screen(name)` MUST follow this sequence:
1. Call `on_deactivated()` on the currently visible screen (if any)
2. Switch `QStackedWidget` to the new screen
3. Store the new screen name as current
4. Call `on_activated()` on the new screen

#### Scenario: Deactivated is called before transition
- **WHEN** switching from Dashboard to HomeScreen
- **THEN** `DashboardScreen.on_deactivated()` SHALL be called before `HomeScreen.on_activated()`

### Requirement: Screen base class manages bus subscriptions automatically
The `Screen` base class MUST provide `_subscribe(event_type, callback)` which tracks the subscription token internally. `on_deactivated()` in the base class MUST unsubscribe all tracked tokens. Screens MUST subscribe to bus events in `on_activated()` and MUST call `super().on_deactivated()` if they override `on_deactivated()`.

#### Scenario: Subscriptions are cleaned up on deactivation
- **WHEN** a screen is deactivated
- **THEN** all bus subscriptions made via `_subscribe()` SHALL be unsubscribed automatically

#### Scenario: Hidden screen does not receive bus events
- **WHEN** a screen is hidden and a relevant bus event is published
- **THEN** the hidden screen's callback SHALL NOT be invoked

### Requirement: HomeScreen displays a navigable menu
`HomeScreen` SHALL display:
- Black background (`#000000`)
- Title `"Master Injection"`, Arial 48 Bold, white, top-centered
- Vertical menu with two items: `"Dashboard"` → `"dashboard"` and `"Calibração de VE"` → `"ve_calibration"`
- Navigation hint at the bottom: `"↑↓ Navegar  Enter Selecionar"`, gray

Selected item style: white text (`#FFFFFF`), 1 px `#1E90FF` border, translucent blue background.
Unselected item style: gray text (`#888888`), no border.

Auto-repeat key events MUST be ignored — only fresh presses after a release change selection.

#### Scenario: Selected item is visually distinguished
- **WHEN** the first menu item is selected
- **THEN** it SHALL have a blue border and white text; all other items SHALL be gray with no border

#### Scenario: Auto-repeat is ignored for navigation
- **WHEN** the ↓ key is held and OS generates auto-repeat events
- **THEN** the selection SHALL NOT change more than once per actual key press cycle

### Requirement: Screens are registered inside AppWindow
All screens MUST be instantiated and registered inside `AppWindow._register_screens()` using `self._register_screen("name", screen_instance)`. No screen registration MUST be required in `main.py`.

#### Scenario: New screen is accessible via bus event
- **WHEN** a screen is registered with name `"ve_calibration"`
- **THEN** publishing `ScreenRequestedEvent("ve_calibration")` SHALL show that screen
