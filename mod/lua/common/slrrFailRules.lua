-- slrrFailRules: random mechanical failures as pure rules (docs/FAILURES.md). No game calls: the vehicle extension gathers the inputs, calls tick() once a frame and applies what it returns.
-- A part that is healthy or serviced (condition >= 0.5) has no chance; below that the hazard per minute of driving grows with the square of the wear and with what really kills the part
-- (stress). A roll that succeeds goes "pending" for a warning time (a message; stopping with the engine off cancels it) and then fails. The numbers are MODELLED.
local M = {}

local exp, min, max, floor = math.exp, math.min, math.max, math.floor

local function num(v, d) v = tonumber(v) if v and v == v and v > -math.huge and v < math.huge then return v end return d end
local function clamp(x, a, b) return x < a and a or (x > b and b or x) end

M.WEAR_START = 0.5          -- condition at and above which a part cannot fail
M.STRESS_MIN, M.STRESS_MAX = 0.1, 10
M.CANCEL_S = 10             -- seconds stopped with the engine off that cancel a pending failure
M.COOLDOWN_S = 600          -- a cancelled kind rests this long

-- (wear term) 0 from 0.5 up, squared below: 0.25 -> 0.25, 0.1 -> 0.64, 0 -> 1
function M.wear(c)
  c = clamp(num(c, 1), 0, 1)
  if c >= M.WEAR_START then return 0 end
  local w = (M.WEAR_START - c) / M.WEAR_START
  return w * w
end

-- what the car measures (inputs, all optional): coolantC, coolantLevel 0..1, oil (the oil's condition 0..1), oilLevel 0..1, rpmFrac (rpm / limiter rpm), cold (engine not yet warm),
-- launches (clutch dumps and spikes in the last minute), landings (hard landings in the last minute), slipS (clutch slip seconds in the last minute), lowFuel (bool)
local function overheat(i)
  if i.coolantC == nil and i.overheatS ~= nil then return clamp(1 + max(0, num(i.overheatS, 0)) / 6, 1, 10) end      -- (no temperature: the seconds over the overheat line in the last minute)
  local t = num(i.coolantC, 90)
  if t < 95 then return 0.2 end
  if t <= 100 then return 1 end
  return 1 + (t - 100) / 5
end
local function revving(i) return num(i.rpmFrac, 0) > 0.9 or num(i.limiterS, 0) > 0 end
local STRESS = {
  head_gasket = function(i) return overheat(i) * (num(i.coolantLevel, 1) < 0.5 and 1.5 or 1) end,
  piston_rings = function(i) return 1 + (num(i.oil, 1) < 0.3 and 1 or 0) + (revving(i) and 1 or 0) + (num(i.coolantC, 90) > 110 and 0.5 or 0) end,
  rod_bearings = function(i)
    return 1 + (num(i.oilLevel, 1) < 0.5 and 2 or 0) + (num(i.oil, 1) < 0.3 and 1 or 0) + (revving(i) and 1.5 or 0) + ((i.cold and num(i.rpmFrac, 0) > 0.6) and 1 or 0)
  end,
  axle = function(i) return 1 + 0.5 * max(0, num(i.launches, 0)) + 0.5 * max(0, num(i.landings, 0)) end,
  diff = function(i) return 1 + 0.5 * max(0, num(i.launches, 0)) + 0.3 * max(0, num(i.landings, 0)) + (num(i.oil, 1) < 0.3 and 0.5 or 0) end,
  gearbox = function(i) return 1 + 0.5 * max(0, num(i.launches, 0)) + ((num(i.rpmFrac, 0) > 0.95 or num(i.limiterS, 0) > 0) and 1 or 0) end,
  clutch = function(i) return 1 + 0.5 * max(0, num(i.launches, 0)) + 0.1 * min(20, max(0, num(i.slipS, 0))) end,
  turbo = function(i) return 1 + (num(i.oil, 1) < 0.3 and 1 or 0) + (num(i.coolantC, 90) > 110 and 1 or 0) end,
  fuel_pump = function(i) return 1 + (i.lowFuel and 1 or 0) end,
  alternator = function() return 1 end,
}

-- id -> the rule. kinds: the Part Wear kinds whose lowest condition is the part's; group: the settings group (engine, drive, electrics); base: hazard per minute at wear 1 and stress 1;
-- warn: seconds of warning (0 = sudden); result: what the car side applies, by the game's own function where there is one:
--   every result has `how` (a name for the car side and the hook onSlrrPartWearFailure(vehId, kind, how)): headGasket, rings, seize, shaft, diff, gearbox, or the plain drop's kind name
--   { game = 'thermals', flag = ... } thermals:setPartConditionThermals(odometer, { [flag] = true }, visual) (table form, only the flag: the number form empties a fuel tank and more)
--   { game = 'lockUp' } engine:lockUp() (and the thermals flag 'connectingRodBearingsDamaged'); { game = 'onBreak', device = 'shaft'|'differential'|'gearbox' } device:onBreak()
--   { drop = kind, level } the existing condition drop of rules.FAILURE (a plain failure: the part's worst effect)
M.RULES = {
  head_gasket = { kinds = { 'radiator', 'engine' }, group = 'engine', base = 0.010, warn = 90, result = { game = 'thermals', flag = 'headGasketBlown', how = 'headGasket' },
    warnText = 'The temperature is creeping up: ease off', failText = 'The head gasket has blown' },
  piston_rings = { kinds = { 'engine', 'oil' }, group = 'engine', base = 0.008, warn = 60, result = { game = 'thermals', flag = 'pistonRingsDamaged', how = 'rings' },
    warnText = 'The engine is burning oil and has lost its edge', failText = 'The piston rings are damaged' },
  rod_bearings = { kinds = { 'engine', 'oil' }, group = 'engine', base = 0.006, warn = 40, result = { game = 'lockUp', flag = 'connectingRodBearingsDamaged', how = 'seize' },
    warnText = 'The engine is knocking from the bottom end', failText = 'The bottom end has failed: the engine has seized' },
  axle = { kinds = { 'cv' }, group = 'drive', base = 0.004, warn = 15, result = { game = 'onBreak', device = 'shaft', how = 'shaft' },
    warnText = 'Something is clunking in the driveline', failText = 'A driveshaft has broken' },
  diff = { kinds = { 'diff' }, group = 'drive', base = 0.003, warn = 20, result = { game = 'onBreak', device = 'differential', how = 'diff' },
    warnText = 'The differential is whining', failText = 'The differential has failed' },
  gearbox = { kinds = { 'gearbox' }, group = 'drive', base = 0.003, warn = 30, result = { game = 'onBreak', device = 'gearbox', drop = 'gearbox', level = 0.10, how = 'gearbox' },
    warnText = 'The gearbox is whining and crunching', failText = 'The gearbox has failed' },
  clutch = { kinds = { 'clutch' }, group = 'drive', base = 0.010, warn = 0, result = { how = 'clutch', drop = 'clutch', level = 0.08 }, failText = 'The clutch is slipping' },
  turbo = { kinds = { 'turbo' }, group = 'engine', base = 0.006, warn = 30, result = { how = 'turbo', drop = 'turbo', level = 0.10 },
    warnText = 'The turbo is whistling and smoking', failText = 'The turbo has lost boost' },
  fuel_pump = { kinds = { 'fuel' }, group = 'engine', base = 0.006, warn = 20, result = { how = 'fuel', drop = 'fuel', level = 0.08 },
    warnText = 'The engine is stuttering under load', failText = 'The engine is starving for fuel at high load' },
  alternator = { kinds = { 'alternator' }, group = 'electrics', base = 0.004, warn = 30, result = { how = 'alternator', drop = 'alternator', level = 0.05 },
    warnText = 'The lights are dimming', failText = 'The alternator has stopped charging' },
}
M.ORDER = { 'head_gasket', 'piston_rings', 'rod_bearings', 'axle', 'diff', 'gearbox', 'clutch', 'turbo', 'fuel_pump', 'alternator' }

-- the part's condition for a rule: the lowest of its kinds (conds[kind] = 0..1; a missing kind is new)
function M.conditionOf(id, conds)
  local r = M.RULES[id]
  if not r then return 1 end
  local c = 1
  for _, k in ipairs(r.kinds) do c = min(c, clamp(num(conds and conds[k], 1), 0, 1)) end
  return c
end

function M.stress(id, inputs)
  local f = STRESS[id]
  if not f then return 1 end
  local ok, v = pcall(f, type(inputs) == 'table' and inputs or {})
  return clamp(ok and num(v, 1) or 1, M.STRESS_MIN, M.STRESS_MAX)
end

-- settings: failures (master), failureRate 0..3, failEngine / failDrive / failElectrics (false switches a group off), failureWarnings (false: sudden), failureNeverRacing
local function groupOn(s, group) return s['fail' .. group:sub(1, 1):upper() .. group:sub(2)] ~= false end
local function rateOf(s) return clamp(num(s.failureRate, 1), 0, 3) end

-- hazard per minute of driving for a rule
function M.hazard(id, cond, inputs, s)
  local r = M.RULES[id]
  if not r or type(s) ~= 'table' or not s.failures or not groupOn(s, r.group) then return 0 end
  return r.base * M.wear(cond) * M.stress(id, inputs) * rateOf(s)
end

-- the chance of at least one failure in dtMin minutes at hazard h
function M.chance(h, dtMin) return 1 - exp(-max(0, num(h, 0)) * max(0, num(dtMin, 0))) end
function M.roll(h, dtMin, rand) return rand() < M.chance(h, dtMin) end

-- the minutes to a failure on average at a hazard (math.huge at zero)
function M.expectedMinutes(h) h = num(h, 0) return h > 0 and 1 / h or math.huge end

-- ---- the state: pending warnings, cancel cooldowns, the minute clock of the rolls, what has failed
function M.newState() return { pending = {}, cooldown = {}, acc = 0, failed = {}, stopped = 0 } end

local function failNow(st, id, events)
  st.pending[id], st.failed[id] = nil, true
  events[#events + 1] = { id = id, event = 'fail', text = M.RULES[id].failText, result = M.RULES[id].result, how = M.RULES[id].result.how, kind = M.RULES[id].kinds[1] }
end
local function startPending(st, id, s, events)
  local r = M.RULES[id]
  if r.warn <= 0 or s.failureWarnings == false then failNow(st, id, events) return end
  st.pending[id] = r.warn
  events[#events + 1] = { id = id, event = 'warn', text = r.warnText, seconds = r.warn }
end

-- a part already failed (loaded from the stored conditions) cannot fail again until repaired
function M.markFailed(st, id) st.failed[id] = true end
function M.clearFailed(st, id) st.failed[id] = nil end

-- for 80: make a failure pending now (its warning first) or immediate
function M.force(st, id, s)
  local events = {}
  if not M.RULES[id] or st.failed[id] or st.pending[id] then return events end
  startPending(st, id, s or {}, events)
  return events
end

-- one step of dt seconds. conds: Part Wear kind -> condition; inputs: see above; s: the settings; rand(): 0..1 (injected: the car seeds it);
-- ctx: { driving = engine on and moving, stopped = engine off and not moving, racing = a race/job/chase is on }
-- returns the events: { id, event = 'warn'|'cancel'|'fail', text, result }
function M.tick(st, conds, inputs, dt, s, rand, ctx)
  local events = {}
  dt = clamp(num(dt, 0), 0, 5)
  s = type(s) == 'table' and s or {}
  ctx = type(ctx) == 'table' and ctx or {}
  if not s.failures then st.pending = {} st.acc = 0 return events end
  st.stopped = ctx.stopped and st.stopped + dt or 0
  for id in pairs(st.cooldown) do st.cooldown[id] = st.cooldown[id] - dt if st.cooldown[id] <= 0 then st.cooldown[id] = nil end end
  for _, id in ipairs(M.ORDER) do                       -- the pending warnings run on: they end in a failure, or the player stops
    local left = st.pending[id]
    if left then
      if st.stopped >= M.CANCEL_S then
        st.pending[id] = nil
        st.cooldown[id] = M.COOLDOWN_S
        events[#events + 1] = { id = id, event = 'cancel' }
      else
        st.pending[id] = left - dt
        if st.pending[id] <= 0 then failNow(st, id, events) end
      end
    end
  end
  if ctx.driving and not (ctx.racing and s.failureNeverRacing) then
    st.acc = st.acc + dt
    while st.acc >= 60 do                              -- one roll per minute of driving
      st.acc = st.acc - 60
      for _, id in ipairs(M.ORDER) do
        if not st.failed[id] and not st.pending[id] and not st.cooldown[id] then
          local h = M.hazard(id, M.conditionOf(id, conds), inputs, s)
          if h > 0 and M.roll(h, 1, rand) then startPending(st, id, s, events) end
        end
      end
    end
  end
  return events
end

-- the hazard of every rule now, for the debug list
function M.report(conds, inputs, s)
  local out = {}
  for _, id in ipairs(M.ORDER) do
    local c = M.conditionOf(id, conds)
    out[#out + 1] = { id = id, condition = c, wear = M.wear(c), stress = M.stress(id, inputs), perMinute = M.hazard(id, c, inputs, s) }
  end
  return out
end

return M
