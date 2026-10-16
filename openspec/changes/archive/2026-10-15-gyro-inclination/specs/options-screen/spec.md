## MODIFIED Requirements

### Requirement: Options screen layout
The Options screen (name `options`, shown to the user as `ECU`) SHALL have a black background, the title `ECU` in large bold white text, a vertical list of fields and the hint `↑↓ Navegar | Enter Alterar | Esc Voltar` in gray at the bottom. Each field SHALL be one row with its label on the left and its current value on the right. The list SHALL contain, for now, only the field `Fase`. The selected field SHALL be drawn with white text, a blue border and a translucent blue background, like the selected Home menu item. Below the list a status line SHALL show the latest status message (empty when there is none).

#### Scenario: Initial content
- **WHEN** the Options screen is shown for the first time
- **THEN** it shows the title `ECU`, the field `Fase` selected, the hint and an empty status line
