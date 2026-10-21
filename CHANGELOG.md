# Changelog

## 0.1.0 (not released)

This list is only filled in as each item is proven in the game with screenshots and logs.

Proven in the game:

- Worn suspension, frame and exhaust metal look (the Worn look switch): on the Covet, the Vivace and the pickup the floor pan, suspension arms, axles, driveshaft, fuel tank and muffler take dark grime with rust patches when the car's springs and shock absorbers are worn, set at spawn for the whole car; a second spawn of the same car shows it too, and a car set back to new comes up clean. The exhaust pipes and the engine bay stay as they are (the pickup's exhaust is patchwork, as expected). Seen on the three cars on their sides (2026-10-21).

- Worn brake disc look at spawn: on the Vivace a car spawned with a worn record shows heavy rust on the worn disc and a light tint on the lightly worn one, plain steel at baseline; the stored wear is found at the first spawn of a session.

- Worn brake pads: with the pads at 5 %, a 30 % partial brake from 18 to 9 m/s took about 1.5 times as long as with new pads (2.1 s against 3.2 s on the Vivace).
- Worn shock absorbers: with all four at 0 %, a 1 m drop gave 4 bounces and about 1.3 s to settle, against 2 bounces and 0.4 s with new ones; the values reach the damper beams.
- Wrench Works garage repairs (freeroam): a worn shock absorber and two worn discs were listed under Services > Part wear with their condition and a price ($129 for the shock absorber); paying for the shock absorber took the entry off the list and put the part back to 100 %.

Built and tested offline only (all off by default; switch on in ESC > Mods > Part wear):

- A condition per part (shock absorbers, springs, brake pads and discs, engine, clutch, paint) that wears by distance, hard stops, heat, hard landings and age.
- Effects of worn parts: shocks bounce more, springs sit lower and a little softer, pads and discs fade earlier, the engine loses power, the clutch slips (the numbers are from the research notes; the ones with no source are labelled as modelled in the rules file).
- Breakdowns (off with the "Parts can break" setting): a badly worn part can fail, with a message on screen: a blown shock, soft brakes, a slipping clutch.
- Worn paint look through Car Surface FX (needs its "Worn paint (test)" switch).
- Wrench Works garage: worn parts are listed under Services with their condition and a price, and a click pays and sets the part back to new.
- Worn brake disc look (switch: Worn look in the Mods page): brake discs show a surface bloom of rust and then heavy rust as the disc and pad condition falls, set when the car is spawned (it changes at the next spawn or garage visit; the red-hot brake glow is untouched); calipers and hubs change while driving. Only on cars spawned after part wear is switched on.
- The metal look's rust strength: on the Vivace's black floor pan the full-strength patches read as glowing embers, so both stages are toned down (not yet seen).
- Wear is kept per car and per career slot, so careers never share wear.
