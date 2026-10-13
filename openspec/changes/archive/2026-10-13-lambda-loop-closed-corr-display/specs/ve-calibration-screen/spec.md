## MODIFIED Requirements

### Requirement: Top bar
The top bar SHALL show seven cards in order: RPM, MAP, VE, LAMBDA, LAMBDA_TARGET, FUEL_TRIM, LAMBDA_LOOP, each with the signal's display string. The LAMBDA_LOOP value SHALL be green when its raw value is `1` or `2` and orange otherwise.

#### Scenario: Open loop
- **WHEN** the lambda loop value is `0`
- **THEN** the LAMBDA_LOOP card is orange and reads `Open`

#### Scenario: Closed loop with correction
- **WHEN** the lambda loop value is `2`
- **THEN** the LAMBDA_LOOP card is green and reads `Closed+C`
