## RENAMED Requirements

- FROM: `### Requirement: Out-of-limit color for non-alarm signals`
- TO: `### Requirement: Out-of-limit color`

## MODIFIED Requirements

### Requirement: Out-of-limit color
For every signal in the grid whose catalog entry has limits, the card value SHALL be shown in red while the value is strictly outside those limits, whether or not its alarm is enabled, and in the signal's color otherwise. While an alarm flash is running for a card, the flash controls that card's colors.

#### Scenario: Boost above its limit
- **WHEN** BOOST is `200` (limit 165, alarm disabled)
- **THEN** the BOOST card value is red

#### Scenario: Alarm-enabled signal above its limit
- **WHEN** RPM is `6700` (limit 6600, alarm enabled)
- **THEN** the RPM card value is red

#### Scenario: Back within limits
- **WHEN** BOOST returns to `150`
- **THEN** the card value returns to the BOOST color
