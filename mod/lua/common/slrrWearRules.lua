-- slrrWearRules: the pure rules of part wear. No game calls: the vehicle extension (slrrWear) and the garage side read the same numbers from here,
-- and tools/test_wear_rules.py checks them offline.
-- A part has a condition c, 0..1 (1 = new; the player sees it as a percentage) and a wear w = 1 - c. Condition never rises except by repair.
-- Effects are FACTORS on the car's own jbeam value (never above 1.0: raising a spring or damper above its jbeam value can blow up light nodes) or
-- small absolute amounts (sag in mm, drag in Nm); the vehicle side applies them from the jbeam base value, never to the current value.
-- Source of the numbers: docs/PART_WEAR_RESEARCH.md (the Graph repo), sections 4.2, 4.3 and 6.
local M = {}

local function clamp(x, a, b) return x < a and a or (x > b and b or x) end
M.clamp = clamp

-- real kilometres of normal use at lifeScale 1; `days` for the parts that age by the calendar (the game's day rate decides what a day is)
M.KINDS = {
  damper = {life = 100000, group = 'suspension'}, spring = {life = 200000, group = 'suspension'}, swaybar = {life = 150000, group = 'suspension'},
  bushing = {life = 150000, group = 'suspension'}, balljoint = {life = 150000, group = 'suspension'}, steering = {life = 180000, group = 'suspension'},
  bearing = {life = 200000, group = 'suspension'},
  padF = {life = 40000, group = 'brakes'}, padR = {life = 80000, group = 'brakes'}, rotor = {life = 80000, group = 'brakes'},
  caliper = {life = 150000, group = 'brakes'}, fluid = {days = 1095, group = 'brakes'},
  engine = {life = 350000, group = 'engine'}, filter = {life = 25000, group = 'engine'}, ignition = {life = 60000, group = 'engine'},
  exhaust = {days = 2920, group = 'engine'}, cat = {life = 200000, group = 'engine'}, radiator = {days = 3650, group = 'engine'},
  mounts = {life = 150000, group = 'drive'}, clutch = {life = 150000, group = 'drive'}, gearbox = {life = 250000, group = 'drive'},
  cv = {life = 200000, group = 'drive'}, diff = {life = 300000, group = 'drive'},
  battery = {days = 1460, group = 'electrics'}, alternator = {life = 200000, group = 'electrics'},
  paint = {life = 300000, days = 4380, group = 'body'},        -- the car's paint as a whole (clearcoat 8-15 years in the research; the split between km and age is MODELLED)
}

-- extra kilometres of wear one event costs, per kind (Street Legal's abuse counters feed these)
M.ABUSE_KM = {
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
M.RANGES = {lifeScale = {0.01, 1}, abuseScale = {0, 3}, ageScale = {0, 3}, effectStrength = {0, 2}, springSagMax = {0, 40}, springRateLoss = {0, 0.2},
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
M.PRICE = {damper = 150, spring = 130, rotor = 140, padF = 90, padR = 70, engine = 2500, filter = 40, clutch = 600, paint = 900}
M.NAME = {damper = 'shock absorber', spring = 'spring', rotor = 'brake disc', padF = 'front brake pads', padR = 'rear brake pads', engine = 'engine internals', filter = 'air filter',
          clutch = 'clutch', paint = 'paint'}
function M.repairPrice(kind, c, mult)
  local base = M.PRICE[kind]
  if not base then return nil end
  return math.floor(base * (0.3 + 0.7 * (1 - clamp(c, 0, 1))) * (mult or 1) + 0.5)
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
  return clamp(c - lost, 0, 1)
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
function E.bushing(c, s) local w = eff(c, s) return {k = clamp(1 - 0.5 * w, 0.5, 1), d = clamp(1 - 0.3 * w, 0.7, 1)} end
function E.balljoint(c, s) return {strength = clamp(1 - 0.6 * eff(c, s), 0.4, 1)} end
function E.steering(c, s, st)
  local w = eff(c, s)
  return {k = clamp(1 - 0.4 * w, 0.6, 1), powerCoef = (st and st.leaking) and clamp(1 - 0.5 * w, 0.5, 1) or 1}
end
function E.bearing(c, s)
  local w = eff(c, s)
  return {dragNm = c < 0.25 and 5 + 60 * w * w or 0, humVolume = w * w}   -- (a failing bearing drags; a worn one only hums)
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

function E.engine(c, s)
  local w = eff(c, s)
  return {cap = clamp(1 - s.enginePowerLoss * w, 0.7, 1), dynFriction = 1 + 0.5 * w, misfire = clamp(0.15 * math.max(0, w - 0.5), 0, 0.4)}
end
function E.filter(c, s) return {cap = clamp(1 - 0.04 * eff(c, s), 0.96, 1)} end
function E.ignition(c, s) return {misfire = clamp(0.2 * math.max(0, eff(c, s) - 0.6), 0, 0.4)} end
function E.exhaust(c, s) local w = eff(c, s) return {mufflingOffset = -0.3 * w, gainDb = 2 * w} end
function E.cat(c, s) return {cap = clamp(1 - 0.3 * math.max(0, eff(c, s) - 0.5), 0.85, 1)} end
function E.mounts(c, s) local w = eff(c, s) return {k = clamp(1 - 0.5 * w, 0.5, 1), d = clamp(1 - 0.3 * w, 0.7, 1)} end
function E.clutch(c, s) local w = eff(c, s) return {lockTorque = clamp(1 - 0.55 * w, 0.45, 1), freePlay = 1 + 6 * w} end
function E.gearbox(c, s) return {friction = 1 + eff(c, s)} end
function E.diff(c, s) return {friction = 1 + eff(c, s)} end
-- the paint wear look: four layers 0..1 for the paint canvas of Car Surface FX (carSurfaceFx.setPaintWear); they follow the visualWear setting, not effectStrength.
-- fade grows with wear, grime with it more slowly, scuffs a little later, rust only from 40 % worn (MODELLED shapes: no source gives these curves)
function E.paint(c, s)
  local w, v = 1 - clamp(c, 0, 1), clamp(s.visualWear or 0, 0, 1)
  return {fade = clamp(w * v, 0, 1), grime = clamp(0.6 * w * v, 0, 1), scuffs = clamp(0.8 * w ^ 1.2 * v, 0, 1), rust = clamp(math.max(0, (w - 0.4) / 0.6) ^ 1.5 * v, 0, 1)}
end
function E.battery(c, s) return {crank = clamp(1 - 0.4 * eff(c, s), 0.6, 1)} end
function E.alternator(c, s) return {charge = clamp(1 - eff(c, s), 0.15, 1)} end   -- (a dead alternator still charges a little: no stranding)

-- Brake fade (0f, handling side). Pad friction holds to an onset temperature, then falls linearly to 40 % less over FADE_SPAN degrees C.
-- Numbers: OEM pads fade from about 350 C; measured pads lost 0.41-0.48 -> 0.25-0.28 mu at 510-573 C (about 40 %). The span and the lower onset of a worn pad are MODELLED, not sourced.
-- Returns a factor on brake torque, 0.6..1; strength 0 or wear off = 1.
-- The game already fades brakes with heat (wheels.lua calculateThermalEfficiency on brakeSurfaceTemperature), so the car must apply wornFade (the EXTRA
-- loss of a worn pad), not this absolute curve, or fade counts twice.
M.FADE_ONSET, M.FADE_SPAN, M.FADE_LOSS = 350, 200, 0.4
function M.brakeFade(tempC, padC, s)
  if not s.wearEnabled or s.effectStrength <= 0 then return 1 end
  local onset = M.FADE_ONSET - 50 * eff(padC or 1, s)   -- (worn pads and rotors carry less heat away: fade starts earlier)
  return 1 - M.FADE_LOSS * clamp(((tempC or 0) - onset) / M.FADE_SPAN, 0, 1)
end

function M.wornFade(tempC, padC, s) return M.brakeFade(tempC, padC, s) / M.brakeFade(tempC, 1, s) end   -- (<= 1; 1 on a new pad)

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

return M
