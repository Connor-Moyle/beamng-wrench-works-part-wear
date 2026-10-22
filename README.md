# Wrench Works: Part Wear

Parts of your car wear out as you drive, and a worn part changes how the car drives. For BeamNG.drive 0.40.

**Everything is off by default.** Install the mod and nothing changes until you switch it on: ESC > Mods > Part wear > "Part wear" (or pick the Light or Realistic preset on the same page).

## What it does

Every part has a condition from 100 % (new) down to 0 %. Conditions go down with distance, hard braking, hard landings after jumps, brakes and engine running hot, and time. A worn part has an effect:

- **Shock absorbers**: less damping, so the car floats and bounces more.
- **Springs**: the corner sinks a little and the spring gets slightly softer.
- **Brake pads and discs**: pads lose bite; discs fade earlier when hot; pads worn to the metal grind.
- **Engine**: less power, rougher running; **clutch**: slips when worn (a manual car's clutch, and the clutches of a double-clutch gearbox).
- **Breakdowns** (the "Parts can break" setting): a badly worn part can fail, with a message on screen: a blown shock absorber, soft brakes, a slipping clutch. Since 0.2.0 the failures are random in a logical way (a part above half its condition never fails; overheating, hard revving, low oil and torque spikes raise the chance of the head gasket, the bottom end, a driveshaft and the like), with a warning first, and the engine, driveline and electrical failures are separate switches that are off by default; nothing fails in a race unless you allow it.
- **Looks** (the "Worn look" setting, and one slider per look): brake discs and calipers rust, the suspension, frame and exhaust metal get grime and rust, the engine bay gets oily, the rims collect brake dust and scuffs, the cabin fades and creases, and the paint fades and rusts (paint, glass pits and haze, and the wipers need Car Surface FX). The look of the discs and the metal is set when the car is spawned, so it changes at the next spawn or garage visit.
- **Repairs**: in the Wrench Works garage, worn parts are listed under Services with their condition and a price. Pay, and the part is new again.

Wear is kept for each car, and separately for each career save, so careers never share wear. Nothing wears on traffic cars.

## Settings (ESC > Mods > Part wear)

Presets: **Off**, **Light** (slow wear, small effects, no breakdowns) and **Realistic** (the full effects). The wear and breakdown rows also take part in Wrench Works' Gameplay presets (Easy, Hardcore, Realistic, Sandbox). The page also has sliders for the wear speed, how much rough driving and age count, the strength of each effect, the breakdown chance and the strength of the worn look.

## Requirements

- BeamNG.drive 0.40.
- Wrench Works 1.8.3 or newer: it provides the Mods page and the garage repairs (1.8.9 or later for the shelf: parts taken off keep their wear and can be reconditioned). Without it the rules still run, but there is no settings page and no repair entries.
- Car Surface FX 0.4 or newer for the worn paint look; 0.4.11 for the glass pits and haze and the worn wipers.
- Street Legal's inventory (optional): oil, coolant and battery items are used through Part Wear.

## What has been tested in the game

Seen working in the game (Covet, Vivace, pickup): the worn metal look on the floor pan, arms, axles and fuel tank; the rust on brake discs at spawn; the detection of springs and dampers on the Vivace, including its front springs in the strut; the shortening of the spring beams; worn pads (longer stops) and worn shock absorbers (more bounce); the loss of power of a worn engine; a worn clutch slipping at a hard launch, on the Covet and on the Vivace's double-clutch gearbox; breakdowns of a shock absorber and the engine; the worn paint look; the dirty look of the engine bay; wear kept when you swap a part; the repairs in the Wrench Works garage. The garage's power curve does not show a worn engine's lost power; the car's acceleration does.

Found by the mod on the car but without an effect yet (leaf spring wear does nothing): the pickup's rear leaf springs, the master cylinder and the brake fluid. Built and tested only offline so far (the unit tests in `tools/`): the rust on brake calipers and hubs, and the gearbox, differential, driveshafts, turbocharger, radiator, ignition, engine oil, anti-roll bars, control arm bushes and wheel bearings. Version 0.2.0 adds the fuel system, intercooler, catalytic converter, battery, steering, flywheel, bulbs, alternator, body, glass, doors, seats and wipers, the worn looks of wheels, cabin and more models, and random failures: all of it built and tested offline only so far. The full list is in `CHANGELOG.md`; tell us if one of them does not work for you.

## For testers and modders

The testing steps for the apply layer are in `docs/PROBE_STEPS.md`; the design is in `docs/DESIGN.md`; texture credits are in `docs/TEXTURE_CREDITS.md`. The rules are in `mod/lua/common/slrrWearRules.lua` (pure, no game calls). The unit tests run with `python tools/test_wear_*.py` (they need `lupa`) and `node tools/globalcheck.js` (needs `luaparse`).

## Credits

Rust textures are made from CC0 photographs by ambientCG (https://ambientcg.com); see `docs/TEXTURE_CREDITS.md`. By Connor Moyle.
