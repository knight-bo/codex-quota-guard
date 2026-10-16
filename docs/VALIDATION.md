# Validation

## Version 0.1.1 baseline

Run `python3 -m unittest discover -s tests -v` from the source root.
All 35 automated tests passed. Wheel build, isolated installation, and CLI
synthetic-replay smoke testing passed. Tests use synthetic data and fake child
processes; these are not authenticated integration tests.

Regression coverage includes concurrent checks during simulation, interrupted
simulation, missing provenance, multiple quota windows, missing/stale/invalid
readings, reset ordering, exact bucket selection, response-plus-notification in
one write, buffered-response deadlines, strict integer response IDs, blocked
stdin writes with an outer watchdog, partial frames, persistent at-most-one
interrupt attempts and unconfirmed checkpoint reporting.

Real authenticated quota reads and real managed-turn interruption are unverified.
No guarantee is made for controlling hosted cloud tasks or detached processes.
Checkpoint requests do not verify that application data was saved. This release
is experimental advisory software, not an atomic quota reservation service.


## Version 0.2.0 validation

The development validation run passed 48 offline unittest cases and compileall.
These results validate the exercised implementation and synthetic protocol paths,
not live account access. Actual plugin installation in the client UI, authenticated
quota reads, and managed-turn interruption have not been verified for this release.
Manifest JSON parsing is checked separately; it is not proof of client acceptance.

Version 0.2.0 also passed a no-dependency/no-build-isolation wheel build,
installation into a fresh isolated virtual environment, synthetic CLI replay,
and rejection of that replay by `check` (exit 2). The wheel contains the Python
CLI; plugin installation uses the complete repository package and manifests.

The 0.2.0 review regression covers a stop accepted during an in-flight read:
healthy, low-quota and transport-error outcomes all exit without a new interrupt
or healthy report; stopped state and subsequent cached checks deny admission.
