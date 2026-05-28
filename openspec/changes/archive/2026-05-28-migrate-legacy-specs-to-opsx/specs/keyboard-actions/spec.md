## ADDED Requirements

### Requirement: Event marker fires on Enter/Return key press
The system SHALL play `alarm.wav` (one-shot from the start) and publish `EventMarkRequestedEvent` to the event bus whenever `Qt.Key.Key_Return` or `Qt.Key.Key_Enter` is pressed. This is a global action active on every screen. `LogWriter` is subscribed to `EVENT_MARK_REQUESTED` and MUST mark the next CSV row.

#### Scenario: Event marker triggers on Return key
- **WHEN** the Return key is pressed on any screen
- **THEN** `alarm.wav` SHALL play and `EventMarkRequestedEvent` SHALL be published

### Requirement: Lambda loop toggles after Space is held for 2 seconds
The system SHALL toggle the lambda loop state when the Space key is held continuously for 2000 ms. `KeyHoldDetector` manages the timer. On trigger, `LambdaToggle` reads `vehicle_state.is_lambda_loop_closed()` and publishes `EcuCommandRequestedEvent(LAMBDA_LOOP_OPEN)` if closed, or `EcuCommandRequestedEvent(LAMBDA_LOOP_CLOSE)` if open. `ve_sound` is played (one-shot).

#### Scenario: Lambda loop opens when it was closed
- **WHEN** Space is held for 2 s and the lambda loop is currently Closed
- **THEN** `EcuCommandRequestedEvent(LAMBDA_LOOP_OPEN)` SHALL be published

#### Scenario: Lambda loop closes when it was open
- **WHEN** Space is held for 2 s and the lambda loop is currently Open
- **THEN** `EcuCommandRequestedEvent(LAMBDA_LOOP_CLOSE)` SHALL be published

### Requirement: Hold detector fires exactly once and ignores OS auto-repeat
`KeyHoldDetector` MUST start its timer on the first key press. The timer MUST be cancelled on key release. OS-generated auto-repeat events (while a key is held) MUST NOT restart the timer. The `triggered` signal MUST be emitted exactly once per successful hold.

#### Scenario: Auto-repeat does not restart hold timer
- **WHEN** a key is held and the OS generates auto-repeat events
- **THEN** the hold timer SHALL NOT reset and SHALL fire after the original start time + hold_ms

#### Scenario: Hold timer is cancelled on release
- **WHEN** the key is released before hold_ms elapses
- **THEN** no `triggered` signal SHALL be emitted

### Requirement: ESC returns to home screen from any screen
Pressing `ESC` on any screen MUST navigate to the HomeScreen.

#### Scenario: ESC navigates home
- **WHEN** ESC is pressed on the Dashboard screen
- **THEN** the HomeScreen SHALL become active

### Requirement: HomeScreen navigation uses arrow keys and Enter
While HomeScreen is active: `↑` MUST move selection up (wrapping to the last item); `↓` MUST move selection down (wrapping to the first item); `Enter` MUST publish `ScreenRequestedEvent` for the selected screen.

#### Scenario: Down arrow wraps from last to first item
- **WHEN** the last menu item is selected and `↓` is pressed
- **THEN** the first menu item SHALL become selected

#### Scenario: Enter opens the selected screen
- **WHEN** an item is selected and Enter is pressed
- **THEN** `ScreenRequestedEvent(screen_name)` SHALL be published on the bus

### Requirement: VE Calibration screen handles its own keyboard actions
While VE Calibration is active:
- `↑` MUST call `ve_map_state.adjust_ve(rpm, map, +6.0)` and trigger write debounce, play `ve_sound`
- `↓` MUST call `ve_map_state.adjust_ve(rpm, map, −6.0)` and trigger write debounce, play `ve_sound`
- `R` MUST call `ve_map_state.reset()` and trigger write debounce, play `ve_sound`
- `O` MUST send `LAMBDA_LOOP_OPEN` to the ECU, play `open_sound`
- `P` MUST send `LAMBDA_LOOP_CLOSE` to the ECU, play `closed_sound`

#### Scenario: Up arrow increases VE at current operating point
- **WHEN** the VE Calibration screen is active and `↑` is pressed
- **THEN** `adjust_ve(rpm, map, +6.0)` SHALL be called and the debounce timer SHALL be started

#### Scenario: R resets all VE cells
- **WHEN** R is pressed on the VE Calibration screen
- **THEN** all VE cells SHALL be restored to their original values and the write debounce SHALL be triggered
