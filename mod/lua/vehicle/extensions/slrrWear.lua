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
  padF = {'F'}, padR = {'R'}, engine = {'all'}, filter = {'all'}, clutch = {'all'}, paint = {'all'},   -- paint: no apply here, the game side draws it
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

local function say(m) log('I', 'slrrWear', m) end
local function layer() return rawget(_G, 'slrrWearProbe') end
local function look() return rawget(_G, 'slrrWearLook') end

local function finite(x, d) x = tonumber(x) if x == nil or x ~= x or x == math.huge or x == -math.huge then return d end return x end   -- no NaN or inf in a condition, a snapshot or a report

local function get(kind, corner) return (cond[kind] and cond[kind][corner]) or 1 end
function M.getCondition(kind, corner) return get(kind, corner or CORNERS[kind] and CORNERS[kind][1]) end
function M.setCondition(kind, corner, c)
  if not CORNERS[kind] then return false end
  cond[kind] = cond[kind] or {}
  cond[kind][corner] = rules.clamp(finite(c, 1), 0, 1)
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
        elseif kind == 'clutch' then ok = P.clutch and pcall(P.clutch, c) end
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
      local lvl, text = rules.failureStep(kind, c, dt / 3600, settings, rand)      -- a badly worn part can fail (only with the breakdowns setting on)
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
