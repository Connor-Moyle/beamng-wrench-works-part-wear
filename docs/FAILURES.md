# Random mechanical failures (design, 0f, 2026-10-22)

Connor: "add random mechanical failures, so for instance if you haven't repaired your axles one could break but this should be configurable, things like headgasket failure, bottom end bearing failure etc, it should be random chance of happening, but in a logical way".

Status: design for 82 (owner of Part Wear) and 62; the pure rules and their tests come next (`slrrFailRules.lua`, `tools/test_wear_failures.py`), the car-side apply after 82 agrees. Nothing is run in game.

## What exists
`rules.failureStep/failureRoll` (0.1.x): a part below condition 0.15 can fail, hazard per hour `failureRate * (0.15 - c) / 0.15`, and a failure sets the part's condition to a low "failed" level (`M.FAILURE`: a blown shock, soft brakes, a slipping clutch ...) with a message; only with the setting `failures` on. That is a flat chance with no cause, no warning and no authentic result. This design replaces the roll with a cause-driven hazard and warnings, keeps the same storage (the condition is the whole state, so a failed part stays failed until repaired and survives a respawn and a save), and keeps `failures` as the master switch and `failureRate` as the frequency.

## The hazard (per minute of driving)
For a part of kind k with condition c (1 = new):

    h = BASE[k] * wear(c) * stress(k) * failureRate * kindSwitch(k)        (per minute, while the car is driven)
    wear(c) = 0 for c >= 0.5;  ((0.5 - c) / 0.5)^2 below   (0.25 -> 0.25, 0.1 -> 0.64, 0 -> 1)

So a healthy or serviced part (c >= 0.5; a repair puts it back to 1) has NO chance, the chance grows with the square of the wear, and what really kills the part multiplies it (stress, capped at 10, floored at 0.1). Each minute the car is driven (engine running, speed over 1 m/s) one roll: `rand() < 1 - exp(-h)`, `rand` seeded (vehicle id, game minute) so tests and 80's checks repeat. A failed part (already at its failure level) cannot fail again. With `failureRate` 1 and a worn-out part under the worst stress the expected time to failure is `1 / (BASE * 10)` minutes (head gasket 10 min of hard overheating; an axle about 25 min of repeated launches); with a healthy part, never.

## The kinds, their cause, and the result
BASE is per minute at wear 1 and stress 1 (MODELLED, tuned by 80's feel). The result uses the GAME's own failure where the game has one (guarded calls, `pcall`), else the existing condition drop. "Authentic" = through the game's own function.

| failure | part kinds read | stress (what really kills it) | result | authentic? |
|---|---|---|---|---|
| Head gasket | radiator, engine | coolant temperature: x0.2 under 95 C, then +1 per 5 C over 100 C (cap 10); a low coolant level | `thermals:setPartConditionThermals(odometer, {headGasketBlown = true}, visual)` (table form with only the flag: coolant leak 100 g/s, torque x0.8) | yes (the game's own) |
| Piston rings | engine, oil | oil condition under 0.3 (overdue oil service), rpm within 10 % of the limiter, overheating | `{pistonRingsDamaged = true}` (oil leak 10 g/s, torque x0.8) | yes |
| Bottom-end (rod) bearings | engine, oil | low oil level or pressure, rpm over 90 % of the limit, oil overdue, cold revving | a knock warning, then `engine:lockUp()` (the game's engine seizure: torque 0, starter off, damage flag) and the thermals flag `{connectingRodBearingsDamaged = true}` | yes (lockUp is the game's) |
| Axle / halfshaft / CV | cv | torque spikes: a clutch dump launch, wheelspin biting, a hard landing (the existing abuse counters) in the last 60 s: stress 1 + 0.5 per event | `shaft:onBreak()` of the driveshaft/halfshaft device (the game's own break: `isBroken`, the torque path stops), else a CV joint knock via the condition drop | yes where the device has `onBreak` |
| Differential | diff | the same spikes, low oil (condition) | `differential:onBreak()` | yes |
| Gearbox | gearbox | shifts at high rpm, launches, limiter seconds | manual: `gearbox:onBreak()`; others: the existing condition drop (grinding, slipping) | manual only |
| Clutch | clutch | launches, slip seconds | the existing drop (slipping), not the game's permanent damage flag | no (plain) |
| Turbo | turbo | oil condition, overheating | the existing drop (lost boost) | no |
| Fuel pump | fuel | high load with low fuel | the existing drop (starving at load) | no |
| Alternator, battery | alternator, battery | age | the existing drop | no |
| Springs, dampers, links, bushings, bearings | suspension kinds | landings, kerbs | the existing drop | no |
| Brake fluid, master | fluid, master | hot brakes (boiling) | the existing drop (soft pedal) | no |
| Radiator | radiator | impacts (the game's own) | not here | - |

Not offered (honest list): a timing belt (the game has no timing model), tyre failures (Car Surface FX's blowouts own them; no double), engine block and cylinder wall melting (the game does it itself from overheating: left alone), a spring beam snapping (no game function to break one on a healthy car).

## Warnings
Most failures announce themselves, so a player who maintains the car rarely sees one. A roll that succeeds does not apply at once: the part goes "pending" for a warning time W (head gasket 90 s, rings 60 s, bearings 40 s, gearbox 30 s, axle 15 s; sudden ones have none: a CV or axle under a spike, the clutch) and the player is told with a message in plain words (`The engine is knocking`, `The temperature is creeping up: ease off`, `Something is clunking in the rear axle`, `The gearbox is whining`). During the warning the hazard is gone from the roll but the failure comes at the end of W unless the player stops: speed under 1 m/s with the engine off for 10 s cancels it and puts that kind on a 10 minute cooldown, so "pull over" is the right answer. Honest limit: the cues are messages (and the temperature gauge for overheating); a mod cannot add engine knock audio.

## Settings (Mods menu, tab Part Wear, group Breakdowns; every row tagged `gameplay` for ba's presets: Hardcore higher, Easy off or low)
- `failures` (exists): master switch, default per preset (Realistic on).
- `failureRate` (exists): 0 to 3, "Breakdown chance".
- per group on/off: engine internals (gasket, rings, bearings), drivetrain (axle, diff, gearbox, clutch), cooling and electrics, suspension and brakes. Default on.
- `failureWarnings`: warnings on or off (default on; off makes every failure sudden).
- `failureNeverRacing`: no failure while Street Legal's race, job or chase is running (default off; the Easy preset sets it on). Read through Street Legal's `sl_career.freeToStart` busy state, guarded, nothing when SL is not there.
- debug force (not a setting): `slrr_partwear.forceFailure(vehId, kind)` from the console, for 80: makes that kind pending now and fails after its warning; `slrr_partwear.hazard(vehId)` lists the current hazard per kind and its stress terms.

## Integration (82 owns the route; proposal)
- `mod/lua/common/slrrFailRules.lua` (pure, mine): `BASE`, `wear(c)`, `stress(kind, inputs)`, `hazardPerMin(kind, c, inputs, settings)`, `roll(h, dtMin, rand)`, `WARN` (seconds and texts), `pending` state transitions, `cancels(state)`; tested by `tools/test_wear_failures.py` (lupa).
- `slrrWear.lua` (82): replaces `failureStep` for the kinds in the table with one call per minute: gathers the inputs it already measures (coolant temperature, oil, rpm and limiter seconds, the launch and landing counters), calls the rules, runs the pending machine, applies the result through the guarded calls above, stores the lowered condition as now (so the repair list and `conditionsOf` see the part failed).
- Career side: a locked-up engine or a broken shaft leaves the car undrivable: a5's tow and the repair list handle "car can't move" the way they do for a wreck; the repair costs follow the part conditions as for every other worn part.
- Nothing runs with part wear off, the master `failures` off, or a car that is not watched.

## Tests (the pure rules)
wear(c): zero from 0.5 up, squared below; stress caps and floors; a healthy part never fails over a million rolls; a worn part under the worst stress fails within the expected time on average (seeded); frequency 0 is never, 3 is three times as often; per-kind switches; warnings: pending, cancel on stopping, cooldown, `warnings off` is sudden; a failed part cannot fail again; garbage inputs (NaN, nil) give hazard 0; the table has a game function name for every authentic row.

## Open questions for 82
1. Does `slrrWear.lua` already measure coolant temperature, rpm over the limiter, oil level and a launch counter (the `ABUSE_KM` events say launch, landing, limiter_s, overheat_s exist), or do I get the inputs from a reader like `slrrWearLook` does?
2. May the apply for the engine failures go through the thermals device handle that `slrrWear` already holds (`powertrain.getDevice('mainEngine')` and its `thermals`)?
3. Is a tow/repair hook from a5 needed on your side, or does the condition store suffice for SL?

## Answers (82, 2026-10-22) and what changed
- slrrWear already measures `overheat_s`, `limiter_s`, distance and drive time; the rules accept those as stand-ins: `inputs.overheatS` (seconds over the overheat line in the last minute, used when there is no `coolantC`) and `inputs.limiterS` (rev limiter seconds, counts as revving). Launch and landing counts are new measurements (82 adds them if wanted; without them the axle stress is 1).
- The engine apply goes through the thermals handle `slrrWear` already holds, table forms only, guarded, with a condition-only fallback.
- Every fail event carries a named `how` (headGasket, rings, seize, shaft, diff, gearbox, or the plain kind) and a `kind`; Part Wear fires the GE hook `onSlrrPartWearFailure(vehId, kind, how)` so Street Legal and Drivers can react (a message, a tow, an injury).
- The first test of `lockUp()` and `onBreak()` is on a throwaway car (they change the car for good); applied only after the warning time and not during a race with never-racing on.
