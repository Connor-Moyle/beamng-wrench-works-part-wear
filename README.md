# Wrench Works: Part Wear

Parts of your car wear out as you drive, and a worn part changes how the car drives. For BeamNG.drive 0.40.

**Everything is off by default.** Install the mod and nothing changes until you switch it on: ESC > Mods > Part wear > "Part wear" (or pick the Light or Realistic preset on the same page).

## What it does

Every part has a condition from 100 % (new) down to 0 %. Conditions go down with distance, hard braking, hard landings after jumps, brakes and engine running hot, and time. A worn part has an effect:

- **Shock absorbers**: less damping, so the car floats and bounces more.
- **Springs**: the corner sinks a little and the spring gets slightly softer.
- **Brake pads and discs**: pads lose bite; discs fade earlier when hot; pads worn to the metal grind.
- **Engine**: less power, rougher running; **clutch**: slips when worn.
- **Breakdowns** (the "Parts can break" setting): a badly worn part can fail, with a message on screen: a blown shock absorber, soft brakes, a slipping clutch.
- **Looks** (the "Worn look" setting): brake discs and calipers rust, the suspension, frame and exhaust metal get grime and rust, and the paint fades and rusts (paint needs Car Surface FX). The look of the discs and the metal is set when the car is spawned, so it changes at the next spawn or garage visit.
- **Repairs**: in the Wrench Works garage, worn parts are listed under Services with their condition and a price. Pay, and the part is new again.

Wear is kept for each car, and separately for each career save, so careers never share wear. Nothing wears on traffic cars.

## Settings (ESC > Mods > Part wear)

Presets: **Off**, **Light** (slow wear, small effects, no breakdowns) and **Realistic** (the full effects). The page also has sliders for the wear speed, how much rough driving and age count, the strength of each effect, the breakdown chance and the strength of the worn look.

## Requirements

- BeamNG.drive 0.40.
- Wrench Works 1.8.3 or newer: it provides the Mods page and the garage repairs. Without it the rules still run, but there is no settings page and no repair entries.
- Car Surface FX 0.4 or newer, only for the worn paint look.

## What has been tested in the game

Seen working in the game (Covet, Vivace, pickup): the worn metal look on the floor pan, arms, axles and fuel tank; the rust on brake discs at spawn; the detection of springs and dampers on the Vivace; the shortening of the spring beams; worn pads (longer stops) and worn shock absorbers (more bounce); the loss of power of a worn engine; the dirty look of the engine bay; wear kept when you swap a part; the repairs in the Wrench Works garage. The garage's power curve does not show a worn engine's lost power; the car's acceleration does. Built and tested only offline so far (the unit tests in `tools/`): the effect of a worn clutch, failures, the paint look, and the rust on brake calipers and hubs. The full list is in `CHANGELOG.md`; tell us if one of them does not work for you.

## For testers and modders

The testing steps for the apply layer are in `docs/PROBE_STEPS.md`; the design is in `docs/DESIGN.md`; texture credits are in `docs/TEXTURE_CREDITS.md`. The rules are in `mod/lua/common/slrrWearRules.lua` (pure, no game calls). The unit tests run with `python tools/test_wear_*.py` (they need `lupa`) and `node tools/globalcheck.js` (needs `luaparse`).

## Credits

Rust textures are made from CC0 photographs by ambientCG (https://ambientcg.com); see `docs/TEXTURE_CREDITS.md`. By Connor Moyle.
