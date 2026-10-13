# screen-navigation Specification

## Purpose

Defines the full-screen application window, how screens are activated and receive keyboard input, and the Home screen with its menu and ECU connection status.

## Requirements

### Requirement: Full-screen multi-screen window
The app SHALL show a single full-screen window containing exactly one visible screen at a time. The available screens are `home`, `dashboard` and `ve_calibration`, and the app SHALL start on `home`.

#### Scenario: Startup
- **WHEN** the app starts
- **THEN** the window is full-screen and shows the Home screen

### Requirement: Screen switching lifecycle
Showing a screen by name SHALL first notify the currently visible screen that it is being hidden, then display the requested screen, then notify it that it is active. Requesting a name that is not registered SHALL be an error.

#### Scenario: Switch
- **WHEN** the user opens the Dashboard from Home
- **THEN** Home is notified it was hidden and the Dashboard is notified it is active

#### Scenario: Unknown screen
- **WHEN** a screen name that does not exist is requested
- **THEN** an error is raised and the visible screen does not change

### Requirement: Keyboard routing
Key press and key release events received by the window SHALL be delivered only to the currently visible screen, which alone decides how to react.

#### Scenario: Key on VE screen
- **WHEN** the user presses a key while the VE calibration screen is visible
- **THEN** only the VE calibration screen handles it

### Requirement: Return to Home with ESC
On the Dashboard and the VE calibration screen, ESC SHALL show the Home screen.

#### Scenario: Back from calibration
- **WHEN** the user presses ESC on the VE calibration screen
- **THEN** the Home screen is shown

### Requirement: Home screen content
The Home screen SHALL have a black background, the centered title `Master Injection` in large bold white text, a connection line, a vertical menu and the hint `↑↓ Navegar | Enter Selecionar` in gray at the bottom. The menu SHALL contain `Dashboard` (opens `dashboard`) and `Calibração de VE` (opens `ve_calibration`), in that order.

#### Scenario: Initial selection
- **WHEN** Home is first shown
- **THEN** `Dashboard` is selected

### Requirement: Menu navigation
On Home, ↑ SHALL move the selection to the previous item and ↓ to the next, wrapping around at both ends; Enter SHALL open the selected screen. Auto-repeat key events SHALL be ignored. The selected item SHALL be drawn with white text, a blue border and a translucent blue background; other items SHALL be gray with no visible border.

#### Scenario: Wrap down
- **WHEN** the last item is selected and the user presses ↓
- **THEN** the first item becomes selected

#### Scenario: Wrap up
- **WHEN** the first item is selected and the user presses ↑
- **THEN** the last item becomes selected

#### Scenario: Held key
- **WHEN** the user holds ↓
- **THEN** the selection moves only once

#### Scenario: Open
- **WHEN** `Calibração de VE` is selected and the user presses Enter (or Return)
- **THEN** the VE calibration screen is shown

### Requirement: Connection information and status
The Home screen SHALL show where the app is connected: `Port: <port> | Baudrate: <baudrate> | ` for the serial source, or `Mock: <path> | ` for the mock source (a path longer than 40 characters SHALL be shown as `...` plus its last 40 characters). Next to it, while Home is the active screen, a colored dot and a label SHALL show the connection status, refreshed every 500 ms:

| Status | Label | Dot |
|---|---|---|
| CONNECTED | `Connected` | green |
| CONNECTING | `Connecting` | yellow |
| HANDSHAKE | `Handshake` | yellow |
| ERROR | `Error` | red |
| DISCONNECTED | `Disconnected` | red |
| anything else | `Unknow` | gray |

#### Scenario: Serial link up
- **WHEN** the serial source reports CONNECTED
- **THEN** the label reads `Connected` with a green dot

#### Scenario: Refresh stops when hidden
- **WHEN** the user leaves Home
- **THEN** the status is no longer refreshed until Home is shown again

### Requirement: Exit with ESC on Home
On the Home screen, pressing ESC SHALL close the window and exit the app. Auto-repeat events SHALL be ignored.

#### Scenario: Exit from Home
- **WHEN** the user presses ESC on the Home screen
- **THEN** the app closes

#### Scenario: Held ESC after returning to Home
- **WHEN** the user holds ESC on the Dashboard until it returns to Home
- **THEN** the app does not exit until ESC is released and pressed again
