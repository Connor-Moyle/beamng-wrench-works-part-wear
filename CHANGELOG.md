# Changelog

## Next (not released)

Built offline, not seen in the game:

- **Worn wheels.** The rims of the stock Covet, Vivace and pickup wheels (51 rim materials) get a worn stage (brake dust and kerb scuffs) and a rusty stage (the steel's rust), as variants of the game's own rim materials with the rim's maps kept; the game side puts them in the car's glowMap at spawn from the bearing and pad conditions (82's part). The cabin and seat materials of the same cars and the game's racing, offroad and vintage seats (16 materials) get a worn stage (faded) and a heavily worn stage (creased, shiny patches), from the seat condition; only materials with no detail layer or lit stage of their own. The suspension, frame and exhaust metal and the engine bay of 28 more models of the car pool (the generated list `slrrWearLookList.models`, from the survey of the stock cars' exhaust meshes; the metal at the low strengths of the Vivace, untuned for each atlas) get the same two stages. The new detail textures are game-cooked DDS only after a test run.

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
