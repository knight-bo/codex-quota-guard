# Validation — 0.1.1

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
