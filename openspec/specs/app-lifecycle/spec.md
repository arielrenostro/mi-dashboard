# app-lifecycle Specification

## Purpose

Defines how the app shuts down when the user closes it: the order in which its parts stop, bounded waiting for background threads, and the guarantee that exiting neither crashes nor hangs.

## Requirements

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

### Requirement: Bounded waiting
Waiting for a background thread to finish SHALL be bounded: 3 seconds for the ECU source, 1 second for the alarm and 3 seconds for the datalog. When a thread does not finish in time, the app SHALL log a warning and continue shutting down without crashing or hanging.

#### Scenario: Thread does not finish
- **WHEN** the ECU source thread does not finish within its limit
- **THEN** a warning is logged and the remaining components are still stopped

### Requirement: Failure isolation
A failure while stopping one component SHALL be logged and SHALL NOT prevent the remaining components from being stopped.

#### Scenario: Alarm fails to stop
- **WHEN** stopping the alarm raises an error
- **THEN** the error is logged and the datalog is still closed
