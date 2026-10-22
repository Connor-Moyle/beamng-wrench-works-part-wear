# Changelog

## 0.2.0 (unreleased)

Built on 0.1.2 (everything from it is included). **Nothing new in this list has been seen in the game yet**: the first session that runs it is the Part Wear and Drivers test session, and this section moves each line to "seen" only with that evidence. Everything is off by default, like the rest of part wear, and part wear itself is off until you switch it on in ESC > Mods > Part wear.

Needs: Wrench Works 1.8.9 or later (the shelf calls and Recondition; the garage repairs work from 1.8.3), Car Surface FX 0.4.11 for the glass and wiper looks (0.4 for the paint look), BeamNG.drive 0.40. Street Legal's inventory calls `useItem` when you use oil, coolant or a battery.

### New parts (all built and tested offline, not seen in the game)

- **Fuel system, intercooler, catalytic converter, battery.** The fuel system (injectors and pump: a little less power at the worst), the intercooler (turbo cars), the catalytic converter (less power) and the battery (slower cranking). Each has a condition, a price and a repair in the Wrench Works garage.
- **The last five parts.** The steering (a little slack at the rack), the flywheel (inertia), the bulbs (dimmer), the alternator (a worn one charges the battery less) and the exhaust sound.
- **The body and its glass.** The body (lower break and deform limits, down to 60 %, so it crumples a little more), the glass (breaks at a lighter hit), the doors (hinges and latches) and the seat (its mounts). These change how a car crashes: a crash comparison in the game is still to do, and the finder that reads each car's structure has a dump for the first run.
- **Glass pits, haze and worn wipers** through Car Surface FX 0.4.11 (`setGlassWear`, `setWiperWear`): pitting and haze on the player's car, wiper blades that clear fewer drops. Needs "Water drops on the windows" on in Car Surface FX.
- **Still not seen from 0.1.2:** the gearbox, differential, driveshafts, turbocharger, radiator, ignition, engine oil, anti-roll bars, control arm bushes and wheel bearings, and the rust on brake calipers and hubs while driving.

### Worn looks (built offline; the new detail textures are game-cooked DDS only after a test run)

- **Worn wheels.** The rims of the stock Covet, Vivace and pickup wheels (51 rim materials) get a worn stage (brake dust and kerb scuffs) and a rusty stage (the steel's rust), as variants of the game's own rim materials with the rim's maps kept; the stage follows the worse of the wheel bearings and the pads, decided at spawn.
- **Worn cabin.** The cabin and seat materials of those cars and the game's racing, offroad and vintage seats (16 materials) get a faded and a heavily worn stage from the seat condition. The dash and the door cards share the material with the seats, so the whole cabin looks worn, not only the seats. **The cabin look applies only where the interior is the plain material.** Most cars draw their cabin through a skin material (`vivace_interior.skin_interior.arc`, `covet_interior.skin_interior.black` and so on), and for those the cabin keeps its own look until the skin variants (generated from the games skin materials, in the list) are wired in the game side; the Ardente interior and seats (own detail layer) are also left alone.
- **Metal and engine bay of 28 more models** of the car pool (from the survey of the stock cars' exhaust meshes) get the same two stages as the Covet, Vivace and pickup have; the metal uses low strengths because the atlases were not measured one by one.
- **A setting per look** (Looks: brake discs, suspension and frame, engine bay, wheel rims, interior and seats; 0 switches that look off) next to "Worn look". A material the game has not loaded yet gets no entry; the log says how many ("rims stage N (M materials, K not loaded)").
- Not possible: a different stage per corner (a material is one per car), a worn look on parts with no mesh of their own (gearbox, battery, fuel tank and the like), and a change while driving other than the brake discs.

### Random mechanical failures (built offline; the game calls have never run in a game)

- A badly worn part can fail by chance, in a logical way: a part above half its condition never fails, below that the chance rises with the wear and with what really stresses it (an overheating engine for the head gasket, hard revving and low oil for the bottom end, torque spikes for the driveline). A warning comes first (a message, a noise): stopping with the engine off for ten seconds can save the part.
- The game's own failures are used where it has them: a blown head gasket, damaged piston rings, a seized bottom end, a broken driveshaft, differential or gearbox (manual). Other parts drop to a low condition as before.
- **Off by default, and never in a race.** The engine, driveline and electrical groups are separate switches and all ship off (Effects > Breakdowns), "Parts can break" must be on, and "No failures during a race" is on (a race, a job or a chase is never ended by a random failure; the Hardcore gameplay preset turns it off). Only a car with a player seated in it rolls. A seized engine or broken shaft lasts until the car is reset in the game or repaired in the garage: test it on a throwaway car first.
- **The 0.1.2 breakdowns stay.** With "Parts can break" on and a kind's new failure group off (the default), a badly worn clutch, engine, gearbox, driveshaft, turbo, radiator, fuel pump or alternator still breaks the way it did in 0.1.2 (a drop to a low condition with a message). Switching a group on hands those kinds to the random failures, with their warning, and the 0.1.2 breakdown stops for them. The race exemption works through Street Legal's busy state (a race, a job, a chase, a scene or an open lot): the player's car is told when it changes. Not seen in the game.
- Frequency 0 to 3 times (Breakdown chance). A hook `onSlrrPartWearFailure(vehId, kind, how)` lets other mods react.

### Settings and presets

- New rows: the failure groups, the warning, no failures during a race, and one look slider per kind (above).
- **Gameplay presets.** The wear and breakdown rows are tagged gameplay for Wrench Works' Gameplay presets page (Easy: slower wear, fewer failures; Hardcore: faster wear, more failures and failures in races; Realistic and Sandbox too); the look rows are tagged graphics. Part Wear's own presets (Off, Light, Realistic) are unchanged.

### For other mods

- `recordOf`, `restore` and `recondition` keep a taken-off part's wear on the shelf, give it back when fitted and let the garage recondition it; a hook announces the wear of the parts a swap took off (Wrench Works 1.8.9 and later use them).
- `useItem(vehId, kind, item)` for Street Legal's inventory: a new battery (the wear back to new; an electric car's traction battery is set to the item's charge, never a fuel or nitrous tank), an oil change (condition only: the game keeps no oil level a mod can refill) and a coolant refill (the game has no setter that leaves the radiator alone, so a refill also clears the radiator's damage).
- `conditionsOf` lists the new parts; `setCondition` with no corner sets every corner of the kind instead of throwing.

### Fixes (found by reading and by the offline tests)

- A repaired ignition gives the game's own misfire chance back, and a worn engine's power cap gives the game's own state back at a repair and at a clear (a latch could keep the lowered power).
- Worn bulbs are dimmed once from a saved base and restored at clear (they could compound); the steering slack is forgotten while the AI drives; a hard landing and the reset reapply no longer skip an effect.

### Known limits

- **Leaf springs: no effect yet** (seen in 0.1.2: the pickup's rear leaf springs are found but the game's call that changes a spring rate does nothing on these beams). The master cylinder and the brake fluid had no measurable effect in 0.1.2, and gearbox drag was not measurable.
- None of the new parts has been measured in the game; none of the failure calls has run; the body, glass and door limits change crashes and need a crash comparison; the cooked textures for the new looks are still to be made in the game.
- A newly fitted part of a slot no table row covers keeps the old part's wear: repair it in the Wrench Works garage.

## 0.1.2 (2026-10-22)

Seen in the game (a Vivace, a pickup and a Covet, part wear on, Realistic):

- **Front springs on strut cars.** The Vivace's front springs are found (4 springs and 4 dampers on the car, the front pair in the strut part). With the front springs at 10 % the nose sat 1.3 cm lower after settling: a small change, as the model intends.
- **Clutch wear on a dual-clutch car.** The Vivace's gearbox is a dual-clutch box and now takes the clutch wear: its lock torque factor fell to 0.45 with the clutch at 0 %, and a hard 0-60 km/h launch took about 0.4 s longer (4.2 s on average new, 4.6 s worn, noisy). With the gearbox also at 0 % the factor is the product of both (0.315).
- **Anti-roll bars are found** through the torsionbars: 2 on the Vivace, 1 on the pickup and on the Covet.
- **For other mods:** `conditionsOf` gives the stored wear as rows ("front brake pads", section "brakes", 0.92 and so on), and `setWearRate` / `getWearRate` set and read a multiplier on how fast every part wears.

Found, but with no measurable effect yet:

- **Leaf spring wear has no effect yet.** The pickup's rear leaf springs are found (left and right), but with them at 10 % the ride height and pitch did not change at rest: the game's call that changes a spring's rate does nothing on these beams, so this is not a working feature. The pickup's dampers are worn as usual.
- **Master cylinder and brake fluid:** accepted without errors, but one stop from 100 km/h was not measurably longer.
- **Gearbox drag:** not measurable in a 5 s full-throttle run.

Built and tested offline only (not seen in the game; all off by default like the rest):

- The powertrain parts wear and change the car through the game's own wear fields of each device (not seen in the game yet): the gearbox (friction, shift rate of an automatic, lock torque of a dual clutch), the differential per axle, the driveshafts and halfshafts per axle, the turbocharger (boost power and friction, through the turbo module's own call), the radiator (the game's radiator integrity, kept above its leak threshold: at worst 87 % of the coolant, never a leak; switching part wear off or a reset puts the coolant back to full, whatever it was, and clears any real radiator damage), the ignition (misfire chance, split out of the engine's) and the engine oil (a little more engine friction, 15 000 km). A turbo or radiator is set when its condition changes and again after a reset; the turbo's own mileage wear of the game is set to new while ours applies and is not put back. The slot names of the stock cars tell the garage which of them a swapped part resets.
- The chassis parts (not seen in the game yet): the anti-roll bars (the stock bars are torsionbars: their rate through the game's own torsionbar call, at worst a fifth of it for a broken link), control arm and link beams (their rate, at worst 85 %, never their length), wheel bearings (a drag next to the pads', up to 65 Nm on a failing one), brake fluid (the pads fade earlier when hot) and the master cylinder (up to a fifth less torque at the pedal). Which beams count as arms is told by the part's own name, so the Vivace's toe links (in a part that says only "suspension") are not touched; the torsionbar tag the bars are found by is not yet seen in the game.
- A garage repair of the engine now gives its power back (before, the lowered power stayed after a repair), and a repaired ignition gives the game's own misfire chance back. Found by reading the code.
- Records of freeroam cars that are not used for 30 days are dropped; a record in use is kept.
- A reset reapplied only some of the effects: the list of effects being reapplied was changed while it was walked, so one entry in turn was skipped. Fixed, with the whole list copied first.

Known limits:

- The leaf springs, the master cylinder, the brake fluid and the gearbox drag above need another look in the game; none of the powertrain and chassis effects has been measured.
- A newly fitted part of a slot no table row covers keeps the old part's wear; repair it in the Wrench Works garage.

## 0.1.1 (2026-10-22)

Proven in the game since 0.1.0:

- Breakdowns (with "Parts can break" on): a shock absorber at 10 % blew within two seconds of a roll and dropped to 5 % with the message "A shock absorber has blown" on screen; the engine at 14 % gave "The engine is running rough" and dropped to 12 %. Only a part between its failure level and 15 % can break.
- Worn paint through Car Surface FX (its "Worn paint (test)" switch on): a white Covet at 20 % paint condition showed faded, dull paint, a grimy film on the roof and bonnet, scuff lines on the door and orange rust spots along the sill and arches; at 100 % only light dirt.
- Worn clutch: at a hard launch on the Covet with the clutch at 10 %, the rpm stays pinned at the top while the wheels lag (2.4 m/s after one second against 5.8 to 6.7 with a new clutch, 7 against 8.5 m/s after three seconds); in steady driving it holds. Cars with an automatic or double-clutch gearbox, like the Vivace, have no clutch device: it does nothing there.
- A part swap in freeroam sets back to new only the parts of the slot that changed, by the slot's name across the stock cars; the rest of the car keeps its wear. On the Covet with the dampers at 30 %, the front-left spring at 40 %, the front pads at 20 % and the engine at 40 %, swapping the front coilover set the four front damper and spring conditions back to 100 % and left the rear dampers, pads and engine as they were; a second swap kept them too; swapping the front brake pads reset the pads only. The parts are read a few seconds after a spawn (the game's list is still the replaced car's right after it), so a swap in the first seconds resets nothing. A slot with no front or rear in its name resets nothing. No change in frame time was seen with the 5 s refresh.

Seen with no effect yet:

- Rust on brake calipers and hubs while driving: the game switches their materials (2 of 2 meshes of the front-left wheel on the Vivace, no errors in the log), but the wheel hides them and no change was visible; a car with open wheels has not been checked.

Built and tested offline only (0.1.1):

- The part finder now reads whole words and only for the beams that can be links, so the 4-link front axles of the stock Pickup variants, the van, the Nine and the traffic cars ("4link" was read as an alignment link) are no longer skipped. The pickup of the test build has independent front coilovers, so this was not seen in the game.

Known limits:

- No spring wear on the front of strut cars like the Vivace (the front spring is not a beam the finder recognises), and none on the rear of leaf-spring pickups. Their dampers are worn as usual.
- A newly fitted part of a slot no table row covers keeps the old part's wear; repair it in the Wrench Works garage.

Still built and tested offline only: the breakdowns of the other parts (soft brakes, a spring gone soft, the clutch's own breakdown message).

## 0.1.0 (2026-10-21)

This list is only filled in as each item is proven in the game with screenshots and logs.

Proven in the game:

- Worn suspension, frame and exhaust metal look (the Worn look switch): on the Covet, the Vivace and the pickup the floor pan, suspension arms, axles, driveshaft, fuel tank and muffler take dark grime with rust patches when the car's springs and shock absorbers are worn, set at spawn for the whole car; a second spawn of the same car shows it too, and a car set back to new comes up clean. The exhaust pipes and the engine bay stay as they are (the pickup's exhaust is patchwork, as expected). Seen on the three cars on their sides (2026-10-21). The rust strength is per material: on the Vivace's black floor pan the full-strength patches read as glowing embers, so it got a lower one and now reads as old rust on black (seen 2026-10-21).

- Worn brake disc look at spawn: on the Vivace a car spawned with a worn record shows heavy rust on the worn disc and a light tint on the lightly worn one, plain steel at baseline; the stored wear is found at the first spawn of a session.

- Worn brake pads: with the pads at 5 %, a 30 % partial brake from 18 to 9 m/s took about 1.5 times as long as with new pads (2.1 s against 3.2 s on the Vivace).
- Worn shock absorbers: with all four at 0 %, a 1 m drop gave 4 bounces and about 1.3 s to settle, against 2 bounces and 0.4 s with new ones; the values reach the damper beams.
- Worn engine: with the engine at 20 %, the Covet took 7.8 s on average from standstill to 20 m/s against 6.6 s with a new one (three runs each, no overlap): the engine's output cap falls from 0.93 to 0.88 and its friction rises 1.4 times. The garage Car info power curve does not show it (192 against 190 hp on the Vivace): it reads the engine's fixed curve.
- Worn engine bay look: on the Covet with the bonnet off, the engine takes a dust film at 50 % and dark grime with some rust-brown touches at 20 %, set at spawn; hoses, the washer bottle and the battery box stay as they are. It reads as a tired dirty engine, with less shine than intended.
- A part swap in freeroam (the bonnet taken off on the Covet) keeps the car's wear: the four shock absorbers stayed at 30 % and the record key was the same after the respawn.
- Wrench Works garage repairs (freeroam): a worn shock absorber and two worn discs were listed under Services > Part wear with their condition and a price ($129 for the shock absorber); paying for the shock absorber took the entry off the list and put the part back to 100 %.

Built and tested offline only (all off by default; switch on in ESC > Mods > Part wear):

- A condition per part (shock absorbers, springs, brake pads and discs, engine, clutch, paint) that wears by distance, hard stops, heat, hard landings and age.
- Effects of worn parts: shocks bounce more, springs sit lower and a little softer, pads and discs fade earlier, the clutch slips (the numbers are from the research notes; the ones with no source are labelled as modelled in the rules file).
- Breakdowns (off with the "Parts can break" setting): a badly worn part can fail, with a message on screen: a blown shock, soft brakes, a slipping clutch.
- Worn paint look through Car Surface FX (needs its "Worn paint (test)" switch).
- Wrench Works garage: worn parts are listed under Services with their condition and a price, and a click pays and sets the part back to new.
- Worn brake disc look (switch: Worn look in the Mods page): brake discs show a surface bloom of rust and then heavy rust as the disc and pad condition falls, set when the car is spawned (it changes at the next spawn or garage visit; the red-hot brake glow is untouched); calipers and hubs change while driving. Only on cars spawned after part wear is switched on.
- Wear is kept per car and per career slot, so careers never share wear.
- Known limit of a part swap (kept wear, above): a newly fitted part keeps the old part's wear; repair it in the Wrench Works garage.
