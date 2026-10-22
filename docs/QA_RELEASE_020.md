# Part Wear 0.2.0: what 80 checks in the game, and what moves in the changelog (0f, 2026-10-22)

For 80's slot-6 session, next to 82's QA_SLOT6_BLOCK_80.md (sections E and F there are the body kinds and the garage; this block covers everything else new in 0.2.0). Run it as the player where there is a player path (keys, the garage, Street Legal's inventory); the console lines are probes only. Nothing here has been seen in a game yet. After the run, each CHANGELOG line moves from "built offline" to "seen" ONLY with its evidence (frame, log line or number), and a line that failed or showed nothing moves to "Known limits", like the leaf springs did in 0.1.2.

**Build.** Part Wear from `release-020` (with 82's rim-look/failures merges), Wrench Works 1.8.9 or later, Car Surface FX 0.4.11 ("Water drops on the windows" on), Street Legal master (inventory). Settings in ESC > Mods > Part wear: Part wear on, Realistic, Worn look 1, "Parts can break" on. Restore the settings afterwards.

## H. The textures (first, they gate everything visual)
1. Done (82, 80's cook): the six `rim_grime_*` and `seat_wear_*` textures are the game's cooked DDS in `mod/art/slrr_partwear` (the PNGs are gone) and `python tools/test_wear_textures.py` says ok. Check here only that they load: no flat black and no errors (step 2).
2. The log has no errors about `rim_grime`, `seat_wear` or `stages.materials.json`; nothing renders flat black.

## I. The worn looks (a Covet, a Vivace, a pickup; each look is decided at spawn, so set the conditions first, then respawn)
For each car: set conditions with `slrrWear.setCondition(kind, corner, c)` (c 1.0 as the control, 0.45 for stage 1, 0.2 for stage 2), respawn, screenshot the car from 3 m (wheels, cabin through the window, under the bonnet) and read the log:
1. **Rims:** `bearing` and `padF/padR` at 0.2: the log line `rims stage 2 (M materials, K not loaded)`; brake dust and scuffs (stage 1) or rust (stage 2) on the rims vs 1.0. Note M and K: if K is large for the car's own rims, say which materials (82 needs it).
2. **Cabin:** `seat` at 0.2 (or the body): `interior stage N (M materials, K not loaded)`; the cabin looks faded and creased; the Ardente interior and a chosen interior skin stay unchanged (expected).
3. **Metal and bay of another model:** spawn two cars from the list (for example a bolide and a midsize): springs/dampers 0.2 and engine 0.2: the log says metal and engine stage; the metal is not glowing like embers (the Vivace's atlas needed low strengths; these were not measured): frames.
4. **Sliders:** Looks > each of the five set to 0, respawn: that look is gone, the others stay.
5. Frame time (`getPerf`, 60 samples) with all looks on vs part wear off, Low.

## J. Random failures (a THROWAWAY car: a seized engine and a broken shaft last until reset)
No force call exists, so use the seeded random and time: `slrrWear.setRandom(function() return 0 end)` makes every roll succeed; a roll happens once per minute of driving (engine on, over 1 m/s, a player seated). Settings: "Parts can break" on, Breakdown chance 3, the group under test on.
1. **Warning then failure (engine):** `oil` 0.05, `engine` 0.05, `radiator` 0.05, Engine failures on; drive 60 s; a message ("The temperature is creeping up..." or "The engine is knocking...") appears; about 40 to 90 s later the failure: log the game's flags (`thermals.headGasketBlown` / `pistonRingsDamaged` / `connectingRodBearingsDamaged`, `engine.isBroken` for a seize), coolant or oil leak, torque x0.8 for gasket and rings, a seized engine does not start. Reset the car: what stays (the condition store), what clears.
2. **Cancel:** do 1 but stop and switch the engine off for 10 s during the warning: "The noise has stopped", no failure, and no new warning for that part for 10 minutes.
3. **Driveline:** `cv` 0.05, Driveline failures on: a warning, then the driveshaft breaks (the car loses drive: log `shaft.isBroken`). Repeat with `gearbox` (manual) and `diff`.
4. **No failure in a race:** with Street Legal, start a street race with the same conditions: no failure during it (the default); the Hardcore gameplay preset turns that off: one failure can then happen in a race.
5. **A car nobody sits in never rolls**, and a healthy car (all above 0.5) never warns over 5 minutes with rand = 0.
6. **The way back:** repair the part in the Wrench Works garage / reset the car: the condition goes back and the part can fail again later. Note what the career offers for a seized engine (tow, rebuild) for a5.
7. Hook: `onSlrrPartWearFailure(vehId, kind, how)` fires once per failure (print it from the console).

## K. Settings and Gameplay presets
1. ESC > Mods > Part wear: the new rows exist (three failure groups off, warnings on, no failures during a race on, five look sliders) and keep their values after a restart.
2. Mods > Gameplay presets: load Easy, Hardcore, Realistic, Sandbox: the wear rows move (Easy slower, Hardcore faster; Hardcore turns "no failures in a race" off), the look rows do not; Normal resets every Part Wear gameplay row to its default. Part Wear's own preset (Off/Light/Realistic) still works.

## L. Street Legal's inventory (useItem, the player path)
In a Street Legal career with Part Wear on and a worn engine oil (0.2), battery (0.2) and radiator damage: use an oil item, a coolant item and a battery item from the inventory page: the oil and battery conditions go back to new (the garage list shows it), the coolant is refilled (and the radiator damage is cleared: expected), the item leaves the boot only when the car took it; an electric car: the traction battery charge is set to the item's charge and a fuel tank is untouched.

## M. Still-unseen 0.1.2 parts (values, like the clutch evidence: set the condition, read the device fields, then one hard run)
Gearbox (friction, shift rate; a DCT lock torque), differential per axle, driveshafts, turbo (`wearFrictionCoef`, boost), radiator (`radiatorDamage` stays under 0.015 at the worst: no leak), ignition (misfire), oil, anti-roll bars (torsionbar rate), bushings, wheel bearings (drag from a quarter of the life), calipers and hubs rust while driving (frame at 1 m). For each: the field before and after at 0.2, and whether anything is measurable; "no effect" lines go to Known limits.

## N. The new parts (82's section F lists the garage; this is the car)
Fuel (`electrics.fuel` unaffected; power at 0.2), catalytic converter, intercooler (turbo car), battery and starter (cranking time), steering slack (a straight line's drift), flywheel (idle), bulbs (brightness), alternator (battery charge over 10 minutes), exhaust sound: for each the field and one measured number, as in section M.

## What each section proves in the changelog
| CHANGELOG line | Section |
|---|---|
| New parts (fuel, intercooler, cat, battery, the last five) | N |
| Body, glass, doors, seat; glass pits/haze and wipers | 82's E and F |
| Still not seen from 0.1.2 | M |
| Worn wheels, cabin, 28 models, a setting per look | H, I |
| Random failures (each game call) | J |
| Gameplay presets and the new rows | K |
| useItem | L |
