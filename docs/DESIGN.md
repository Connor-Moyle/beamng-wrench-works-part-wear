# Part wear: design (v1)

Source of the numbers: published service and inspection figures for each part (modelled numbers are labelled in the rules file). Rules already written: `mod/lua/common/slrrWearRules.lua` (kinds, lives, abuse, presets, stages, effects as factors on the jbeam value). Probe already written: `mod/lua/vehicle/extensions/slrrWearProbe.lua` (finds springs, dampers, brake wheels, engine; applies one part's effect; reapplies two frames after a reset). Nothing has run in the game.

## What v1 covers

| Part | Condition changes | Effect (never above the jbeam value) | Visual layer |
|---|---|---|---|
| Dampers (per corner) | distance, landings, kerbs | rebound -80 %, compression -60 % at full wear, floor 0.15: floats and bounces more | worn rust/grime on the damper mesh (3 stages) |
| Springs (per corner) | distance, landings, bottoming | sag up to 15 mm (beam rest length), rate -10 % | rust on bare-metal spring meshes |
| Brake pads (front, rear) | braking energy, heat | torque -8 %, then x0.6 below 10 % (grind); squeal coefficient up | none |
| Rotors | pad energy, heat | less brake mass: earlier fade | rusty/scored rotor material |
| Engine internals, filter | distance, limiter, overheat | one torque cap with Street Legal's (min of both), misfire, friction | oily/grimy engine mesh |
| Clutch | launches, slip | lock torque -55 %, free play up | none |
| Body paint | age, distance | none | per-mesh paint fade (the game's own paint aging path) |

Later (v2, from the research doc): bushings, ball joints, steering, bearings, CV, mounts, exhaust, electrics, glass pitting.

## State, per car

- One record per part path (the Wrench Works key): `{kind, c = 0..1, stats, km, flags}`. Only parts with `c < 0.995` or non-default stats are stored.
- Vehicle extension `slrrWearVeh` (from the probe) holds it live, wears it every 0.5 s, reports to GE every 5 s and at stage changes (like the tyre module's reports).
- GE module `slrrWear` keeps the store per car, keyed by the car's persistent id when it has one (Wrench Works / career cars) else by model + config; saved as JSON under the user folder `settings/slrr_partwear/`, and written through the career save when the career owns the car.
- At spawn / rebuild GE sends the record back (`restoreSnapshot` pattern of the tyre module: the vehicle holds it until it has found its parts, a reset re-applies it two frames later).
- Wrench Works: the record travels with the part (shelf and back); the repair tool offers recondition / replace; market `wear` becomes `c = 1 - wear` when fitted. This part waits for the Wrench Works owner (9e); v1 works without it.
- Crash capture (`slrrGarageVeh.capture`) must not read our sag as crash damage: the extension tells it which beam ids it manages.

## Mods menu (ESC > Mods, one page "Part wear")

Whole feature OFF by default (`wearEnabled = false`). Presets Off / Light / Realistic. Settings: lifeScale, abuseScale, ageScale, effectStrength, per-group effects switches (suspension, brakes, engine), springSagMax, springRateLoss, damperLossMax, brakeTorqueLoss, enginePowerLoss, failures + failureRate, visualWear + stages, aiWear off, startUsed. Off removes every effect live (jbeam values put back). Defaults and ranges are in `slrrWearRules.lua`.

## Build order

1. Rules + probe (done, offline). 2. Vehicle extension: wear tick and the effects for dampers, springs, pads, engine; tests with the stand-in car. 3. GE store + Mods page + restore. 4. Capture fix with Wrench Works. 5. Visual stages (file-defined worn materials through the glowMap-at-spawn route proven for the tyre look; one stage material per stock material, textures CC0 or procedural, shipped pre-cooked). 6. Game tests with 80, one part at a time.

## Risks to settle first

Reset ordering (apply a frame after), double application with Street Legal's engine cap and BeamNG's `partCondition` (one owner per coefficient), instability (factors never above 1.0, steps at most 10 % per frame), switching material only at spawn (the tyre look showed switch-ins after spawn render black).
