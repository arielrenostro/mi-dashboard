## MODIFIED Requirements

### Requirement: Full-screen multi-screen window
The app SHALL show a single full-screen window containing exactly one visible screen at a time. The available screens are `home`, `dashboard`, `ve_calibration` and `ignition_tuning`, and the app SHALL start on `home`.

#### Scenario: Startup
- **WHEN** the app starts
- **THEN** the window is full-screen and shows the Home screen

### Requirement: Return to Home with ESC
On the Dashboard, the VE calibration screen and the Ignition tuning screen, ESC SHALL show the Home screen.

#### Scenario: Back from calibration
- **WHEN** the user presses ESC on the VE calibration screen
- **THEN** the Home screen is shown

#### Scenario: Back from ignition tuning
- **WHEN** the user presses ESC on the Ignition tuning screen
- **THEN** the Home screen is shown

### Requirement: Home screen content
The Home screen SHALL have a black background, the centered title `Master Injection` in large bold white text, a connection line, a vertical menu and the hint `↑↓ Navegar | Enter Selecionar` in gray at the bottom. The menu SHALL contain `Dashboard` (opens `dashboard`), `Calibração de VE` (opens `ve_calibration`) and `Ajuste de Ignição` (opens `ignition_tuning`), in that order.

#### Scenario: Initial selection
- **WHEN** Home is first shown
- **THEN** `Dashboard` is selected

#### Scenario: Ignition tuning entry
- **WHEN** `Ajuste de Ignição` is selected and the user presses Enter
- **THEN** the Ignition tuning screen is shown
