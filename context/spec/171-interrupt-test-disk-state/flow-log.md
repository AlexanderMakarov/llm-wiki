# Flow log — #171 interrupt test disk/state correspondence

## fix

- **Stage:** fix + verify
- **Branch:** `fix/171-interrupt-test-correspondence`
- **Verdict:** conformance bug (test asserted wrong invariant; pipeline behaviour unchanged)
- **Change:** `tests/test_synth_parallel.py` — `test_an_interrupt_records_the_pages_that_reached_disk` asserts disk/state correspondence (with vacuous guard) instead of a fixed page count; resume checks no double-synth for pages that landed before interrupt.
- **Evidence:** 50/50 consecutive runs of the targeted test; full `pytest tests/ -q` green.
- **PR keyword:** `Closes #171`
- **Next:** commit-push → remote gates → merge → pull `$MAIN`
