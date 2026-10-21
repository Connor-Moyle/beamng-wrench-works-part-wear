-- slrrWearRules: the pure rules of part wear. No game calls: the vehicle extension (slrrWear) and the garage side read the same numbers from here,
-- and tools/test_wear_rules.py checks them offline.
-- A part has a condition c, 0..1 (1 = new; the player sees it as a percentage) and a wear w = 1 - c. Condition never rises except by repair.
-- Effects are FACTORS on the car's own jbeam value (never above 1.0: raising a spring or damper above its jbeam value can blow up light nodes) or
-- small absolute amounts (sag in mm, drag in Nm); the vehicle side applies them from the jbeam base value, never to the current value.
-- Source of the numbers: published service and inspection figures for each part; a number with no source is labelled MODELLED in a comment.
local M = {}

local function clamp(x, a, b) return x < a and a or (x > b and b or x) end
M.clamp = clamp

-- real kilometres of normal use at lifeScale 1; `days` for the parts that age by the calendar (the game's day rate decides what a day is)
M.KINDS = {
  damper = {life = 100000, group = 'suspension'}, spring = {life = 200000, group = 'suspension'}, swaybar = {life = 150000, group = 'suspension'},
  bushing = {life = 150000, group = 'suspension'}, balljoint = {life = 150000, group = 'suspension'}, steering = {life = 180000, group = 'suspension'},
  bearing = {life = 200000, group = 'suspension'},
  padF = {life = 40000, group = 'brakes'}, padR = {life = 80000, group = 'brakes'}, rotor = {life = 80000, group = 'brakes'},
  caliper = {life = 150000, group = 'brakes'}, fluid = {days = 1095, group = 'brakes'}, master = {life = 200000, days = 3650, group = 'brakes'},
  engine = {life = 350000, group = 'engine'}, turbo = {life = 150000, group = 'engine'}, fuel = {life = 150000, group = 'engine'}, intercooler = {life = 250000, group = 'engine'}, oil = {life = 15000, group = 'engine'}, filter = {life = 25000, group = 'engine'}, ignition = {life = 60000, group = 'engine'},
  exhaust = {days = 2920, group = 'engine'}, cat = {life = 200000, group = 'engine'}, radiator = {days = 3650, group = 'engine'},
  mounts = {life = 150000, group = 'drive'}, clutch = {life = 150000, group = 'drive'}, gearbox = {life = 250000, group = 'drive'},
  cv = {life = 200000, group = 'drive'}, diff = {life = 300000, group = 'drive'},
  battery = {days = 1460, group = 'electrics'}, alternator = {life = 200000, group = 'electrics'}, lights = {life = 200000, days = 5475, group = 'electrics'},
  flywheel = {life = 300000, group = 'drive'},
  paint = {life = 300000, days = 4380, group = 'body'},        -- the car's paint as a whole (clearcoat 8-15 years in the research; the split between km and age is MODELLED)
}

-- extra kilometres of wear one event costs, per kind (Street Legal's abuse counters feed these)
M.ABUSE_KM = {
  oil = {overheat_s = 2, limiter_s = 0.5}, turbo = {overheat_s = 1, limiter_s = 0.5},
  engine = {limiter_s = 1.5, overheat_s = 3, coldrev_s = 1},
  clutch = {launch = 3, slip_s = 0.5},
  damper = {landing = 4, kerb = 0.5},
  spring = {landing = 3, bottoming = 1},
  padF = {hardstop = 20, hot_s = 0.5}, padR = {hardstop = 10, hot_s = 0.25},
  rotor = {hardstop = 8, hot_s = 0.2},
  bearing = {kerb = 2},
  balljoint = {kerb = 2, landing = 3},
}

M.PRESETS = {
  Realistic = {wearEnabled = true, lifeScale = 0.1, abuseScale = 1.5, ageScale = 1, effectStrength = 1, springSagMax = 25, springRateLoss = 0.05,
               damperLossMax = 0.8, brakeTorqueLoss = 0.08, enginePowerLoss = 0.15, failures = true, failureRate = 1, judder = 1, visualWear = 1},
  Light = {wearEnabled = true, lifeScale = 0.03, abuseScale = 0.5, ageScale = 0.3, effectStrength = 0.5, springSagMax = 12, springRateLoss = 0.02,
           damperLossMax = 0.5, brakeTorqueLoss = 0.04, enginePowerLoss = 0.08, failures = false, failureRate = 0, judder = 1, visualWear = 0.6},
  Off = {wearEnabled = false, lifeScale = 0.1, abuseScale = 0, ageScale = 0, effectStrength = 0, springSagMax = 0, springRateLoss = 0,
         damperLossMax = 0, brakeTorqueLoss = 0, enginePowerLoss = 0, failures = false, failureRate = 0, judder = 0, visualWear = 0},
}
M.RANGES = {lifeScale = {0.01, 1}, abuseScale = {0, 3}, ageScale = {0, 3}, effectStrength = {0, 2}, springSagMax = {0, 40}, springRateLoss = {0, 0.2}, wearRate = {0.05, 20},
            damperLossMax = {0, 0.9}, brakeTorqueLoss = {0, 0.3}, enginePowerLoss = {0, 0.3}, failureRate = {0, 3}, judder = {0, 2}, visualWear = {0, 1}}

-- the settings of a preset, as a fresh table; a value in `over` replaces the preset's (clamped to its range)
function M.settings(preset, over)
  local s = {}
  for k, v in pairs(M.PRESETS[preset or 'Realistic'] or M.PRESETS.Realistic) do s[k] = v end
  for k, v in pairs(over or {}) do
    local r = M.RANGES[k]
    s[k] = (r and type(v) == 'number') and clamp(v, r[1], r[2]) or v
  end
  return s
end

-- What a garage charges to put a part back to new (MODELLED, round numbers for a mid-priced car): the price of the part at 0.3 of it for a part that is only a little worn, all of it when
-- fully worn. mult is the garage's price multiplier.
M.PRICE = {damper = 150, spring = 130, rotor = 140, padF = 90, padR = 70, engine = 2500, filter = 40, clutch = 600, paint = 900, gearbox = 900, diff = 500, cv = 350, turbo = 1100, radiator = 300, ignition = 120, oil = 60,
          swaybar = 180, bushing = 260, bearing = 220, fluid = 80, master = 320, fuel = 380, cat = 350, intercooler = 450, battery = 160, alternator = 260, exhaust = 280, steering = 340, lights = 40, flywheel = 400}
M.NAME = {damper = 'shock absorber', spring = 'spring', rotor = 'brake disc', padF = 'front brake pads', padR = 'rear brake pads', engine = 'engine internals', filter = 'air filter',
          clutch = 'clutch', paint = 'paint', gearbox = 'gearbox', diff = 'differential', cv = 'driveshafts', turbo = 'turbocharger', radiator = 'radiator',
          ignition = 'ignition', oil = 'engine oil',
          swaybar = 'anti-roll bar', bushing = 'control arm bushes', bearing = 'wheel bearing', fluid = 'brake fluid', master = 'brake master cylinder',
          fuel = 'fuel pump and injectors', cat = 'catalytic converter', intercooler = 'intercooler', battery = 'battery', alternator = 'alternator', exhaust = 'exhaust system', steering = 'steering rack and tie rods', lights = 'bulbs', flywheel = 'flywheel'}
function M.repairPrice(kind, c, mult)
  local base = M.PRICE[kind]
  if not base then return nil end
  return math.floor(base * (0.3 + 0.7 * (1 - clamp(c, 0, 1))) * (mult or 1) + 0.5)
end

-- the stage of a worn brake disc look from the worse of the disc's and its pads' condition: 0 the car's own, 1 worn, 2 rusty (the limits are MODELLED); none when the worn look is 0
M.DISC_WORN_BELOW, M.DISC_RUSTY_BELOW = 0.6, 0.3
function M.discStage(c, visual)
  if (visual or 0) <= 0 then return 0 end
  return c < M.DISC_RUSTY_BELOW and 2 or (c < M.DISC_WORN_BELOW and 1 or 0)
end
M.lookStage = M.discStage              -- (the suspension, frame and exhaust metal use the same limits)
-- the condition the suspension, frame and exhaust metal look follows: the mean of the car's springs and dampers over its four corners (a corner not in the record is new: the store
-- keeps only parts below new)
M.CORNERS = { 'FL', 'FR', 'RL', 'RR' }
function M.mechCondition(rec)
  local sum = 0
  for _, kind in ipairs({ 'spring', 'damper' }) do
    local t = type(rec) == 'table' and type(rec[kind]) == 'table' and rec[kind] or {}
    for _, corner in ipairs(M.CORNERS) do sum = sum + clamp(tonumber(t[corner]) or 1, 0, 1) end
  end
  return sum / 8
end
-- the condition the engine bay look follows: the engine internals (one record, 'all'); new when not stored
function M.engineCondition(rec)
  local t = type(rec) == 'table' and type(rec.engine) == 'table' and rec.engine or {}
  return clamp(tonumber(t.all) or 1, 0, 1)
end

-- 'Good' >= 75 %, 'Worn' 50-75, 'Bad' 25-50, 'Failing' < 25
function M.stage(c)
  return c >= 0.75 and 'Good' or (c >= 0.5 and 'Worn' or (c >= 0.25 and 'Bad' or 'Failing'))
end

-- the wear the effects see: w times the strength, at most 1 (strength 0 = no effect at all)
local function eff(c, s) return clamp((1 - clamp(c, 0, 1)) * (s and s.effectStrength or 1), 0, 1) end
M.effectiveWear = eff

-- condition after `inp` = {km, days, events = {name = count}} on a part of `kind`. Never rises; 0 at the lowest.
function M.wearStep(kind, c, inp, s)
  local k = M.KINDS[kind]
  if not k or not s.wearEnabled then return c end
  local life, lost = (k.life or 0) * s.lifeScale, 0
  if life > 0 then
    lost = lost + math.max(0, inp.km or 0) / life   -- (a negative reading, an odometer reset, never repairs)
    for name, n in pairs(inp.events or {}) do
      local extra = (M.ABUSE_KM[kind] or {})[name]
      if extra then lost = lost + math.max(0, n) * extra * s.abuseScale / life end
    end
  end
  if k.days then lost = lost + math.max(0, inp.days or 0) * s.ageScale / k.days end
  return clamp(c - lost * (s.wearRate or 1), 0, 1)     -- wearRate: the career's own 'how often services are needed' on top of the player's wear speed (1 = as set)
end

-- which of the shared events a part counts, under the names of M.ABUSE_KM: ev = {hardstop, landing, hotF_s, hotR_s (seconds with the front / rear brakes hot), overheat_s, limiter_s}
function M.eventsFor(kind, corner, ev)
  ev = ev or {}
  if kind == 'padF' then return {hardstop = ev.hardstop, hot_s = ev.hotF_s} end
  if kind == 'padR' then return {hardstop = ev.hardstop, hot_s = ev.hotR_s} end
  if kind == 'rotor' then return {hardstop = ev.hardstop, hot_s = (tostring(corner):sub(1, 1) == 'R') and ev.hotR_s or ev.hotF_s} end
  if kind == 'engine' or kind == 'oil' then return {overheat_s = ev.overheat_s, limiter_s = ev.limiter_s} end
  if kind == 'turbo' then return {overheat_s = ev.overheat_s, limiter_s = ev.limiter_s} end
  if kind == 'damper' or kind == 'spring' then return {landing = ev.landing} end
  return {}
end
M.HOT_C = 350                 -- brake surface temperature above which the pads and discs are counted as hot (the fade onset of the research; the game's own fade starts about here)
M.OVERHEAT_C = 112            -- coolant temperature above which the engine is counted as overheating (Street Legal uses the same)
M.LANDING_G = 30              -- vertical deceleration (m/s^2) after a fall that counts as a hard landing (MODELLED)

-- What a failure does: the part drops to a low condition (the apply layer then gives it its worst effect: a blown shock, grinding brakes, a slipping clutch). The condition is the whole state:
-- it survives a respawn and a save, and only a repair puts the part back. MODELLED levels; the text is shown on screen.
M.FAILURE = {
  damper = {level = 0.05, text = 'A shock absorber has blown'},
  spring = {level = 0.10, text = 'A spring has gone soft'},
  padF = {level = 0.06, text = 'The front brakes have gone soft'},
  padR = {level = 0.06, text = 'The rear brakes have gone soft'},
  clutch = {level = 0.08, text = 'The clutch is slipping'},
  engine = {level = 0.12, text = 'The engine is running rough'},
  gearbox = {level = 0.10, text = 'The gearbox is grinding'}, cv = {level = 0.10, text = 'A driveshaft joint is knocking'},
  turbo = {level = 0.10, text = 'The turbo has lost boost'}, radiator = {level = 0.10, text = 'The radiator is not cooling well'},
  ignition = {level = 0.10, text = 'The engine is misfiring'},
  fuel = {level = 0.08, text = 'The engine is starving for fuel at high load'}, cat = {level = 0.08, text = 'The catalytic converter is blocked'},
  intercooler = {level = 0.10, text = 'The intercooler is leaking boost'}, battery = {level = 0.05, text = 'The battery is nearly flat'},
  alternator = {level = 0.05, text = 'The alternator has stopped charging'}, steering = {level = 0.08, text = 'The steering has gone loose'},
  swaybar = {level = 0.05, text = 'An anti-roll bar link has broken'}, bushing = {level = 0.10, text = 'A control arm bush has worn out'},
  bearing = {level = 0.10, text = 'A wheel bearing is failing'}, fluid = {level = 0.08, text = 'The brake fluid has boiled'}, master = {level = 0.08, text = 'The brake pedal has gone soft'},
}
-- a failure roll for one part over dtHours: the new condition and the text, or nil. Only a part still above its failure level can fail (a failed part stays failed until repaired).
function M.failureStep(kind, c, dtHours, s, rand)
  local f = M.FAILURE[kind]
  if not f or c <= f.level then return nil end
  if M.failureRoll(c, dtHours, s, rand) then return f.level, f.text end
  return nil
end

-- a failure roll for dt hours: below 0.15 a part can fail, hazard per hour failRate * (0.15 - c) / 0.15; rand() in 0..1 is injected for tests
function M.failureRoll(c, dtHours, s, rand)
  if not s.failures or c >= 0.15 then return false end
  return rand() < s.failureRate * (0.15 - c) / 0.15 * dtHours
end

-- The per-part effects. Every factor is on the jbeam value, between its floor and 1.0.
local E = {}
M.EFFECT = E

function E.damper(c, s, st)
  local w = eff(c, s)
  local rebound, comp, fast = 1 - s.damperLossMax * w, 1 - 0.75 * s.damperLossMax * w, 1 - 0.625 * s.damperLossMax * w
  local f = (st and st.leaking and 0.5 or 1) * (1 - 0.25 * clamp(st and st.heat or 0, 0, 1))
  return {rebound = clamp(rebound * f, 0.15, 1), comp = clamp(comp * f, 0.15, 1), fast = clamp(fast * f, 0.15, 1)}
end

-- sag in millimetres of corner drop (the vehicle side turns it into a beam rest-length change via the motion ratio); rate a factor on beamSpring
function E.spring(c, s, st)
  local w = eff(c, s)
  local sag = s.springSagMax * math.sqrt(w) * ((st and st.rear) and 1.3 or 1)
  local rate = 1 - s.springRateLoss * w
  if st and st.broken then sag, rate = sag + 35, math.min(rate, 0.6) end
  return {sagMm = clamp(sag, 0, 60), rate = clamp(rate, 0.6, 1)}
end

function E.swaybar(c, s, st) return {k = clamp((st and st.linkBroken) and 0.2 or (1 - 0.3 * eff(c, s)), 0.2, 1)} end
-- the control arms and links: the rate of their NORMAL beams, a little softer at worst (the alignment is held by the beam's length, which stays; MODELLED, 0.85 is conservative on purpose)
function E.bushing(c, s) local w = eff(c, s) return {k = clamp(1 - 0.15 * w, 0.85, 1), d = clamp(1 - 0.1 * w, 0.9, 1)} end
function E.balljoint(c, s) return {strength = clamp(1 - 0.6 * eff(c, s), 0.4, 1)} end
-- the steering rack and tie rods: play. deadZone is the share of the input swallowed around the centre (6 % at worst), lagS the seconds of slack the input is smoothed over; k and powerCoef are the old
-- stiffness terms, not applied by the apply layer (no game value for a rack's stiffness)
function E.steering(c, s, st)
  local w = eff(c, s)
  return {k = clamp(1 - 0.4 * w, 0.6, 1), powerCoef = (st and st.leaking) and clamp(1 - 0.5 * w, 0.5, 1) or 1, deadZone = 0.06 * w, lagS = 0.08 * w * w}
end
function E.bearing(c, s)
  local w = eff(c, s)
  local t = clamp((0.25 - c) / 0.25, 0, 1)      -- 0 at a quarter of the life, 1 at none: the drag rises from nothing, no step
  return {dragNm = t * (5 + 60 * w * w), humVolume = w * w}   -- (a failing bearing drags; a worn one only hums)
end

local function pads(c, s)
  local w = eff(c, s)
  local grind = c < 0.1 and s.effectStrength > 0   -- metal on metal
  local torque = grind and 0.6 or clamp(1 - s.brakeTorqueLoss * w, 0.6, 1)
  return {torque = torque, squealLow = 0.6 * math.max(0, w - 0.7) / 0.3, grind = grind, glazing = clamp(0.3 * w, 0, 0.3)}
end
E.padF, E.padR = pads, pads
function E.rotor(c, s, st)
  local w = eff(c, s)
  return {massCoef = clamp(1 - 0.15 * w, 0.85, 1), judder = 0.12 * clamp(st and st.dtv or w, 0, 1) * s.judder}
end
function E.caliper(c, s, st)
  if st and st.seized then return {dragNm = 20 + 60 * eff(c, s), torque = 0.7} end
  return {dragNm = 0, torque = 1}
end
-- brake fluid: `water` 0..0.04; the efficiency curve shifts down by 80 * water / 0.03 degrees C
function E.fluid(c, s, st)
  local water = (st and st.water) or (1 - c) * 0.04
  return {curveShiftC = -80 * clamp(water, 0, 0.04) / 0.03 * (s.effectStrength > 0 and 1 or 0), leakTorque = (st and st.leaking) and 0.5 or 1}
end

-- the master cylinder and booster: a weaker pedal, up to a fifth less braking at the pedal (MODELLED)
function E.master(c, s) return {torque = clamp(1 - 0.2 * eff(c, s), 0.8, 1)} end

function E.engine(c, s)
  local w = eff(c, s)
  return {cap = clamp(1 - s.enginePowerLoss * w, 0.7, 1), dynFriction = 1 + 0.5 * w, misfire = 0}      -- (the misfire is the ignition's now: kind 'ignition'; the field stays so old callers read 0)
end
function E.filter(c, s) return {cap = clamp(1 - 0.04 * eff(c, s), 0.96, 1)} end
-- the fuel pump and injectors: a power cap at high load; the intercooler (cars with a turbo or supercharger only): less dense charge air (MODELLED, small on purpose)
function E.fuel(c, s) return {cap = clamp(1 - 0.06 * eff(c, s), 0.94, 1)} end
function E.intercooler(c, s) return {cap = clamp(1 - 0.05 * eff(c, s), 0.95, 1)} end
function E.ignition(c, s) return {misfire = clamp(0.2 * math.max(0, eff(c, s) - 0.6), 0, 0.4)} end
-- the game's own sport-exhaust modes use mufflingOffset -0.25 to 0.2 and gainOffset -2 to 1.5: ours stay inside that
function E.exhaust(c, s) local w = eff(c, s) return {mufflingOffset = -0.2 * w, gainDb = 1.5 * w} end
function E.cat(c, s) return {cap = clamp(1 - 0.3 * math.max(0, eff(c, s) - 0.5), 0.85, 1)} end
function E.mounts(c, s) local w = eff(c, s) return {k = clamp(1 - 0.5 * w, 0.5, 1), d = clamp(1 - 0.3 * w, 0.7, 1)} end
function E.clutch(c, s) local w = eff(c, s) return {lockTorque = clamp(1 - 0.55 * w, 0.45, 1), freePlay = 1 + 6 * w} end
-- the powertrain parts write the game's own wear fields of their device (the game's range at a million km: gearbox friction x2, shift rate x0.2, DCT lock x0.7, shaft friction x1.5, turbo power x0.2,
-- friction x20; ours stay well inside it; MODELLED, none is proven in the game)
function E.gearbox(c, s) local w = eff(c, s) return {friction = 1 + w, shiftRate = clamp(1 - 0.5 * w, 0.5, 1), lockTorque = clamp(1 - 0.3 * w, 0.7, 1)} end   -- shiftRate: automatic and CVT; lockTorque: DCT
function E.diff(c, s) return {friction = 1 + eff(c, s)} end
function E.cv(c, s) return {friction = 1 + 0.5 * eff(c, s)} end
function E.turbo(c, s) local w = eff(c, s) return {power = clamp(1 - 0.4 * w, 0.6, 1), friction = 1 + 3 * w} end
-- `integrity` is the game's own 0..1 scale for the radiator (1 new): radiator damage 0.1 * (1 - integrity) and the coolant mass down to 10 % at 0. The game turns any radiator damage above 0.015 into a coolant
-- LEAK that drains the engine dry, so the worst here is 0.86 (damage 0.014, no leak; 87 % of the coolant): the effect is a little less cooling reserve, never a leak
M.RADIATOR_WORST = 0.86
function E.radiator(c, s) return {integrity = clamp(1 - (1 - M.RADIATOR_WORST) * eff(c, s), M.RADIATOR_WORST, 1)} end
function E.oil(c, s) return {dynFriction = 1 + 0.15 * eff(c, s)} end
-- the paint wear look: four layers 0..1 for the paint canvas of Car Surface FX (carSurfaceFx.setPaintWear); they follow the visualWear setting, not effectStrength.
-- fade grows with wear, grime with it more slowly, scuffs a little later, rust only from 40 % worn (MODELLED shapes: no source gives these curves)
function E.paint(c, s)
  local w, v = 1 - clamp(c, 0, 1), clamp(s.visualWear or 0, 0, 1)
  return {fade = clamp(w * v, 0, 1), grime = clamp(0.6 * w * v, 0, 1), scuffs = clamp(0.8 * w ^ 1.2 * v, 0, 1), rust = clamp(math.max(0, (w - 0.4) / 0.6) ^ 1.5 * v, 0, 1)}
end
function E.battery(c, s) return {crank = clamp(1 - 0.4 * eff(c, s), 0.6, 1)} end
function E.alternator(c, s) return {charge = clamp(1 - eff(c, s), 0.15, 1)} end   -- (a dead alternator still charges a little: no stranding)
-- the bulbs: the brightness of every bulb's filament value (down to 60 %), and from 70 % worn a flicker (the share of frames a bulb drops to a third)
function E.lights(c, s) local w = eff(c, s) return {brightness = clamp(1 - 0.4 * w, 0.6, 1), flicker = clamp(0.25 * math.max(0, w - 0.7) / 0.3, 0, 0.25)} end
-- the flywheel: a little more rotating mass at worst (MODELLED: no source ties wear to inertia; the game's engine has one inertia value)
function E.flywheel(c, s) return {inertia = 1 + 0.08 * eff(c, s)} end

-- Brake fade. Pad friction holds to an onset temperature, then falls linearly to 40 % less over FADE_SPAN degrees C.
-- Numbers: OEM pads fade from about 350 C; measured pads lost 0.41-0.48 -> 0.25-0.28 mu at 510-573 C (about 40 %). The span and the lower onset of a worn pad are MODELLED, not sourced.
-- Returns a factor on brake torque, 0.6..1; strength 0 or wear off = 1.
-- The game already fades brakes with heat (wheels.lua calculateThermalEfficiency on brakeSurfaceTemperature), so the car must apply wornFade (the EXTRA
-- loss of a worn pad), not this absolute curve, or fade counts twice.
M.FADE_ONSET, M.FADE_SPAN, M.FADE_LOSS = 350, 200, 0.4
function M.brakeFade(tempC, padC, s, shiftC)
  if not s.wearEnabled or s.effectStrength <= 0 then return 1 end
  local onset = M.FADE_ONSET - 50 * eff(padC or 1, s) + (shiftC or 0)   -- (worn pads and rotors carry less heat away: fade starts earlier; old brake fluid boils earlier: shiftC is negative)
  return 1 - M.FADE_LOSS * clamp(((tempC or 0) - onset) / M.FADE_SPAN, 0, 1)
end

function M.wornFade(tempC, padC, s, shiftC) return M.brakeFade(tempC, padC, s, shiftC) / M.brakeFade(tempC, 1, s) end   -- (<= 1; 1 on a new pad)

function M.effects(kind, c, s, st)
  local f = E[kind]
  if not f or not s.wearEnabled then return nil end
  return f(c, s, st)
end

-- ONE power cap for the engine: the smallest of Street Legal's own factor and ours (ours = internals times filter times cat).
function M.torqueCap(slFactor, ...)
  local cap = slFactor or 1
  local ours = 1
  for _, f in ipairs({...}) do ours = ours * f end
  return math.min(cap, ours)
end

-- a value moves toward its target by at most `maxFrac` of the base value per call (no step above 10 % per frame, so no jolt on a spring or damper)
function M.limitStep(prev, target, base, maxFrac)
  local m = (maxFrac or 0.10) * math.abs(base or 1)
  return prev + clamp(target - prev, -m, m)
end

-- Which wear kinds a parts slot holds, from the slot's name across the stock cars (the game's slots are per axle, not per corner): the slot "vivace_shock_R_wide" is the rear shock absorbers,
-- "covet_coilover_F" the front shock absorbers and springs together, "brakepad_F" the front pads, "etk800_brake_F" the front discs, "*_engine" and "*_engine_internals*" the engine,
-- "*_flywheel" the clutch (the clutch kit is sold and fitted with the flywheel: MODELLED). Returns a list of { kind =, corners = { ... } }, empty for a slot that holds no wear item.
local NOT_WEAR = { strutbrace = true, strutbar = true, bar = true, towerbar = true, cover = true, covers = true, handbrake = true, pedalbox = true, mount = true, mounts = true,
                   ecu = true, intake = true, bay = true, light = true, lights = true, airbox = true, downpipe = true, power = true }      -- whole words of the slot name (split at '_'): a slot like "..._flywheel_lightweight" is not dropped
local AXLE = { F = 'F', IFS = 'F', SFA = 'F', R = 'R', RR = 'R', RL = 'R', RRL = 'R', RRR = 'R' }     -- the slot name's axle word
function M.slotWear(slot)
  slot = tostring(slot or '')
  local low = slot:lower()
  for word in low:gmatch('[^_]+') do if NOT_WEAR[word] then return {} end end
  local function axle(word) local t = slot:match(word .. '_(%u+)') return t and AXLE[t] end
  local function corners(a) return a == 'F' and { 'FL', 'FR' } or { 'RL', 'RR' } end
  local out = {}
  if low:find('coilover', 1, true) or low:find('strut', 1, true) then
    local a = axle(low:find('coilover', 1, true) and 'coilover' or 'strut')
    if a then out[#out + 1] = { kind = 'damper', corners = corners(a) } out[#out + 1] = { kind = 'spring', corners = corners(a) } end
  elseif low:find('shock', 1, true) then
    local a = axle('shock')
    if a then out[#out + 1] = { kind = 'damper', corners = corners(a) } end
  elseif low:find('spring', 1, true) then
    local a = axle('spring')
    if a then out[#out + 1] = { kind = 'spring', corners = corners(a) } end
  elseif low:find('brakepad', 1, true) then
    local a = axle('brakepad')
    if a then out[#out + 1] = { kind = a == 'F' and 'padF' or 'padR', corners = { a } } end
  elseif slot:find('_brakes?_%u') then
    local a = axle('brakes?')
    if a then out[#out + 1] = { kind = 'rotor', corners = corners(a) } end
  elseif low:find('_engine$') or low:find('_engine_alt$') or low:find('_engine_midengine$') or low:find('engine_.-internals') or low:find('_engine_internals') then
    out[#out + 1] = { kind = 'engine', corners = { 'all' } }
  elseif low:find('_flywheel') then
    out[#out + 1] = { kind = 'clutch', corners = { 'all' } }
    out[#out + 1] = { kind = 'flywheel', corners = { 'all' } }
  elseif low:find('transmission', 1, true) then
    out[#out + 1] = { kind = 'gearbox', corners = { 'all' } }
  elseif low:find('_differential', 1, true) then
    local a = axle('differential')
    out[#out + 1] = { kind = 'diff', corners = { a or 'all' } }                      -- (a mid-engine or single diff, no axle letter: the one for the car)
  elseif low:find('driveshaft', 1, true) or low:find('halfshaft', 1, true) then       -- driveshafts and halfshafts, "..._halfshafts_R", "vivace_driveshaft"
    local a = axle(low:find('halfshaft', 1, true) and 'halfshafts?' or 'driveshaft')
    out[#out + 1] = { kind = 'cv', corners = a and { a } or { 'F', 'R' } }
  elseif low:find('_radiator', 1, true) then
    out[#out + 1] = { kind = 'radiator', corners = { 'all' } }
  elseif low:find('exhaust', 1, true) and not low:find('tip', 1, true) and not low:find('exit', 1, true) or low:find('muffler', 1, true) then   -- the catalytic converter is part of the exhaust fitted with it
    out[#out + 1] = { kind = 'cat', corners = { 'all' } }
    out[#out + 1] = { kind = 'exhaust', corners = { 'all' } }
  elseif low:find('fueltank', 1, true) or low:find('fuelcell', 1, true) then            -- the fuel pump sits in the tank
    out[#out + 1] = { kind = 'fuel', corners = { 'all' } }
  elseif low:find('_steering', 1, true) then                                           -- the steering rack ("covet_steering"; the power steering pump has the word power)
    out[#out + 1] = { kind = 'steering', corners = { 'all' } }
  elseif low:find('bulb', 1, true) then
    out[#out + 1] = { kind = 'lights', corners = { 'all' } }
  elseif low:find('swaybar', 1, true) then
    local a = axle('swaybar')
    if a then out[#out + 1] = { kind = 'swaybar', corners = { a } } end
  elseif low:find('_hub_', 1, true) then                                             -- the hub carries the wheel bearing; "covet_3wheel_hub_gears" has no axle letter
    local a = axle('hub')
    if a then out[#out + 1] = { kind = 'bearing', corners = corners(a) } end
  elseif low:find('_turbo_', 1, true) and not low:find('exhaust', 1, true) then       -- the turbo unit ("vivace_turbo_i4_1.5_diesel"); airbox and downpipe are pipes, "exhaust_turbo" is an exhaust
    out[#out + 1] = { kind = 'turbo', corners = { 'all' } }
  end
  return out
end

return M
