## ADDED Requirements

### Requirement: Visual alarm flash
When the alarm onset notification is emitted for a signal that has a card in the Dashboard grid, that card SHALL flash for as long as the alarm is firing: starting immediately and repeating every 200 ms, its background alternates between black and yellow while its value text is red. When the alarm stops firing the card background SHALL return to black and the value color SHALL follow the out-of-limit color rule. Signals without a card produce no visual effect.

#### Scenario: Flash starts
- **WHEN** the RPM alarm starts firing and RPM is in the grid
- **THEN** the RPM card background alternates black and yellow every 200 ms

#### Scenario: Flash ends
- **WHEN** the RPM alarm stops firing
- **THEN** the card background returns to black

#### Scenario: Signal not in grid
- **WHEN** an alarm starts for a signal that has no card
- **THEN** nothing flashes
