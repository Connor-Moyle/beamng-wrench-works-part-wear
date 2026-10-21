# Testing the apply layer in the game

Run these in the vehicle Lua console of the car under test, with part wear switched OFF on the Mods page (when it is on, the part wear skeleton hands its own conditions to the probe and overrides what you set; with it on, use `slrrWear.setCondition(kind, corner, c)` instead).

1. `extensions.load('slrrWearProbe'); slrrWearProbe.detect()`: the log lists springs, dampers (bump stops are skipped), wheels and the engine.
   Expect 4 springs and 4 dampers on a typical car; a leaf-spring pickup lists fewer or none (leaf springs are not single spring beams).
2. `slrrWearProbe.damper('FL', 0.3)`, then drive over a kerb and let the corner bounce: it should float and take longer to settle.
   `slrrWearProbe.spring('FL', 0.3)`: the front-left corner sits lower (measure the node height, about 8 mm at Realistic) and a little softer.
   Reset the car (R): the effect comes back two frames later ('reapplied after a reset' in the log). `slrrWearProbe.clear()` puts everything back.
3. `slrrWearProbe.pads('F', 0.05)`: longer stopping distance (100 to 0 km/h), more squeal; `slrrWearProbe.pads('F', 1)` back.
4. `slrrWearProbe.engine(0.2, 0.5)`: less power (dyno), a little rougher; `clear()` restores it.
`slrrWearProbe.preset('Light')` or `('Off')` changes the strength; `status()` prints what is applied.
