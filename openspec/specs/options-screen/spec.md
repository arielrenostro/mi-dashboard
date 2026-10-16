# options-screen Specification

## Purpose
Defines the Options screen, a keyboard-driven list of ECU settings that can be changed from the driver's seat. For now it has a single field, the engine phase (Negativa or Positiva), whose change is sent to the ECU as described in `phase-write`.

## Requirements

### Requirement: Options screen layout
The Options screen (name `options`, shown to the user as `ECU`) SHALL have a black background, the title `ECU` in large bold white text, a vertical list of fields and the hint `↑↓ Navegar | Enter Alterar | Esc Voltar` in gray at the bottom. Each field SHALL be one row with its label on the left and its current value on the right. The list SHALL contain, for now, only the field `Fase`. The selected field SHALL be drawn with white text, a blue border and a translucent blue background, like the selected Home menu item. Below the list a status line SHALL show the latest status message (empty when there is none).

#### Scenario: Initial content
- **WHEN** the Options screen is shown for the first time
- **THEN** it shows the title `ECU`, the field `Fase` selected, the hint and an empty status line

### Requirement: Phase display
The `Fase` field SHALL show `Negativa` when the latest `#X02` block known to the app has phase value 0, `Positiva` when it has phase value 1, and `—` when no `#X02` block is known yet or the phase value is neither 0 nor 1. While a phase change is waiting to be sent or confirmed, the field SHALL show the requested phase instead, followed by ` …`. The field SHALL follow the shared state: when a new `#X02` block is published and no change is in progress, the displayed value SHALL update without any key press.

#### Scenario: Negative phase
- **WHEN** an `#X02` block with phase value 0 is published
- **THEN** the field reads `Negativa`

#### Scenario: Positive phase
- **WHEN** an `#X02` block with phase value 1 is published
- **THEN** the field reads `Positiva`

#### Scenario: Unknown phase
- **WHEN** no `#X02` block has been published
- **THEN** the field reads `—`

#### Scenario: Unexpected phase value
- **WHEN** an `#X02` block with phase value 2 is published
- **THEN** the field reads `—`

#### Scenario: Change in progress
- **WHEN** the phase is `Negativa` and the user presses Enter on the field
- **THEN** the field reads `Positiva …` until the change is confirmed or fails

### Requirement: Phase toggle
Pressing Enter or Return on the selected `Fase` field SHALL switch the requested phase to the opposite of the one currently displayed, and SHALL start (or restart) the phase write described in `phase-write`. When the displayed phase is `—` (unknown) Enter SHALL do nothing. Auto-repeat events SHALL be ignored, so holding the key toggles once. Enter on the Options screen SHALL NOT play the event-mark sound and SHALL NOT request a `MARK` in the data log.

#### Scenario: Toggle to positive
- **WHEN** the phase is `Negativa` and the user presses Enter
- **THEN** the field shows `Positiva …` and a phase write is scheduled

#### Scenario: Toggle twice
- **WHEN** the user presses Enter twice, each press separated by a new key event
- **THEN** the requested phase is back to the original one

#### Scenario: Unknown phase
- **WHEN** the phase is `—` and the user presses Enter
- **THEN** nothing changes and no write is scheduled

#### Scenario: Held key
- **WHEN** the user holds Enter
- **THEN** the phase is toggled only once

#### Scenario: No event mark
- **WHEN** the user presses Enter on the Options screen
- **THEN** the key is not announced to the event marker

### Requirement: Field navigation
↑ SHALL select the previous field and ↓ the next, wrapping around at both ends. With a single field the selection SHALL stay on it. Auto-repeat events SHALL be ignored.

#### Scenario: Single field
- **WHEN** the user presses ↓ on the Options screen
- **THEN** `Fase` remains selected

### Requirement: Status messages
The status line SHALL reflect the phase write, using exactly these texts:

| Situation | Text |
|---|---|
| Change waiting for the 1 s delay | `Alteração pendente…` |
| Reading or writing `#X02` | `Enviando para a ECU…` |
| ECU holds the requested phase | `Fase aplicada (não gravada na memória)` |
| ECU holds a different phase after the write | `A ECU manteve a fase <Negativa ou Positiva>` |
| No answer to a request | `Sem resposta da ECU` |
| Answer that is not a valid `#X02` block | `Resposta #X02 inválida` |

A failure message SHALL stay until the next toggle; the success message SHALL stay until the next toggle or until the screen is left.

#### Scenario: Success message
- **WHEN** the ECU confirms the requested phase
- **THEN** the status line reads `Fase aplicada (não gravada na memória)`

#### Scenario: Failure message kept
- **WHEN** a request times out
- **THEN** the status line reads `Sem resposta da ECU` until the user toggles again

### Requirement: Refresh on activation
When the Options screen becomes active the app SHALL request `#X02` from the ECU so the field shows the phase the ECU holds now, unless a phase change is in progress. The request SHALL NOT write anything.

#### Scenario: Open the screen
- **WHEN** the Options screen becomes active and no change is in progress
- **THEN** the `#X02` request is queued without arguments

#### Scenario: Open during a change
- **WHEN** the Options screen becomes active while a phase change is in progress
- **THEN** no extra request is queued

### Requirement: Leaving the screen
ESC SHALL show the Home screen. Leaving the Options screen SHALL NOT cancel a phase change that is waiting or in progress; it continues in the background and its result is visible next time the screen is shown.

#### Scenario: Back to Home
- **WHEN** the user presses ESC on the Options screen
- **THEN** the Home screen is shown

#### Scenario: Leave during the delay
- **WHEN** the user toggles the phase and leaves the screen before 1 s passes
- **THEN** the phase write still happens
