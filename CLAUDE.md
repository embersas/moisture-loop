# CLAUDE.md

This file provides repository guidance to Claude Code and other coding agents.

## Project state

Moisture Loop v0.1 is implemented under `custom_components/moisture_loop/`.
`SPECIFICATION.md` version `0.1.0-spec.4` is the authoritative behavioural and
safety contract. Preserve the Stage 7 traceability evidence: 134 normative
behavioural IDs, invariants I1-I37, and transitions T1-T59.

Home Assistant 2025.9.0 or later is supported. The mandatory minimum and the
separately pinned supported-current environment must both remain green. See
`DEVELOPMENT.md` for exact environment, test, coverage, contract, traceability,
lint, hassfest, and HACS commands.

## Architecture boundaries

- One config entry owns native zone subentries; each zone pairs one moisture
  sensor with one `switch` or `valve` actuator.
- `state_machine.py` and the pure model layer must not import Home Assistant.
- Configuration reconciliation owns add/reconfigure/delete runtime safety.
  Native deletion takes effect immediately and may retain Store tombstones.
- Every commanded ON remains subject to the final live authorization fence.
- Runtime safety uses schema 2. Schema 1 exists only as verified migration
  input and is not current runtime authority.
- The integration is local-only and must not depend on Recorder, cloud
  services, telemetry, API keys, outbound HTTP, or direct `.storage` file
  manipulation.
- Manual watering is bounded. Shutdown, restart, deletion, and configuration
  change never resume an interrupted WATERING pulse.

## Working conventions

- Do not change behaviour without reconciling it with `SPECIFICATION.md`.
- Preserve fail-closed semantics, global serialization, conservative runtime
  accounting, and actuator-hazard identity across lifecycle changes.
- Keep the mandatory HA 2025.9.0 and supported-current jobs separate.
- Do not treat mocked tests or CI as completion of the seven §46 prototype
  validations; those remain Slice 13 work until explicitly authorized.
- Do not publish releases, submit to HACS or `home-assistant/brands`, or alter
  external repository hosting without explicit authorization.
