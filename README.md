# Part wear (Wrench Works): offline rules and the vehicle-side probe

Status: offline rules and a probe for the tester. Nothing here has run in the game. The design and the 11-step build order are in
`docs/PART_WEAR_RESEARCH.md` of the Graph repo.

- `mod/lua/common/slrrWearRules.lua`: the pure rules (condition 0..1, stages, wear per step, failure rolls, the effect of each part kind as factors on the
  jbeam value, presets Realistic / Light / Off, the one engine cap, the 10 % step limit). `python tools/test_wear_rules.py`.
- `mod/lua/vehicle/extensions/slrrWearProbe.lua`: finds the springs, dampers, brake wheels and engine of any car and applies one part's worn effect from the
  rules. `python tools/test_wear_probe.py` runs it against a stand-in car.

Rules that every effect follows: a factor is never above 1.0 (never stiffer or stronger than the jbeam), none goes to zero, values step in by at most 10 %
per frame, and the values are computed from the jbeam base, never from the current value. A vehicle reset overwrites what an extension sets in `onReset`,
so the probe reapplies two frames after a reset.

## Probe steps for the tester (vehicle Lua of the car under test)
1. `extensions.load('slrrWearProbe'); slrrWearProbe.detect()`: the log lists springs, dampers (bump stops are skipped), wheels and the engine.
   Expect 4 springs and 4 dampers on a typical car; a leaf-spring pickup lists fewer or none (leaf springs are not single spring beams).
2. `slrrWearProbe.damper('FL', 0.3)`, then drive over a kerb and let the corner bounce: it should float and take longer to settle.
   `slrrWearProbe.spring('FL', 0.3)`: the front-left corner sits lower (measure the node height, about 8 mm at Realistic) and a little softer.
   Reset the car (R): the effect comes back two frames later ('reapplied after a reset' in the log). `slrrWearProbe.clear()` puts everything back.
3. `slrrWearProbe.pads('F', 0.05)`: longer stopping distance (100 to 0 km/h), more squeal; `slrrWearProbe.pads('F', 1)` back.
4. `slrrWearProbe.engine(0.2, 0.5)`: less power (dyno), a little rougher; `clear()` restores it.
`slrrWearProbe.preset('Light')` or `('Off')` changes the strength; `status()` prints what is applied.
