-- slrrWear: the vehicle side of part wear. Holds each part's condition (0..1, 1 = new), wears it by distance and hard stops, hands changes to the apply
-- layer (slrrWearProbe: the springs, dampers, brakes, engine, clutch) and reports the state to the game side (slrrWear.onReport) every few seconds.
-- OFF until settings arrive with wearEnabled = true (setSettings): no wear, nothing applied, the car is the jbeam car.
--   slrrWear.setSettings(tbl)              a full settings table (rules.settings shape); wearEnabled false puts every jbeam value back
--   slrrWear.setCondition(kind, corner, c) / getCondition(kind, corner)
--   slrrWear.snapshot() / restoreSnapshot(blob)   JSON-safe {kind = {corner = c}}, only parts below 0.995; the keys may be strings after a round trip
local M = {}
local rules = require('slrrWearRules')

-- the parts of the store and the corners each has ('F' / 'R' = an axle, 'all' = one for the car)
local CORNERS = {
  damper = {'FL', 'FR', 'RL', 'RR'}, spring = {'FL', 'FR', 'RL', 'RR'}, rotor = {'FL', 'FR', 'RL', 'RR'},
  padF = {'F'}, padR = {'R'}, engine = {'all'}, filter = {'all'}, clutch = {'all'}, paint = {'all'},
  gearbox = {'all'}, diff = {'F', 'R', 'all'}, cv = {'F', 'R'}, turbo = {'all'}, radiator = {'all'}, ignition = {'all'}, oil = {'all'},
  fuel = {'all'}, cat = {'all'}, intercooler = {'all'}, battery = {'all'}, steering = {'all'}, body = {'all'}, glass = {'all'}, wipers = {'all'}, door = {'FL', 'FR', 'RL', 'RR', 'T'}, seat = {'all'}, flywheel = {'all'}, lights = {'all'}, alternator = {'all'}, exhaust = {'all'},
  swaybar = {'F', 'R'}, bushing = {'FL', 'FR', 'RL', 'RR'}, bearing = {'FL', 'FR', 'RL', 'RR'}, fluid = {'F', 'R'}, master = {'all'},   -- paint: no apply here, the game side draws it
}
local TICK, REPORT, CHANGE, HARD_STOP, HARD_FROM = 0.5, 5, 0.01, 7, 15   -- s, s, smallest change handed on, m/s^2, m/s

local settings = rules.settings('Off')
local cond = {}            -- cond[kind][corner] = c
local given = {}           -- the c last handed to the apply layer, same shape
local active = false
local timer, report, dirty, pending = 0, 0, false, 0
local lastV, braking = 0, false
local lastVz, landCool, acc = nil, 0, {}   -- the vertical speed of the last frame, the quiet time after a landing, the seconds and events collected since the last tick
local axles = nil                          -- wheel index -> 'F' / 'R' by where the wheel's node is on the car (jbeam y grows backward)
local rand = math.random
function M.setRandom(f) rand = f end
-- random mechanical failures (slrrFailRules, docs/FAILURES.md): the rules decide, this file measures and applies. Without the rules file nothing here runs and the old failure roll stays.
local okF, F = pcall(require, 'slrrFailRules')
local failSt = okF and F.newState() or nil
local racing = false                 -- set by Street Legal while a race, job or chase is on (settings.failureNeverRacing)
function M.setRacing(b) racing = b == true end
local COVERED = {}                   -- the kinds the failure rules know
if okF then for _, r in pairs(F.RULES) do for _, k in ipairs(r.kinds) do COVERED[k] = true end end end
local GROUP_SETTING = { engine = 'failEngine', drive = 'failDrive', electrics = 'failElectrics' }
-- A kind's breakdowns belong to the random failures only while one of its rules' groups is switched on; with the group off (the default) the 0.1.2 threshold breakdown ("Parts can break")
-- stays as it was, so an upgrade loses nothing.
local function ownedByRules(kind)
  if not (failSt and COVERED[kind]) then return false end
  for _, r in pairs(F.RULES) do
    if settings[GROUP_SETTING[r.group] or ''] == true then
      for _, k in ipairs(r.kinds) do if k == kind then return true end end
    end
  end
  return false
end

local function say(m) log('I', 'slrrWear', m) end
local function layer() return rawget(_G, 'slrrWearProbe') end
local function look() return rawget(_G, 'slrrWearLook') end

local function finite(x, d) x = tonumber(x) if x == nil or x ~= x or x == math.huge or x == -math.huge then return d end return x end   -- no NaN or inf in a condition, a snapshot or a report

local function get(kind, corner) return (cond[kind] and cond[kind][corner]) or 1 end
function M.getCondition(kind, corner) return get(kind, corner or CORNERS[kind] and CORNERS[kind][1]) end
function M.setCondition(kind, corner, c)
  if not CORNERS[kind] then return false end
  cond[kind] = cond[kind] or {}
  -- no corner: every corner of the kind
  for _, k in ipairs(corner ~= nil and { corner } or CORNERS[kind]) do cond[kind][k] = rules.clamp(finite(c, 1), 0, 1) end
  dirty = true
  return true
end

-- hand the changed parts to the apply layer (each call is by condition; the layer steps the values in and reapplies after a reset)
local function push(force)
  local P = layer()
  if not (P and active) then return end
  for kind, corners in pairs(CORNERS) do
    for _, corner in ipairs(corners) do
      local c = get(kind, corner)
      given[kind] = given[kind] or {}
      if force or math.abs((given[kind][corner] or 1) - c) >= CHANGE then
        given[kind][corner] = c
        local ok
        if kind == 'damper' or kind == 'spring' or kind == 'rotor' then ok = P[kind] and pcall(P[kind], corner, c)
        elseif kind == 'padF' or kind == 'padR' then ok = pcall(P.pads, corner, c)
        elseif kind == 'engine' then ok = pcall(P.engine, c, get('filter', 'all'))
        elseif kind == 'clutch' then ok = P.clutch and pcall(P.clutch, c)
        elseif kind == 'diff' or kind == 'door' or kind == 'cv' or kind == 'swaybar' or kind == 'bushing' or kind == 'bearing' or kind == 'fluid' then ok = P[kind] and pcall(P[kind], corner, c)
        elseif kind == 'gearbox' or kind == 'turbo' or kind == 'radiator' or kind == 'ignition' or kind == 'oil' or kind == 'master' or kind == 'fuel' or kind == 'cat' or kind == 'intercooler' or kind == 'battery'
            or kind == 'body' or kind == 'glass' or kind == 'seat' or kind == 'steering' or kind == 'flywheel' or kind == 'lights' or kind == 'alternator' or kind == 'exhaust' then ok = P[kind] and pcall(P[kind], c) end
      end
    end
  end
end

function M.setSettings(s)
  settings = rules.settings(nil, s)
  local want = settings.wearEnabled == true
  if want and not active then
    if not layer() then pcall(function() extensions.load('slrrWearProbe') end) end
    if layer() and layer().setSettings then pcall(layer().setSettings, settings) end
    active = layer() ~= nil
    given = {}
    push(true)
    local ok, springs, dampers = pcall(layer().detect)      -- what the apply layer found on this car, in the log: a car with 0 shows up
    say(string.format('on: %s springs, %s dampers found', ok and tostring(springs) or '?', ok and tostring(dampers) or '?'))
  elseif active and not want then
    active, given = false, {}
    if layer() then pcall(layer().clear) end
    if look() then pcall(look().restore) end
    say('off: every jbeam value back')
  elseif active then
    if layer() and layer().setSettings then pcall(layer().setSettings, settings) end
    push(true)
  end
end

function M.snapshot()
  local out = {}
  for kind, t in pairs(cond) do
    for corner, c in pairs(t) do
      if c < 0.995 then out[kind] = out[kind] or {} out[kind][corner] = math.floor(finite(c, 1) * 1000 + 0.5) / 1000 end
    end
  end
  return out
end
function M.restoreSnapshot(blob)
  cond = {}
  for kind, t in pairs(blob or {}) do
    if CORNERS[kind] and type(t) == 'table' then for corner, c in pairs(t) do M.setCondition(kind, tostring(corner), c) end end
  end
  dirty = true
  push(false)
end

local function lit(t)      -- a Lua literal of the snapshot, for the game side
  local parts = {}
  for kind, cs in pairs(t) do
    local inner = {}
    for corner, c in pairs(cs) do inner[#inner + 1] = string.format('[%q]=%s', corner, tostring(c)) end
    parts[#parts + 1] = string.format('[%q]={%s}', kind, table.concat(inner, ','))
  end
  return '{' .. table.concat(parts, ',') .. '}'
end
local function send()
  dirty = false
  if obj and obj.queueGameEngineLua then obj:queueGameEngineLua(string.format('if slrr_partwear then slrr_partwear.onReport(%d, %s) end', obj:getId(), lit(M.snapshot()))) end
end

-- one wear step for every part from the distance and the events since the last one
local function announce(text)
  if guihooks and guihooks.message then pcall(guihooks.message, text, 6, 'slrrWear') end
  say(text)
end
local function wear(km, ev, dt)
  for kind, corners in pairs(CORNERS) do
    for _, corner in ipairs(corners) do
      local c = get(kind, corner)
      local n = rules.wearStep(kind, c, {km = km, events = rules.eventsFor(kind, corner, ev)}, settings)
      if n < c then cond[kind] = cond[kind] or {} cond[kind][corner] = n dirty = true c = n end
      local lvl, text
      if not ownedByRules(kind) then lvl, text = rules.failureStep(kind, c, dt / 3600, settings, rand) end      -- a badly worn part can fail (only with the breakdowns setting on)
      if lvl then cond[kind] = cond[kind] or {} cond[kind][corner] = lvl dirty = true announce(text) end
    end
  end
end

-- every frame: a hard landing is a big upward deceleration just after a fall
local function sample(dt)
  landCool = math.max(0, landCool - dt)
  local vel = obj and obj.getVelocity and obj:getVelocity()
  local vz = vel and finite(vel.z, nil)
  if vz and lastVz and dt > 0 then
    if lastVz < -2 and (vz - lastVz) / dt > rules.LANDING_G and landCool == 0 then acc.landing = (acc.landing or 0) + 1 landCool = 1 end
  end
  lastVz = vz
end
-- every tick: the seconds the brakes, the engine and the rev limiter spent over their limits
local function heat(ev, dt)
  if not (axles and next(axles)) then
    axles = {}
    local ys, n = 0, 0
    for i, w in pairs(wheels and wheels.wheels or {}) do local nd = v and v.data.nodes[w.node1] if nd and nd.pos then ys, n = ys + nd.pos.y, n + 1 end end
    for i, w in pairs(wheels and wheels.wheels or {}) do local nd = v and v.data.nodes[w.node1] axles[i] = (nd and nd.pos and n > 0 and nd.pos.y < ys / n) and 'F' or 'R' end
  end
  for i, w in pairs(wheels and wheels.wheels or {}) do
    if finite(w.brakeSurfaceTemperature, 0) > rules.HOT_C then local k = axles[i] == 'F' and 'hotF_s' or 'hotR_s' ev[k] = dt end
  end
  local el = electrics and electrics.values or {}
  if finite(el.watertemp, 0) > rules.OVERHEAT_C then ev.overheat_s = dt end
  local eng = powertrain and powertrain.getDevice and powertrain.getDevice('mainEngine')      -- the limiter flag is on the engine device, not in electrics
  if eng and eng.revLimiterActive == true then ev.limiter_s = dt end
end

-- what a failure does in the game: each call guarded, since none has been seen in a running game yet. A call that is missing on this car leaves the failure as a message only.
local function mainEngine() return powertrain and powertrain.getDevice and powertrain.getDevice('mainEngine') end
local function flag(eng, name) local th = eng and eng.thermals if th and th.setPartConditionThermals then pcall(th.setPartConditionThermals, 0, {[name] = true}, true) end end
local function breakOne(match)
  local list = {}
  for _, d in pairs(powertrain and powertrain.getDevices and powertrain.getDevices() or {}) do
    if type(d.type) == 'string' and d.type:find(match) and d.onBreak and not d.isBroken then list[#list + 1] = d end
  end
  local d = list[#list > 0 and math.max(1, math.floor(rand() * #list) + 1) or 1]
  if d then pcall(d.onBreak, d) else say('failure: no device of type ' .. match .. ' on this car to break') end
end
local function applyFailure(r)
  if r.game == 'thermals' then flag(mainEngine(), r.flag)
  elseif r.game == 'lockUp' then
    local eng = mainEngine()
    if eng and eng.lockUp then pcall(eng.lockUp, eng) end
    flag(eng, r.flag or 'connectingRodBearingsDamaged')
  elseif r.game == 'onBreak' then breakOne(r.device == 'differential' and 'differential' or (r.device == 'gearbox' and 'earbox' or 'shaft')) end
  if r.drop and CORNERS[r.drop] then
    for _, corner in ipairs(CORNERS[r.drop]) do if get(r.drop, corner) > r.level then cond[r.drop] = cond[r.drop] or {} cond[r.drop][corner] = r.level dirty = true end end
  end
end
local function handleFailures(events)      -- what the rules answered: say it, apply it, tell the game side
  for _, e in ipairs(events) do
    if e.event == 'warn' then announce(e.text)
    elseif e.event == 'cancel' then announce('The noise has stopped')
    elseif e.event == 'fail' then
      announce(e.text)
      if e.result then applyFailure(e.result) end
      if obj and obj.queueGameEngineLua then obj:queueGameEngineLua(string.format('extensions.hook("onSlrrPartWearFailure", %d, %q, %q)', obj:getId(), tostring(e.kind or e.id), tostring(e.how or e.id))) end
    end
  end
end
local landLog, failClock = {}, 0      -- the times of the hard landings of the last minute (the rules' stress input); launches and clutch slip are not measured, so they stay nil
local function failTick(dt, speed, ev)
  failClock = failClock + dt
  for _ = 1, ev.landing or 0 do landLog[#landLog + 1] = failClock end
  while landLog[1] and landLog[1] < failClock - 60 do table.remove(landLog, 1) end
  local el = electrics and electrics.values or {}
  local conds = {}
  for kind in pairs(COVERED) do
    local low = 1
    for _, corner in ipairs(CORNERS[kind] or {}) do low = math.min(low, get(kind, corner)) end
    conds[kind] = low
  end
  for id in pairs(F.RULES) do if F.conditionOf(id, conds) >= F.WEAR_START then F.clearFailed(failSt, id) end end      -- repaired: it can fail again
  local eng = mainEngine()
  local maxRpm = eng and finite(eng.maxRPM, 0) or 0
  local inputs = { oil = conds.oil, overheatS = ev.overheat_s, limiterS = ev.limiter_s, lowFuel = finite(el.fuel, 1) < 0.05, landings = #landLog,
                   rpmFrac = maxRpm > 0 and finite(el.rpm, 0) / maxRpm or nil, coolantC = (el.watertemp ~= nil) and finite(el.watertemp, nil) or nil }
  local running = finite(el.rpm, 0) > 50
  local pi = rawget(_G, 'playerInfo')
  local seated = pi == nil or pi.anyPlayerSeated == true      -- (no playerInfo: a test) a car nobody sits in never rolls: a parked car with the engine on, or a towed one
  local ctx = { driving = seated and running and speed > 1, stopped = (not running) and speed < 0.5, racing = racing }
  handleFailures(F.tick(failSt, conds, inputs, dt, settings, rand, ctx))
end
function M.forceFailure(id)      -- A CONSOLE CALL FOR A TESTER ON A THROWAWAY CAR: never wire it to a button or another mod. It starts the rule's warning now (or the failure at once when it has no warning), whatever the groups' switches say
  if not (failSt and F.RULES[id] and active) then return false end
  local ev = F.force(failSt, id, settings)
  handleFailures(ev)
  return #ev > 0
end

local function tick(dt)
  if pending > 0 then pending = pending - 1 if pending == 0 then push(true) end end      -- a few frames after a reset (the apply layer reapplies on its own after two): hand every part over again, whatever the order
  timer, report = timer + dt, report + dt
  sample(dt)
  if timer >= TICK then
    local speed = math.abs(finite(electrics and electrics.values and electrics.values.wheelspeed, 0))
    local events = acc
    acc = {}
    heat(events, timer)
    local decel = (lastV - speed) / timer
    if decel > HARD_STOP and lastV > HARD_FROM then if not braking then events.hardstop = 1 end braking = true elseif decel < 3 then braking = false end
    wear(speed * timer / 1000, events, timer)
    if failSt then local ok, err = pcall(failTick, timer, speed, events) if not ok then say('failures: ' .. tostring(err)) end end
    lastV, timer = speed, 0
    push(false)
    if look() then pcall(look().update, get, settings) end      -- the worn disc look: nothing happens in a car spawned without the glowMap entry
  end
  if dirty and report >= REPORT then report = 0 send() end
end
function M.updateGFX(dt)              -- our code never gets to disable the vehicle: one error switches part wear off for this car, logged once
  if not active then return end
  local ok, err = pcall(tick, finite(dt, 0))
  if not ok then
    active, given = false, {}
    if layer() then pcall(layer().clear) end
    say('switched off after an error: ' .. tostring(err))
  end
end

function M.status()
  local t = {}
  for kind, cs in pairs(M.snapshot()) do for corner, c in pairs(cs) do t[#t + 1] = string.format('%s %s %.3f', kind, corner, c) end end
  table.sort(t)
  return string.format('wear %s, %d parts below new: %s', active and 'on' or 'off', #t, table.concat(t, ', '))
end

function M.onReset() lastV, braking, pending, lastVz, acc, landCool = 0, false, 3, nil, {}, 0 end      -- no false landing from the speed before the reset, and no events carried over
function M.onExtensionUnloaded() if active and layer() then pcall(layer().clear) end if look() and look().drop then pcall(look().drop) end end      -- (no material writes at a teardown)

return M
