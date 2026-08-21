# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This is a greenfield project with **no code yet**. It contains:

- `initial_prompt.md` — the original brief defining requirements, decision-making rules (its §56), and quality bar (its §58).
- `SPECIFICATION.md` — the completed v0.1 technical specification (47 sections + decisions summary + readiness verdict). **This is the source of truth for implementation.** Verdict: READY WITH PROTOTYPE VALIDATIONS (see its §46 for the validation items).

The project follows a strict two-phase workflow:

1. **Specification phase (done):** `SPECIFICATION.md` was produced per the brief. Changes to behaviour must be made in the spec first.
2. **Implementation phase (next, only when the user asks):** Build the integration exactly as specified — provisional name "Moisture Loop", domain `moisture_loop`, one config entry with one subentry per zone, HA ≥ 2025.7, pure `state_machine.py` core with no `homeassistant` imports.

## What is being built

A hardware-agnostic Home Assistant custom integration for **closed-loop soil-moisture irrigation**: each zone pairs a soil-moisture sensor with an irrigation actuator (`switch`/`valve`), and the integration waters in bounded pulses with soak/recheck loops until a target moisture is reached or a safety limit trips. Distribution is expected via HACS.

## Non-negotiable design principles

These come from `initial_prompt.md` and govern every design and implementation decision:

- **Soil moisture is the authoritative feedback signal.** This is not an evapotranspiration/weather model, and moisture is not merely a veto on a timer.
- **Pulse → soak → recheck.** Never "water until sensor reaches target" — water moves through soil with significant delay.
- **Conservative failure behaviour.** When uncertain, stop or refuse to start. Sensor unavailability, HA restarts, or crashes must never result in uncontrolled watering. Never automatically resume an interrupted watering pulse after restart.
- **Hysteresis:** a new automatic session requires `moisture < start_threshold`; an in-progress session continues while `moisture < target_threshold`. These are deliberately different.
- **Hardware-agnostic:** no Ecowitt/Holman/vendor-specific logic; use HA entity abstractions only.
- **Deterministic:** same inputs + persisted state → same transition. Every edge case has an explicitly defined outcome.
- **Configuration over hard-coded agronomy:** thresholds are user-configurable; never claim universal moisture percentages for crops/soils.
- **Local-only:** no cloud account, external network service, telemetry, or API key.
- **Manual watering must have a mandatory maximum duration** — no indefinite ON command through the integration.

The overriding objective (section 58): *"A predictable irrigation controller that cannot accidentally keep watering merely because a sensor, timer, integration or Home Assistant state behaves unexpectedly."*

## Working conventions

- Research **current** official Home Assistant developer documentation before making architecture claims — do not rely on outdated integration patterns. Cite current docs for API-dependent decisions.
- Make decisions rather than presenting options. For significant choices: identify alternatives, weigh trade-offs, choose one, justify it. Genuinely undecidable items get labelled `VALIDATE DURING PROTOTYPE` with exact test criteria.
- v0.1 scope is tightly bounded — weather, ET, flow meters, ML/adaptive watering, multi-sensor zones, and scheduling calendars are explicitly deferred (section 6 of the brief has the full non-goals list).
- The deployment context is Brisbane, Australia, but all time handling must use HA's configured local timezone — no hard-coded timezone assumptions.

## Commands

None yet — no build, lint, or test tooling exists. When implementation begins, it will follow Home Assistant's current custom-integration conventions (`custom_components/<domain>/`, pytest with HA's recommended testing stack, mocked time for timer tests).
