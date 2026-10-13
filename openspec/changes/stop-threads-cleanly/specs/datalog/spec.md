## ADDED Requirements

### Requirement: Clean shutdown of the log
When the app exits, the datalog SHALL write every row it has already received, close the file and finish its writer thread. Closing the datalog more than once SHALL be harmless.

#### Scenario: Rows pending at exit
- **WHEN** frames have been received but not yet written and the app exits
- **THEN** all of them are in the file after shutdown and the file is closed

#### Scenario: Closed twice
- **WHEN** the datalog is closed a second time
- **THEN** nothing happens and no error is raised
