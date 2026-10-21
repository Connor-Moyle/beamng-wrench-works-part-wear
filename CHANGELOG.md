# Changelog

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
- The powertrain parts wear and change the car through the game's own wear fields of each device (not seen in the game yet): the gearbox (friction, shift rate of an automatic, lock torque of a dual clutch), the differential per axle, the driveshafts and halfshafts per axle, the turbocharger (boost power and friction, through the turbo module's own call), the radiator (the game's radiator integrity, kept above its leak threshold: at worst 87 % of the coolant, never a leak; switching part wear off or a reset puts the coolant back to full, whatever it was, and clears any real radiator damage), the ignition (misfire chance, split out of the engine's) and the engine oil (a little more engine friction, 15 000 km). A turbo or radiator is set when its condition changes and again after a reset; the turbo's own mileage wear of the game is set to new while ours applies and is not put back. The slot names of the stock cars tell the garage which of them a swapped part resets.
- The chassis parts (not seen in the game yet): the anti-roll bars (the stock bars are torsionbars: their rate through the game's own torsionbar call, at worst a fifth of it for a broken link), control arm and link beams (their rate, at worst 85 %, never their length), wheel bearings (a drag next to the pads', up to 65 Nm on a failing one), brake fluid (the pads fade earlier when hot) and the master cylinder (up to a fifth less torque at the pedal). Which beams count as arms is told by the part's own name, so the Vivace's toe links (in a part that says only "suspension") are not touched; the torsionbar tag the bars are found by is not yet seen in the game.
- The engine split and the battery (not seen in the game yet): the fuel pump and injectors, the catalytic converter and (on a car with a turbo or supercharger) the intercooler each take a small share of the engine's power, all in one cap with the internals and the air filter (at worst x0.94, x0.85 and x0.95); a weak battery lowers the starter's torque to 60 %.
- The last five (not seen in the game yet): the steering rack and tie rods add a dead zone (6 % at worst) and a slack (0.08 s) to the steering input, through the value the game's input writes and its steering reads (the dead zone is left out on a gamepad, whose own dead zone is in the input, and under the AI); the flywheel adds up to 8 % to the engine's inertia; worn bulbs dim (down to 60 %) and from 70 % worn flicker; a worn alternator charges a model of the starter battery (ours: the game has none, and it starts full at each spawn) more slowly, so with the lights on the starter turns slower (never under 40 %); a worn exhaust is louder and less muffled through the engine's own exhaust sound parameters, inside the game's own sport-exhaust range. The flywheel inertia and the dead zone are modelled; no source ties them to wear.
- The body, the glass, the door hinges and the seat mounts (not seen in the game yet, and the last kinds to ship: weakening the body changes how the whole car crashes, so it needs per-car dumps and crash comparisons first): their beams' deform and strength limits go down to x0.6 for the body and frame, x0.7 for the glass, x0.7 / x0.8 for a door's hinge springs, and a seat mount gets x0.85 softer and x0.8 weaker. A beam with no strength limit keeps none. The glass pits and haze and the wiper blades' share are rules for Car Surface FX's setGlassWear and setWiperWear (the game side wires them). `slrrWearProbe.dumpStructure()` lists what it finds on a car.
- A reset reapplied only some of the effects: the list of effects being reapplied was changed while it was walked, so one entry in turn was skipped. Fixed, with the whole list copied first (offline test).

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
