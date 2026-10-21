-- slrrWearProbe: the vehicle-side probe for part wear (see docs/PROBE_STEPS.md). A dev tool, not the
-- final wear extension: it finds the parts on any car, applies ONE part's worn effect from the shared rules (slrrWearRules), steps it in by at most
-- 10 % of the jbeam value per frame, reapplies it a frame after a vehicle reset, and puts every jbeam value back on clear().
--   extensions.load('slrrWearProbe')            (vehicle Lua of the car under test)
--   slrrWearProbe.detect()                      list what it found (log lines 'slrrWearProbe: ...')
--   slrrWearProbe.damper('FL', 0.3)             condition 0.3 on the front-left damper ('F', 'R', 'all' also)
--   slrrWearProbe.spring('FL', 0.3)             sag and a softer rate on that corner's spring
--   slrrWearProbe.pads('F', 0.05)               brake pads of the front axle at 5 %
--   slrrWearProbe.engine(0.2, 0.5)              internals at 20 %, air filter at 50 % (power cap, friction, misfire)
--   slrrWearProbe.gearbox(c) / diff(axle, c) / cv(axle, c) / turbo(c) / radiator(c) / ignition(c) / oil(c)    the powertrain parts (the game's own wear fields of each device)
--   slrrWearProbe.preset('Realistic')           the strength of the effects (Realistic, Light, Off)
--   slrrWearProbe.clear()                       every jbeam value back
--   slrrWearProbe.status()                      what is applied now
local M = {}
local rules = require('slrrWearRules')

local settings = rules.settings('Realistic')
local beams = {}       -- cid -> {kind, corner, part, base = {..}, cur = {..}, target = {..}, rest0}
local applied = {}     -- the effects asked for: {kind, corner, c}, in order, for the reapply after a reset
local brakes = {}      -- wheel index -> {base = {...}, target = {...}}
local engineTarget
local clutchTarget   -- {lock, freePlay} factors from the clutch condition
local gearboxTarget, diffTarget, cvTarget = nil, {}, {}      -- {friction, shiftRate, lockTorque}; axle ('F', 'R', 'all') -> friction
local turboTarget, radiatorTarget, ignitionTarget, oilTarget       -- {power, friction}; the game's radiator integrity; the misfire chance; the engine's dynamic friction factor
local fieldBase = {}       -- device -> field -> the value the game gave it, put back by clear()
local turboBase            -- the turbocharger's own damage state, put back by clear()
local rotorCond = {}   -- corner or axle -> rotor condition (it lowers the fade onset with the pads)
local pending = 0      -- frames until the reapply after a reset
local moving = false

local function say(msg) log('I', 'slrrWearProbe', msg) end

local function cornerOf(node)
  -- the wheel nearest to a node gives its corner: front or rear by y (jbeam y grows backward), left or right by x (jbeam +x is the car's left)
  local best, bestD
  for i, w in pairs(wheels.wheels) do
    local n = v.data.nodes[w.node1]
    if n and n.pos then
      local d = (n.pos.x - node.pos.x) ^ 2 + (n.pos.y - node.pos.y) ^ 2
      if not bestD or d < bestD then best, bestD = n, d end
    end
  end
  if not best then return '?' end
  local ymid, n, sum = 0, 0, 0
  for _, w in pairs(wheels.wheels) do local nd = v.data.nodes[w.node1] if nd and nd.pos then sum, n = sum + nd.pos.y, n + 1 end end
  ymid = n > 0 and sum / n or 0
  return (best.pos.y < ymid and 'F' or 'R') .. (best.pos.x > 0 and 'L' or 'R')
end

-- A suspension beam is told by the part it belongs to: the game's own shape tests alone also catch the door hinges (bounded beams with a spring and a precompression) and the steering
-- (bounded beams with damping), found on the vivace (80, 2026-10-21). Its springs are NORMAL beams with a precompression, named spring_RL in their part path, not bounded beams.
local NOT_SUSPENSION = {'door', 'hood', 'trunk', 'tailgate', 'steering', 'steer', 'seat', 'latch', 'hinge', 'wiper', 'mirror'}
-- the alignment and anti-roll parts: only a NORMAL beam is ever one of them, and they are told by a whole word of the part path ("camber_link", "toe_link"), not a piece of one: the pickup's
-- front is "pickup_coilover_4link_F" (a 4-link axle), a multilink rear is "multilink", and neither is a link beam
local NOT_NORMAL = {link = true, links = true, toe = true, camber = true, arm = true, arms = true, swaybar = true, arb = true}
local function linkPart(path)
  for w in tostring(path or ''):lower():gmatch('[a-z0-9]+') do if NOT_NORMAL[w] then return true end end
  return false
end
local SUSPENSION = {'suspension', 'spring', 'shock', 'strut', 'coilover', 'damper'}
-- a NORMAL beam (the vivace's springs) must also be in a part that says spring or coilover: the alignment links of vivace_suspension_R_wide are NORMAL beams with a spring and a precompression near 1
local function springPart(path)
  local p = tostring(path or ''):lower()
  return p:find('spring', 1, true) ~= nil or p:find('coilover', 1, true) ~= nil
end
local function suspensionPart(path, normal)
  if normal and linkPart(path) then return false end
  local p = tostring(path or ''):lower()
  for _, w in ipairs(NOT_SUSPENSION) do if p:find(w, 1, true) then return false end end
  for _, w in ipairs(SUSPENSION) do if p:find(w, 1, true) then return true end end
  return false
end
M.suspensionPart = suspensionPart

-- every spring and damper of the car, by the game's own tests (partCondition.lua:161 for the damper) and the part they belong to
local function scan()
  beams = {}
  local springs, dampers, stops = 0, 0, 0
  for cid, b in pairs(v.data.beams) do
    if (b.beamType == 2 or (b.beamType == 0 and springPart(b.partPath))) and suspensionPart(b.partPath, b.beamType == 0) then   -- BOUNDED, or NORMAL in a spring part (the vivace's springs)
      local node = v.data.nodes[b.id1]
      if (b.beamSpring or 0) > 0 and (b.beamPrecompression or 1) > 1 then
        springs = springs + 1
        beams[cid] = {kind = 'spring', corner = node and cornerOf(node) or '?', part = b.partPath, base = {b.beamSpring, b.beamDamp or 0}}
      elseif b.beamType == 2 and (b.beamSpring or 0) == 0 and (b.beamDamp or 0) > 0 and b.beamDampRebound and (b.beamDampVelocitySplit or math.huge) < math.huge then
        if (b.beamDampRebound or 0) == 0 then   -- (a bump stop: no rebound damping, a split of about 2)
          stops = stops + 1   -- a bump stop, not a damper
        else
          dampers = dampers + 1
          beams[cid] = {kind = 'damper', corner = node and cornerOf(node) or '?', part = b.partPath,
                        base = {b.beamDamp, b.beamDampRebound, b.beamDampFast or b.beamDamp, b.beamDampReboundFast or b.beamDampRebound, b.beamDampVelocitySplit, b.beamDampVelocitySplitRebound or b.beamDampVelocitySplit}}
        end
      end
    end
  end
  return springs, dampers, stops
end

function M.detect()
  local springs, dampers, stops = scan()
  say(string.format('springs %d, dampers %d, bump stops skipped %d', springs, dampers, stops))
  for cid, r in pairs(beams) do say(string.format('  %s %s beam %d in %s', r.kind, r.corner, cid, tostring(r.part))) end
  local nw = 0
  for i, w in pairs(wheels.wheelRotators or wheels.wheels) do
    nw = nw + 1
    say(string.format('  wheel %s: brakeTorque %.0f, initial %.0f, glazing %s', tostring(w.name or i), w.brakeTorque or -1, w.initialBrakeTorque or -1, tostring(w.padGlazingFactor)))
  end
  local eng = powertrain.getDevice('mainEngine')
  say(string.format('engine %s, torque state %s, clutch %s, tbars %d', tostring(eng and eng.name), tostring(eng and eng.outputTorqueState),
    tostring(powertrain.getDevice('clutch') ~= nil), v.data.torsionbars and #v.data.torsionbars or 0))
  return springs, dampers, nw
end

local function match(corner, c) return corner == 'all' or c == corner or (#corner == 1 and c:sub(1, 1) == corner) end

local function want(kind, corner, cond)
  if not next(beams) then scan() end
  for cid, r in pairs(beams) do
    if r.kind == kind and match(corner, r.corner) then
      r.cur = r.cur or {}
      local state = r.state or {rear = r.corner:sub(1, 1) == 'R'}
      local e = rules.effects(kind, cond, settings, state)
      if e then
        if kind == 'damper' then
          local b = r.base
          r.target = {b[1] * e.comp, b[2] * e.rebound, b[3] * e.fast, b[4] * e.fast, b[5], b[6]}
        else
          r.rest0 = r.rest0 or obj:getBeamRestLength(cid)
          r.target = {r.base[1] * e.rate, r.base[2], r.rest0 - e.sagMm / 1000}   -- motion ratio taken as 1 (a coilover strut stands nearly upright)
        end
        if not r.curv then
          local src = kind == 'damper' and r.base or {r.base[1], r.base[2], r.rest0 or obj:getBeamRestLength(cid)}
          r.curv = {}
          for i = 1, #src do r.curv[i] = src[i] end
        end
        moving = true
      end
    end
  end
end

local function copyOf(t) local o = {} for i, x in ipairs(t) do o[i] = x end return o end
local function remember(kind, corner, cond)
  for i = #applied, 1, -1 do
    if applied[i].kind == kind and applied[i].corner == corner then table.remove(applied, i) end
  end
  applied[#applied + 1] = {kind = kind, corner = corner, c = cond}
end

function M.setSettings(tbl) settings = tbl for _, a in ipairs(copyOf(applied)) do M.reapply(a) end say('settings set') end   -- the full table of rules.settings(..), from the Mods page
function M.preset(name) settings = rules.settings(name) for _, a in ipairs(copyOf(applied)) do M.reapply(a) end say('preset ' .. tostring(name)) end
function M.damper(corner, cond) want('damper', corner, cond) remember('damper', corner, cond) say(string.format('damper %s condition %.2f', corner, cond)) end
function M.spring(corner, cond) want('spring', corner, cond) remember('spring', corner, cond) say(string.format('spring %s condition %.2f', corner, cond)) end

function M.pads(axle, cond)
  local e = rules.effects(axle == 'R' and 'padR' or 'padF', cond, settings)
  if not e then return end
  for i, w in pairs(wheels.wheelRotators or wheels.wheels) do
    local node = v.data.nodes[w.node1]
    local c = node and cornerOf(node) or '?'
    if axle == 'all' or c:sub(1, 1) == axle or c == axle then
      brakes[i] = brakes[i] or {base = {w.initialBrakeTorque or w.brakeTorque, w.padGlazingFactor or 0, w.squealCoefLowSpeed or 0, w.frictionTorque or 0}}
      brakes[i].padC, brakes[i].corner = cond, c
      brakes[i].target = {brakes[i].base[1] * e.torque, math.max(brakes[i].base[2], e.glazing), brakes[i].base[3] + e.squealLow, brakes[i].base[4]}
    end
  end
  remember('pads', axle, cond)
  moving = true
  say(string.format('pads %s condition %.2f: torque x%.2f, squeal +%.2f, grind %s', axle, cond, e.torque, e.squealLow, tostring(e.grind)))
end

-- a worn rotor carries less heat, so the pad's fade starts earlier; the effect itself is applied in step() with the pads
function M.rotor(corner, cond)
  rotorCond[corner] = cond
  remember('rotor', corner, cond)
  say(string.format('rotor %s condition %.2f', corner, cond))
end

-- the clutch device's own wear coefficients (the game sets them from the odometer at spawn; a reset reapplies ours)
function M.clutch(cond)
  local e = rules.effects('clutch', cond, settings)
  if not e then return end
  clutchTarget = {lock = e.lockTorque, freePlay = e.freePlay}
  remember('clutch', 'all', cond)
  say(string.format('clutch condition %.2f: lock torque x%.2f, free play x%.1f', cond, e.lockTorque, e.freePlay))
end

function M.engine(cInternals, cFilter)
  local a, b = rules.effects('engine', cInternals, settings), rules.effects('filter', cFilter or 1, settings)
  if not a then return end
  engineTarget = {cap = rules.torqueCap(1, a.cap, b and b.cap or 1), dyn = a.dynFriction, misfire = a.misfire}
  remember('engine', 'all', cInternals)
  say(string.format('engine: power cap %.3f, dynamic friction x%.2f, misfire %.3f', engineTarget.cap, engineTarget.dyn, engineTarget.misfire))
end

-- ---- the powertrain parts: the game's own wear fields of each device (docs/POWERTRAIN_GAME_VALUES.md). Never device:setPartCondition with a number: on a fuel tank it empties the tank, on the
-- engine it blows the head gasket below 0.3, on a gearbox it can remove a gear. Devices are found by type through powertrain.getOrderedDevices().
local GEARBOXES = {manualGearbox = true, automaticGearbox = true, cvtGearbox = true, dctGearbox = true, sequentialGearbox = true}
local function devices(types)
  local out = {}
  local ok, list = pcall(function() return powertrain.getOrderedDevices() end)
  for _, d in ipairs(ok and list or {}) do if types[d.type] then out[#out + 1] = d end end
  return out
end
-- the axle of a device from its name ("differential_F", "halfshaft_FL", "driveshaftR"): 'F', 'R' or nil (a centre or single one)
local function axleOfDevice(d)
  local a = tostring(d.name or ''):match('[_%l](%u)%u?$')
  return (a == 'F' or a == 'R') and a or nil
end
local function setField(d, field, value)
  if d[field] == nil then return end
  fieldBase[d] = fieldBase[d] or {}
  if fieldBase[d][field] == nil then fieldBase[d][field] = d[field] end
  d[field] = value
end

function M.gearbox(cond)
  local e = rules.effects('gearbox', cond, settings)
  if not e then return end
  gearboxTarget = {friction = e.friction, shiftRate = e.shiftRate, lockTorque = e.lockTorque}
  remember('gearbox', 'all', cond)
  say(string.format('gearbox condition %.2f: friction x%.2f, shift rate x%.2f, DCT lock x%.2f', cond, e.friction, e.shiftRate, e.lockTorque))
end
function M.diff(axle, cond)
  local e = rules.effects('diff', cond, settings)
  if not e then return end
  diffTarget[axle] = e.friction
  remember('diff', axle, cond)
  say(string.format('differential %s condition %.2f: friction x%.2f', axle, cond, e.friction))
end
function M.cv(axle, cond)
  local e = rules.effects('cv', cond, settings)
  if not e then return end
  cvTarget[axle] = e.friction
  remember('cv', axle, cond)
  say(string.format('shafts %s condition %.2f: friction x%.2f', axle, cond, e.friction))
end
function M.ignition(cond)
  local e = rules.effects('ignition', cond, settings)
  if not e then return end
  ignitionTarget = {misfire = e.misfire}
  remember('ignition', 'all', cond)
  say(string.format('ignition condition %.2f: misfire %.3f', cond, e.misfire))
end
function M.oil(cond)
  local e = rules.effects('oil', cond, settings)
  if not e then return end
  oilTarget = {dyn = e.dynFriction}
  remember('oil', 'all', cond)
  say(string.format('oil condition %.2f: engine friction x%.2f', cond, e.dynFriction))
end
-- the turbocharger and the radiator keep the game's damage state inside the module, so they are set through the module's own call, once when the condition changes and again after a reset
-- (the game's heat damage of a turbo then goes on from there)
local function engine() return powertrain.getDevice('mainEngine') end
function M.turbo(cond)
  local e = rules.effects('turbo', cond, settings)
  if not e then return end
  local t = engine() and engine().turbocharger
  if not (t and t.isExisting and t.setPartCondition and t.getPartCondition) then say('turbo: this car has none') return end
  if not turboBase then local _, st = t.getPartCondition() turboBase = {damageFrictionCoef = st.damageFrictionCoef, damageExhaustPowerCoef = st.damageExhaustPowerCoef} end
  turboTarget = {power = e.power, friction = e.friction}
  t.setPartCondition(0, {damageFrictionCoef = e.friction, damageExhaustPowerCoef = e.power}, 1)
  remember('turbo', 'all', cond)
  say(string.format('turbo condition %.2f: power x%.2f, friction x%.2f', cond, e.power, e.friction))
end
function M.radiator(cond)
  local e = rules.effects('radiator', cond, settings)
  if not e then return end
  local th = engine() and engine().thermals
  if not (th and th.setPartConditionRadiator) then say('radiator: no thermals on this car') return end
  radiatorTarget = e.integrity
  th.setPartConditionRadiator(0, e.integrity, 1)
  remember('radiator', 'all', cond)
  say(string.format('radiator condition %.2f: the game radiator integrity %.2f', cond, e.integrity))
end

function M.reapply(a)
  if a.kind == 'gearbox' then return M.gearbox(a.c) elseif a.kind == 'diff' then return M.diff(a.corner, a.c) elseif a.kind == 'cv' then return M.cv(a.corner, a.c)
  elseif a.kind == 'turbo' then return M.turbo(a.c) elseif a.kind == 'radiator' then return M.radiator(a.c) elseif a.kind == 'ignition' then return M.ignition(a.c) elseif a.kind == 'oil' then return M.oil(a.c) end
  if a.kind == 'pads' then M.pads(a.corner, a.c) elseif a.kind == 'engine' then M.engine(a.c) elseif a.kind == 'rotor' then M.rotor(a.corner, a.c) elseif a.kind == 'clutch' then M.clutch(a.c) else want(a.kind, a.corner, a.c) end
end

function M.clear()
  for cid, r in pairs(beams) do
    if r.kind == 'damper' then
      local b = r.base
      obj:setBoundedBeamDamp(cid, b[1], b[2], b[3], b[4], b[5], b[6])
    else
      obj:setBeamSpringDamp(cid, r.base[1], r.base[2], -1, -1)
      if r.rest0 then obj:setBeamLength(cid, r.rest0) end
    end
    r.target, r.curv, r.rest0 = nil, nil, nil
  end
  for i, br in pairs(brakes) do
    local w = (wheels.wheelRotators or wheels.wheels)[i]
    if w then w.brakeTorque, w.padGlazingFactor, w.squealCoefLowSpeed, w.frictionTorque = br.base[1], br.base[2], br.base[3], br.base[4] end
  end
  brakes, applied, engineTarget, clutchTarget, rotorCond, moving = {}, {}, nil, nil, {}, false
  for d, fields in pairs(fieldBase) do for f, x in pairs(fields) do d[f] = x end end
  fieldBase, gearboxTarget, diffTarget, cvTarget, ignitionTarget, oilTarget = {}, nil, {}, {}, nil, nil
  local eng0 = engine()
  if turboBase and eng0 and eng0.turbocharger and eng0.turbocharger.setPartCondition then pcall(eng0.turbocharger.setPartCondition, 0, turboBase, 1) end
  if radiatorTarget and eng0 and eng0.thermals and eng0.thermals.setPartConditionRadiator then pcall(eng0.thermals.setPartConditionRadiator, 0, 1, 1) end
  turboBase, turboTarget, radiatorTarget = nil, nil, nil
  local cl = powertrain.getDevice('clutch')
  if cl and cl.wearLockTorqueCoef then cl.wearLockTorqueCoef, cl.wearClutchFreePlayCoef = 1, 1 end
  local eng = powertrain.getDevice('mainEngine')
  if eng then eng.outputTorqueState, eng.wearDynamicFrictionCoef, eng.slowIgnitionErrorChance, eng.fastIgnitionErrorChance = 1, 1, 0, 0 end
  say('cleared: every jbeam value back')
end

function M.status()
  for _, a in ipairs(applied) do say(string.format('applied %s %s %.2f', a.kind, a.corner, a.c)) end
  for cid, r in pairs(beams) do
    if r.curv then say(string.format('  beam %d %s %s now %s', cid, r.kind, r.corner, table.concat((function() local t = {} for i, x in ipairs(r.curv) do t[i] = string.format('%.4g', x) end return t end)(), ' '))) end
  end
end

-- one step toward the targets, at most 10 % of a value per frame
local function step()
  local still = false
  for cid, r in pairs(beams) do
    if r.target and r.curv then
      local changed = false
      for i = 1, #r.target do
        local nv = rules.limitStep(r.curv[i], r.target[i], i == 3 and r.kind == 'spring' and 0.05 or r.base[i] or 1, 0.10)
        if nv ~= r.curv[i] then r.curv[i], changed = nv, true end
      end
      if changed then
        still = true
        if r.kind == 'damper' then obj:setBoundedBeamDamp(cid, r.curv[1], r.curv[2], r.curv[3], r.curv[4], r.curv[5], r.curv[6])
        else obj:setBeamSpringDamp(cid, r.curv[1], r.curv[2], -1, -1) obj:setBeamLength(cid, r.curv[3]) end
      end
    end
  end
  for i, br in pairs(brakes) do
    local w = (wheels.wheelRotators or wheels.wheels)[i]
    if w and br.target then
      local cn = br.corner or ''
      local worst = rotorCond[cn] or rotorCond[cn:sub(1, 1)] or rotorCond.all or 1
      local extra = rules.wornFade(w.brakeSurfaceTemperature or 0, math.min(br.padC or 1, worst), settings)   -- on top of the game's own heat fade
      w.brakeTorque = rules.limitStep(w.brakeTorque, br.target[1] * extra, br.base[1], 0.10)
      w.padGlazingFactor, w.squealCoefLowSpeed, w.frictionTorque = br.target[2], br.target[3], br.target[4]
      if math.abs(w.brakeTorque - br.target[1] * extra) > 1e-6 or math.min(br.padC or 1, worst) < 1 then still = true end   -- (heat changes the fade every frame)
    end
  end
  moving = still
end

function M.onReset() pending = 2 end   -- the resets that follow overwrite what is set here: reapply two frames later

function M.updateGFX(dt)
  if pending > 0 then
    pending = pending - 1
    if pending == 0 then
      for _, r in pairs(beams) do r.curv = nil end   -- back at the jbeam values after the reset: start the steps from there
      for _, a in ipairs(copyOf(applied)) do M.reapply(a) end      -- (a copy: each reapply goes through remember(), which replaces its entry in the list)
      say('reapplied after a reset: ' .. #applied .. ' effects')
    end
  end
  if moving then step() end
  if clutchTarget then
    local cl = powertrain.getDevice('clutch')
    if cl and cl.wearLockTorqueCoef then cl.wearLockTorqueCoef, cl.wearClutchFreePlayCoef = clutchTarget.lock, clutchTarget.freePlay end
  end
  if engineTarget or ignitionTarget or oilTarget then
    local eng = powertrain.getDevice('mainEngine')
    if eng then
      if engineTarget then eng.outputTorqueState = math.min(eng.outputTorqueState or 1, engineTarget.cap) end
      if engineTarget or oilTarget then eng.wearDynamicFrictionCoef = (engineTarget and engineTarget.dyn or 1) * (oilTarget and oilTarget.dyn or 1) end
      local mis = math.max(engineTarget and engineTarget.misfire or 0, ignitionTarget and ignitionTarget.misfire or 0)
      if mis > 0 then eng.slowIgnitionErrorChance = math.max(eng.slowIgnitionErrorChance or 0, mis) end
    end
  end
  if gearboxTarget then
    for _, d in ipairs(devices(GEARBOXES)) do
      setField(d, 'wearFrictionCoef', gearboxTarget.friction)
      setField(d, 'wearGearRatioChangeRateCoef', gearboxTarget.shiftRate)      -- automatic and CVT only: the field is nil on the others
      if d.type == 'dctGearbox' then setField(d, 'wearLockTorqueCoef', gearboxTarget.lockTorque) end
    end
  end
  if next(diffTarget) then
    for _, d in ipairs(devices({differential = true})) do
      local a = axleOfDevice(d)
      setField(d, 'wearFrictionCoef', (a and diffTarget[a]) or diffTarget.all or 1)
    end
  end
  if next(cvTarget) then
    for _, d in ipairs(devices({shaft = true})) do
      local a = axleOfDevice(d)
      setField(d, 'wearFrictionCoef', a and (cvTarget[a] or cvTarget.all or 1) or cvTarget.all or math.max(cvTarget.F or 1, cvTarget.R or 1))      -- a single driveshaft: the worse of the two axles' shafts
    end
  end
end

M.onExtensionLoaded = function() say('loaded: detect(), damper(corner, c), spring(corner, c), pads(axle, c), engine(c, filter), preset(name), clear(), status()') end
return M
