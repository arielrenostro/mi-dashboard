## MODIFIED Requirements

### Requirement: Full-screen multi-screen window
The app SHALL show a single full-screen window containing exactly one visible screen at a time. The available screens are `home`, `dashboard`, `ve_calibration`, `ignition_tuning`, `options` (shown to the user as `ECU`) and `settings` (shown as `Configurações`), and the app SHALL start on `home`.

#### Scenario: Startup
- **WHEN** the app starts
- **THEN** the window is full-screen and shows the Home screen

### Requirement: Return to Home with ESC
On the Dashboard, the VE calibration screen, the Ignition tuning screen, the ECU screen and the Settings screen, ESC SHALL show the Home screen.

#### Scenario: Back from calibration
- **WHEN** the user presses ESC on the VE calibration screen
- **THEN** the Home screen is shown

#### Scenario: Back from ignition tuning
- **WHEN** the user presses ESC on the Ignition tuning screen
- **THEN** the Home screen is shown

#### Scenario: Back from options
- **WHEN** the user presses ESC on the ECU screen
- **THEN** the Home screen is shown

#### Scenario: Back from settings
- **WHEN** the user presses ESC on the Settings screen
- **THEN** the Home screen is shown

### Requirement: Home screen content
The Home screen SHALL have a black background, the centered title `Master Injection` in large bold white text, a connection line, a vertical menu and the hint `↑↓ Navegar | Enter Selecionar` in gray at the bottom. The menu SHALL contain `Dashboard` (opens `dashboard`), `Calibração de VE` (opens `ve_calibration`), `Ajuste de Ignição` (opens `ignition_tuning`), `ECU` (opens `options`) and `Configurações` (opens `settings`), in that order.

#### Scenario: Initial selection
- **WHEN** Home is first shown
- **THEN** `Dashboard` is selected

#### Scenario: Ignition tuning entry
- **WHEN** `Ajuste de Ignição` is selected and the user presses Enter
- **THEN** the Ignition tuning screen is shown

#### Scenario: Options entry
- **WHEN** `ECU` is selected and the user presses Enter
- **THEN** the ECU screen is shown

#### Scenario: Settings entry
- **WHEN** `Configurações` is selected and the user presses Enter
- **THEN** the Settings screen is shown

#### Scenario: Menu content
- **WHEN** Home is shown
- **THEN** the menu lists `Dashboard`, `Calibração de VE`, `Ajuste de Ignição`, `ECU` and `Configurações`, and no item reads `Opções`

### Requirement: Global screen shortcuts
On every screen, including Home, the keys F1, F2, F3, F4 and F12 SHALL show the Dashboard, the VE calibration screen, the Ignition tuning screen, the ECU screen and the Settings screen respectively, following the normal screen switching lifecycle. Pressing the shortcut of the screen that is already visible SHALL do nothing (no lifecycle notifications). Auto-repeat events SHALL be ignored. The shortcut keys SHALL NOT be delivered to the screen and SHALL NOT be announced as key events to the data log marker. Key releases of the shortcut keys SHALL NOT be delivered to the screen either.

#### Scenario: F1 from Home
- **WHEN** the user presses F1 on the Home screen
- **THEN** the Dashboard is shown

#### Scenario: F2 from Dashboard
- **WHEN** the user presses F2 on the Dashboard
- **THEN** the VE calibration screen is shown

#### Scenario: F3 from Options
- **WHEN** the user presses F3 on the ECU screen
- **THEN** the Ignition tuning screen is shown

#### Scenario: F4 from VE calibration
- **WHEN** the user presses F4 on the VE calibration screen
- **THEN** the ECU screen is shown

#### Scenario: F12 from Home
- **WHEN** the user presses F12 on the Home screen
- **THEN** the Settings screen is shown

#### Scenario: F12 from the Ignition tuning screen
- **WHEN** the user presses F12 on the Ignition tuning screen
- **THEN** the Settings screen is shown

#### Scenario: F1 from Settings
- **WHEN** the user presses F1 on the Settings screen
- **THEN** the Dashboard is shown

#### Scenario: Shortcut of the visible screen
- **WHEN** the Dashboard is visible and the user presses F1
- **THEN** the Dashboard is not notified of being hidden or activated again

#### Scenario: Held shortcut
- **WHEN** the user holds F12
- **THEN** the Settings screen is shown once

#### Scenario: Shortcut not announced
- **WHEN** the user presses F1 on a data screen
- **THEN** no key event is announced for that press
