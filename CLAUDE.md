# CLAUDE.md

This file provides repository guidance to Claude Code and other coding agents.

## Project state

MoistureLoop v0.1 is implemented under `custom_components/moisture_loop/`.
`SPECIFICATION.md` version `0.1.0-spec.8` is the authoritative behavioural and
safety contract. Preserve the Stage 7 traceability evidence: 142 normative
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
- Runtime safety uses schema 3. Schemas 1 and 2 exist only as verified
  migration input and are not current runtime authority.
- A retained record whose durable actuator registry row is definitively ABSENT
  may be released only by the §26.4 operator certification, which is durable,
  bound to that exact registry ID, and never inferred. Unavailable, unknown,
  or conflicting identities keep failing closed.
- The integration is local-only and must not depend on Recorder, cloud
  services, telemetry, API keys, outbound HTTP, or direct `.storage` file
  manipulation.
- Manual watering is bounded. Shutdown, restart, deletion, and configuration
  change never resume an interrupted WATERING pulse.
- A genuinely new zone is created `enabled=false` in DISABLED by the entry
  reconciler (`runtime.py` `_new_zone_history`) and admits no watering until an
  explicit user enable. Every existing zone keeps its persisted `enabled`.

## Working conventions

- Do not change behaviour without reconciling it with `SPECIFICATION.md`.
- Preserve fail-closed semantics, global serialization, conservative runtime
  accounting, and actuator-hazard identity across lifecycle changes.
- Keep the mandatory HA 2025.9.0 and supported-current jobs separate.
- Do not treat mocked tests or CI as completion of the seven §46 prototype
  validations; those remain Slice 13 work until explicitly authorized.
- Do not publish releases, submit to HACS or `home-assistant/brands`, or alter
  external repository hosting without explicit authorization.
