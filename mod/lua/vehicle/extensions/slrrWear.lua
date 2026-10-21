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
  padF = {'F'}, padR = {'R'}, engine = {'all'}, filter = {'all'}, clutch = {'all'},
}
local TICK, REPORT, CHANGE, HARD_STOP, HARD_FROM = 0.5, 5, 0.01, 7, 15   -- s, s, smallest change handed on, m/s^2, m/s

local settings = rules.settings('Off')
local cond = {}            -- cond[kind][corner] = c
local given = {}           -- the c last handed to the apply layer, same shape
local active = false
local timer, report, dirty = 0, 0, false
local lastV, braking = 0, false

local function say(m) log('I', 'slrrWear', m) end
local function layer() return rawget(_G, 'slrrWearProbe') end

local function get(kind, corner) return (cond[kind] and cond[kind][corner]) or 1 end
function M.getCondition(kind, corner) return get(kind, corner or CORNERS[kind] and CORNERS[kind][1]) end
function M.setCondition(kind, corner, c)
  if not CORNERS[kind] then return false end
  cond[kind] = cond[kind] or {}
  cond[kind][corner] = rules.clamp(tonumber(c) or 1, 0, 1)
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
    say('on')
  elseif active and not want then
    active, given = false, {}
    if layer() then pcall(layer().clear) end
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
      if c < 0.995 then out[kind] = out[kind] or {} out[kind][corner] = math.floor(c * 1000 + 0.5) / 1000 end
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
  if obj and obj.queueGameEngineLua then obj:queueGameEngineLua(string.format('if slrrWear then slrrWear.onReport(%d, %s) end', obj:getId(), lit(M.snapshot()))) end
end

-- one wear step for every part from the distance and the events since the last one
local function wear(km, events)
  for kind, corners in pairs(CORNERS) do
    for _, corner in ipairs(corners) do
      local c = get(kind, corner)
      local n = rules.wearStep(kind, c, {km = km, events = events}, settings)
      if n < c then cond[kind] = cond[kind] or {} cond[kind][corner] = n dirty = true end
    end
  end
end

function M.updateGFX(dt)
  if not active then return end
  timer, report = timer + dt, report + dt
  if timer >= TICK then
    local speed = math.abs(tonumber(electrics and electrics.values and electrics.values.wheelspeed) or 0)
    local events = {}
    local decel = (lastV - speed) / timer
    if decel > HARD_STOP and lastV > HARD_FROM then if not braking then events.hardstop = 1 end braking = true elseif decel < 3 then braking = false end
    wear(speed * timer / 1000, events)
    lastV, timer = speed, 0
    push(false)
  end
  if dirty and report >= REPORT then report = 0 send() end
end

function M.status()
  local t = {}
  for kind, cs in pairs(M.snapshot()) do for corner, c in pairs(cs) do t[#t + 1] = string.format('%s %s %.3f', kind, corner, c) end end
  table.sort(t)
  return string.format('wear %s, %d parts below new: %s', active and 'on' or 'off', #t, table.concat(t, ', '))
end

function M.onReset() lastV, braking = 0, false end
function M.onExtensionUnloaded() if active and layer() then pcall(layer().clear) end end

return M
