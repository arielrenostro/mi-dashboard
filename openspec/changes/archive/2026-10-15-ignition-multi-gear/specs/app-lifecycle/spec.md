## MODIFIED Requirements

### Requirement: Orderly shutdown
When the event loop ends, the app SHALL shut down in this order: close the window, which first writes the pending ignition results (see ignition-results-log); stop the ECU source, so no new data arrives; stop the alarm; and finally close the datalog, so that every frame received before the ECU source stopped is written. Every background thread SHALL have finished before the process exits, and the process SHALL end with exit status 0 and without Qt error messages.

#### Scenario: Normal exit
- **WHEN** the user closes the app
- **THEN** the window, the ECU source, the alarm and the datalog are stopped in that order and the process ends with exit status 0

#### Scenario: Last frames are kept
- **WHEN** frames arrive immediately before the user closes the app
- **THEN** those frames are present in the CSV log

#### Scenario: Ignition results are kept
- **WHEN** ignition scenarios changed since the last results snapshot and the user closes the app
- **THEN** the results file holds those scenarios when the window has closed
