-- Part wear, game side (global slrr_partwear). Reads the Mods page's settings (slrr/partwearSchema.lua), gives every watched car the vehicle extensions (slrrWear + the apply layer
-- slrrWearProbe), sends the settings and the car's saved conditions, and stores the conditions each car reports (every few seconds while they change).
-- OFF until wearEnabled: no extension is loaded in any car. The store is one file, STATE_FILE: { [carKey] = { kind = { corner = c } } }; carKey is the car's model and part config,
-- or what a caller gives with setCarKey(id, key) (a career car's own id). One file per scope (freeroam, each Street Legal slot, the game's career) so wear never leaks between careers.
--   slrr_partwear.attach(id)         watch a car (the player's car is attached by itself while part wear is on)
--   slrr_partwear.repair(id, kind, corner)   set one part back to new (corner nil = all corners of the kind)
--   slrr_partwear.status()           what is stored and watched
local M = {}
local rules = require('slrrWearRules')
local schema = require('slrr/partwearSchema')

local STATE_FILE = '/settings/slrrPartWear_state.json'
local SAVE_EVERY = 10
local settings = rules.settings('Off')
local watched, keyOf, givenKey, store = {}, {}, {}, nil
local dirtyAt, clock = nil, 0
local storeScope = 'free'

local function say(m) log('I', 'slrr_partwear', m) end
local function veh(id) return be and be:getObjectByID(id) end
local function lit(v)      -- a Lua literal of a JSON-safe table (numbers, strings, booleans, tables)
  if type(v) == 'table' then
    local t = {}
    for k, x in pairs(v) do t[#t + 1] = string.format('[%q]=%s', tostring(k), lit(x)) end
    return '{' .. table.concat(t, ',') .. '}'
  elseif type(v) == 'string' then return string.format('%q', v) end
  if type(v) == 'number' and (v ~= v or v == math.huge or v == -math.huge) then return '1' end      -- a NaN or inf would be a syntax error in the car's command
  return tostring(v)
end
-- wear never leaks between careers: one state file per scope. Freeroam is 'free'; Street Legal's career is 'sl<slot>' (its qa slot 'slqa'), the game's own career 'stock'; M.setScope(name) names any other.
local forced
local function scopeNow()
  if forced then return forced end
  local sl = rawget(_G, 'sl_career')
  if sl and sl.isActive and sl.isActive() == true then return 'sl' .. tostring(sl.getSlot and sl.getSlot() or 1) end
  local cc = rawget(_G, 'career_career')
  if cc and cc.isActive and cc.isActive() == true then return 'stock' end
  return 'free'
end
local function stateFile(scope) return scope == 'free' and STATE_FILE or (STATE_FILE:gsub('%.json$', '_' .. scope .. '.json')) end
local function saveStore() if store and jsonWriteFile then jsonWriteFile(stateFile(storeScope), store, true) end dirtyAt = nil end
local PRUNE_DAYS = 30
local function loadStore()
  local now = scopeNow()
  if store and storeScope ~= now then saveStore() store = nil end       -- another mode or career slot: the old state is written, the new one read
  if not store then
    storeScope = now
    store = jsonReadFile and jsonReadFile(stateFile(now))
    if type(store) ~= 'table' then store = {} end
    -- freeroam records are keyed by model and part config, so every config ever driven leaves one: each record has a last-seen day (store.__seen) and a freeroam record
    -- untouched for PRUNE_DAYS is dropped here (a record with no day yet starts counting now)
    local day = math.floor(os.time() / 86400)
    if type(store.__seen) ~= 'table' then store.__seen = {} end
    local seen = store.__seen
    for k in pairs(store) do if k ~= '__seen' and not seen[k] then seen[k] = day end end
    for k, d in pairs(seen) do
      if store[k] == nil or (now == 'free' and type(d) == 'number' and day - d > PRUNE_DAYS) then store[k], seen[k] = nil, nil end
    end
  end
  return store
end
function M.setScope(name) forced = name end
function M.scope() return scopeNow() end

local function hash(s)      -- a 32-bit string hash of the WHOLE text (a serialized part config can be long and alike for many cars)
  local h = 5381
  for i = 1, #s do h = (h * 33 + s:byte(i)) % 4294967296 end
  return string.format('%08x', h)
end
-- The record a car's wear is kept under: setCarKey's key if a caller gave one; in Street Legal's career the player's car id (sl_fleet.carOfVehicle), in the game's career the inventory id
-- (career_modules_inventory): two identical career cars never share wear. A career car that has no id yet (it is being registered) has no key: nothing is restored or stored for it until
-- it does. Freeroam cars of one model and config share one record (model + hash of the whole part config).
local remember          -- (defined below, with the parts tree helpers)
local settleAt = {}     -- vehicle id -> the time before which the game's parts tree is not trusted: right after a spawn or a swap it still holds the car that was replaced
local SETTLE, REFRESH = 3, 5       -- s: the settling time after a spawn or swap, and how often the player's parts are read again (getConfig hands out the game's own table, flatten walks about a few hundred slots)
local refreshAt = 0
local pendingNew = {}   -- vehicle id -> { {kind, corner}, ... } the parts a swap made new, until the old car's last report is past and the new car has them
local chosen = {}       -- vehicle id -> { slot id -> chosen part name } as of its last spawn or parts change
local pinned = {}       -- vehicle id -> the freeroam key a part swap started from: the swap respawns the car with a changed part config, which is still the same car
local function carKey(id)
  if keyOf[id] then return keyOf[id] end
  local scope = scopeNow()
  if scope:sub(1, 2) == 'sl' then
    local f = rawget(_G, 'sl_fleet')
    local ok, carId = pcall(function() return f and f.carOfVehicle and f.carOfVehicle(id) end)
    return ok and carId and ('slcar' .. tostring(carId)) or nil
  elseif scope == 'stock' then
    local inv = rawget(_G, 'career_modules_inventory')
    local ok, invId = pcall(function() return inv and inv.getInventoryIdFromVehicleId and inv.getInventoryIdFromVehicleId(id) end)
    return ok and invId and ('inv' .. tostring(invId)) or nil
  end
  if pinned[id] then return pinned[id] end
  local o = veh(id)
  if not o then return 'car' .. tostring(id) end
  local cfg = tostring(o.partConfig)
  return tostring(o.JBeam) .. '|' .. hash(cfg) .. '|' .. #cfg
end
function M.setCarKey(id, key) keyOf[id] = key end
M.carKey = carKey

-- the paint wear look of a car: the layers of the stored paint condition go to Car Surface FX (nothing happens without it, or without its setPaintWear)
local function paint(id, off)
  local C = rawget(_G, 'carSurfaceFx')
  if not C then return end
  local key = carKey(id)
  local blob = key and loadStore()[key]
  if C.setPaintWear then
    local c = blob and blob.paint and blob.paint.all or 1
    local e = (not off) and rules.effects('paint', c, settings) or nil
    pcall(C.setPaintWear, id, e or { fade = 0, rust = 0, scuffs = 0, grime = 0 })
  end
  -- the windows (pits and haze) and the wiper blades (the share of drops a sweep clears), from the glass and wiper conditions; both hooks are Car Surface FX's, off or a clear = nothing
  if C.setGlassWear then
    local c = blob and blob.glass and blob.glass.all or 1
    local e = (not off) and rules.effects('glass', c, settings) or nil
    pcall(C.setGlassWear, id, e and { pits = e.pits, haze = e.haze } or { pits = 0, haze = 0 })
  end
  if C.setWiperWear then
    local c = blob and blob.wipers and blob.wipers.all or 1
    local e = (not off) and rules.effects('wipers', c, settings) or nil
    pcall(C.setWiperWear, id, e and e.factor or nil)
  end
end
local function send(id, code) local o = veh(id) if o then o:queueLuaCommand(code) end end

local wearRate = 1       -- the wear rate another mod asked for this session (Street Legal's 'Wear rate' setting); not saved: the caller sends it again
function M.sentSettings() local t = {} for k, v in pairs(settings) do t[k] = v end t.wearRate = wearRate return t end
-- k = a number above 0 (1 = as the player set the wear speed): every part's wear from now on is k times as fast, the stored conditions are not touched. Returns the rate in force.
function M.setWearRate(k)
  if type(k) == 'number' and k == k and k > 0 and k < math.huge then
    wearRate = rules.clamp(k, rules.RANGES.wearRate[1], rules.RANGES.wearRate[2])
    if settings.wearEnabled then for id in pairs(watched) do send(id, 'if slrrWear then slrrWear.setSettings(' .. lit(M.sentSettings()) .. ') end') end end
  end
  return wearRate
end
function M.getWearRate() return wearRate end

local function give(id)       -- the extensions, the settings, then the car's saved conditions
  send(id, "extensions.load('slrrWearProbe') extensions.load('slrrWearLook') extensions.load('slrrWear')")
  send(id, 'slrrWear.setSettings(' .. lit(M.sentSettings()) .. ')')
  local key = carKey(id)
  givenKey[id] = key or false
  if key then say('car ' .. tostring(id) .. ' record key ' .. key) end
  local st = key and loadStore()
  local blob = st and st[key]
  if blob then
    st.__seen[key] = math.floor(os.time() / 86400)       -- a record in use is not unused, whether or not the car has reported yet
    send(id, 'slrrWear.restoreSnapshot(' .. lit(blob) .. ')')
  end
  paint(id)
end

-- The worn look at spawn. The brake discs: the car must carry the worn and rusty variants of disc_brake from spawn, so they go in its glowMap while part wear and its worn look are on
-- (the variants are in vehicles/common/slrrPartWear/stages.materials.json, loaded with the first car; made by tools/make_disc_stage_materials.py). Cars spawned earlier keep their own discs.
local DISC = 'disc_brake'
-- the strength of one kind's look: 0 when the general Worn look or the kind's own setting is 0: the stages themselves do not scale
local function vis(k) return (settings.visualWear or 0) * (tonumber(settings[k]) or 1) end
-- the models the look list covers (JBeam name -> { metal =, engine = }, from the exhaust-mesh survey); the three tables below stay as the fallback
local function listed(jb, what)
  local ok, list = pcall(require, 'slrrWearLookList')
  local m = ok and type(list) == 'table' and type(list.models) == 'table' and list.models[jb]
  return m and m[what] or nil
end
-- JBeam name -> the material of the model's suspension, frame and exhaust metal (read from the game's vehicle files and a probe of a spawned pickup); the worn and rusty variants are in the same stages file
local MECH = { covet = 'covet_mechanical', vivace = 'vivace_mechanical', pickup = 'trucks_mechanical' }
-- JBeam name -> the material of the model's engine (block, head, headers, intake; 82's survey); its 'rusty' variant is heavy oily grime, 'worn' dust with a little oil
local BAY = { covet = 'ibishu_engine', vivace = 'vivace_engine', pickup = 'gavril_v8' }
local ROWS = { { 'metal', MECH, rules.mechCondition, 'lookMetal' }, { 'engine', BAY, rules.engineCondition, 'lookEngine' } }      -- { name in the log, JBeam -> material, the condition the stage follows }
function M.onJbeamLoadingPhase2(_, objID, vehicle)
  if not (settings.wearEnabled and (settings.visualWear or 0) > 0) or type(vehicle) ~= 'table' then return end
  vehicle.glowMap = vehicle.glowMap or {}
  if not vehicle.glowMap[DISC] then vehicle.glowMap[DISC] = { off = DISC, on = 'slrr_disc_brake_worn', on_intense = 'slrr_disc_brake_rusty', simpleFunction = 'slrr_never' } end      -- calipers and hubs: switched while driving
  -- The discs themselves are not plain disc_brake: brakepads.jbeam gives every wheel a brake glow entry (disc_brake_FR ... off = disc_brake, on = the glowing disc), which the engine switches
  -- with the brake temperature. They are not switched by us while driving (we would fight the engine); their `off` material is set HERE, once, from the saved condition: the look of a disc changes at the
  -- next spawn or garage visit, the red-hot glow is untouched. The wheel in the entry's name (FR, FL, RR, RL, or F / R for an axle) names the corner.
  local key = carKey(objID)      -- (a respawn with another config is another car: its record is another one; the same config finds its record)
  local rec = key and loadStore()[key] or {}
  local set = 0
  for name, e in pairs(vehicle.glowMap) do
    if type(e) == 'table' and e.off == DISC and name ~= DISC then
      local corner = tostring(name):match('^disc_brake_(%u%u?)$')
      if corner then
        local axle = corner:sub(1, 1)
        local rot = rec.rotor and tonumber(rec.rotor[corner]) or 1
        local pad = rec[axle == 'F' and 'padF' or 'padR']
        pad = pad and tonumber(pad[axle]) or 1
        local st = rules.discStage(math.min(rot, pad), vis('lookDiscs'))
        if st > 0 then e.off = st == 2 and 'slrr_disc_brake_rusty' or 'slrr_disc_brake_worn' set = set + 1 end
      end
    end
  end
  -- The suspension, frame and exhaust metal, and the engine bay: the model's material (ROWS) gets one glowMap entry whose off target is the worn or rusty variant, from the car's spring
  -- and damper conditions (the metal) or its engine condition (the bay). One stage for the whole car (a glowMap entry is per material, and nothing switches these while driving); a mesh
  -- that mixes in another material (the pickup's exhaust with the engine's, an alt shock) keeps that part as it is. An entry the car already has under that name is left alone.
  local o = veh(objID)
  local jb = o and tostring(o.JBeam)
  local stages = {}
  for _, row in ipairs(ROWS) do
    local mat = jb and (row[2][jb] or listed(jb, row[1]))
    local st = 0
    if mat and vehicle.glowMap[mat] == nil then
      st = rules.lookStage(row[3](rec), vis(row[4]))
      if st > 0 then
        local look = 'slrr_' .. mat .. (st == 2 and '_rusty' or '_worn')
        vehicle.glowMap[mat] = { off = look, on = look, simpleFunction = 'slrr_never' }
      end
    end
    stages[#stages + 1] = row[1] .. ' stage ' .. st
  end
  -- The wheels' rims: the list of rim materials that have worn and rusty variants (slrrWearLookList, made from the stock wheels). One stage for the whole car from the worse of its wheel bearings
  -- and its brake pads (like the discs). An entry is only added for a material that already exists in the game: a glowMap entry for an unknown name makes the engine create an EMPTY material of
  -- that name, which would blank any rim that used it later. A material the car does not use gets an entry that switches nothing.
  local rimSet, rimSkipped, rimStage = 0, 0, 0
  do
    local ok, list = pcall(require, 'slrrWearLookList')
    if ok and type(list) == 'table' and type(list.rims) == 'table' and scenetree and scenetree.findObject then
      local c = 1
      for _, v in pairs(rec.bearing or {}) do c = math.min(c, tonumber(v) or 1) end
      for _, k in ipairs({'padF', 'padR'}) do for _, v in pairs(rec[k] or {}) do c = math.min(c, tonumber(v) or 1) end end
      rimStage = rules.discStage(c, vis('lookRims'))
      if rimStage > 0 then
        for _, mat in ipairs(list.rims) do
          if vehicle.glowMap[mat] == nil then
            if scenetree.findObject(mat) then
              local look = 'slrr_' .. mat .. (rimStage == 2 and '_rusty' or '_worn')
              vehicle.glowMap[mat] = { off = look, on = look, simpleFunction = 'slrr_never' }
              rimSet = rimSet + 1
            else rimSkipped = rimSkipped + 1 end
          end
        end
      end
    end
  end
  stages[#stages + 1] = 'rims stage ' .. rimStage .. ' (' .. rimSet .. ' materials, ' .. rimSkipped .. ' not loaded)'
  -- The cabin: the same entries for the interior and seat materials (list.interior), one stage for the whole cabin from the seat condition (else the worse of the bodywork). The dash and
  -- the door cards share the material, so the whole cabin looks worn and not only the seats. Skin materials and the lit or detail-mapped ones are not in the list.
  local inSet, inSkipped, inStage = 0, 0, 0
  do
    local ok, list = pcall(require, 'slrrWearLookList')
    if ok and type(list) == 'table' and type(list.interior) == 'table' and scenetree and scenetree.findObject then
      local c
      for _, v in pairs(rec.seat or {}) do c = math.min(c or 1, tonumber(v) or 1) end
      if not c then for _, v in pairs(rec.body or {}) do c = math.min(c or 1, tonumber(v) or 1) end end
      inStage = rules.discStage(c or 1, vis('lookCabin'))
      if inStage > 0 then
        for _, mat in ipairs(list.interior) do
          if vehicle.glowMap[mat] == nil then
            if scenetree.findObject(mat) then
              local look = 'slrr_' .. mat .. (inStage == 2 and '_rusty' or '_worn')
              vehicle.glowMap[mat] = { off = look, on = look, simpleFunction = 'slrr_never' }
              inSet = inSet + 1
            else inSkipped = inSkipped + 1 end
          end
        end
      end
    end
  end
  stages[#stages + 1] = 'interior stage ' .. inStage .. ' (' .. inSet .. ' materials, ' .. inSkipped .. ' not loaded)'
  say('worn disc look: glowMap entry added for car ' .. tostring(objID) .. ', ' .. set .. ' disc(s) worn at spawn, ' .. table.concat(stages, ', ') .. ', record key ' .. tostring(key) .. (rec and next(rec) and '' or ' (no record under it)'))
end
local lookMsc = {}               -- vehicle id -> { 'material|mesh' -> switch id }
function M.look(id, wi, stage, list)       -- called by the car (slrrWearLook): a wheel's disc meshes to stage 0 (own), 1 (worn), 2 (rusty)
  local o = veh(id)
  if not o then return end
  lookMsc[id] = lookMsc[id] or {}
  local done, n = 0, 0
  for _, p in ipairs(list or {}) do
    n = n + 1
    local key = p[1] .. '|' .. p[2]
    local msc = lookMsc[id][key]
    if not msc then msc = o:getSwitchableMaterial(p[1], p[1], p[2]) lookMsc[id][key] = msc end
    if msc and msc >= 0 then
      done = done + 1
      if stage < 1 then o:resetMaterials(msc) else o:switchMaterial(msc, 'slrr_' .. p[1] .. (stage >= 2 and '_rusty' or '_worn')) end
    end
  end
  say(string.format('disc look: car %s wheel %s stage %s, %d mesh(es), %d switched', tostring(id), tostring(wi), tostring(stage), n, done))      -- (a switch id below 0 is a mesh the engine made no switch for)
end

local racingSent = {}        -- player car id -> the last busy flag sent to it (slrrWear.setRacing)
function M.attach(id)
  racingSent[id] = nil      -- (a car that is attached again has a fresh slrrWear: it is told again)
  if not settings.wearEnabled then return end
  watched[id] = true
  chosen[id], settleAt[id] = nil, clock + SETTLE      -- (the parts are taken a moment later, see onUpdate)
  give(id)
end
function M.forget(id) racingSent[id] = nil watched[id], keyOf[id], givenKey[id], lookMsc[id], pinned[id], chosen[id], pendingNew[id], settleAt[id] = nil, nil, nil, nil, nil, nil, nil, nil end
-- The parts the car carries, by slot, to tell which slot a swap changed: slot id -> chosen part name, from the parts tree (nodes keyed by slot id under `children`).
local function flatten(tree, out)
  out = out or {}
  for id, node in pairs(type(tree) == 'table' and tree.children or {}) do
    if type(node) == 'table' then out[id] = node.chosenPartName or '' flatten(node, out) end
  end
  return out
end
local function currentTree()
  local pm = rawget(_G, 'core_vehicle_partmgmt')
  local ok, cfg = pcall(function() return pm and pm.getConfig and pm.getConfig() end)
  return ok and type(cfg) == 'table' and cfg.partsTree or nil
end
-- The stored wear of one slot's part, for other mods (Wrench Works' shelf): { condition = the worst of its pairs, parts = { {kind, corner, c}, ... } } with only the pairs that have wear
-- stored (none: condition 1, new); nil when the slot covers no wear kind at all.
local function recordFor(rec, slot)
  local cover = rules.slotWear(slot)
  if #cover == 0 then return nil end
  local parts, worst = {}, 1
  for _, w in ipairs(cover) do
    for _, corner in ipairs(w.corners) do
      local c = rec and rec[w.kind] and rec[w.kind][corner]
      if type(c) == 'number' and c == c and c < 0.999 then
        parts[#parts + 1] = { kind = w.kind, corner = corner, c = c }
        if c < worst then worst = c end
      end
    end
  end
  return { condition = worst, parts = parts }
end
-- A new part in a slot is new: only the wear kinds and corners that slot holds (rules.slotWear) go back to 1.0, the rest of the car keeps its wear.
local function swapped(id, old, new)
  local n, changed, announce = 0, {}, {}
  local key = carKey(id)
  local rec = key and loadStore()[key]
  for slot, part in pairs(new) do
    if old[slot] ~= nil and old[slot] ~= part then
      if #changed < 6 then changed[#changed + 1] = slot end
      local record = recordFor(rec, slot)      -- the old part's wear, before it is set back to new
      if record then announce[#announce + 1] = { slot = slot, oldPart = old[slot], newPart = part, record = record } end
      for _, w in ipairs(rules.slotWear(slot)) do
        for _, corner in ipairs(w.corners) do
          M.repair(id, w.kind, corner)
          pendingNew[id] = pendingNew[id] or {}
          table.insert(pendingNew[id], { w.kind, corner })
          n = n + 1
        end
      end
    end
  end
  if #announce > 0 and rawget(_G, 'extensions') and extensions.hook then pcall(extensions.hook, 'onSlrrPartWearSwapped', id, announce) end
  if n > 0 then say('car ' .. tostring(id) .. ': ' .. n .. ' worn part(s) are new after the parts swap (slots changed: ' .. table.concat(changed, ', ') .. ')') end
end
-- the parts the player's car carries now, for the next swap's comparison (a car that was spawned before part wear was switched on is seen here, when it is attached)
remember = function(id)
  if not (be and id == be:getPlayerVehicleID(0)) then return end
  local ok, t = pcall(function() return flatten(currentTree()) end)
  if ok and next(t) then
    if not chosen[id] then      -- (said once per car: how many slots the snapshot saw and how long after the spawn, to tell a stale snapshot from a wrong compare in a bad run)
      local n = 0
      for _ in pairs(t) do n = n + 1 end
      say(string.format('car %s parts remembered: %d slots, %.1f s after the spawn or attach', tostring(id), n, clock - ((settleAt[id] or clock) - SETTLE)))
    end
    chosen[id] = t
  end
end
-- Wrench Works' shelf: the wear of the part in a slot (recordOf), handed back when a shelf part is fitted (restore), or raised by the garage's recondition. Conditions 0..1, 1 = new.
function M.recordOf(vehId, slotId)
  local key = settings.wearEnabled and carKey(vehId)
  if not key or type(slotId) ~= 'string' then return nil end
  return recordFor(loadStore()[key], slotId)
end
local function setPair(vehId, key, kind, corner, c)
  local st = loadStore()
  st[key] = st[key] or {}
  if c >= 0.999 then
    if st[key][kind] then st[key][kind][corner] = nil if not next(st[key][kind]) then st[key][kind] = nil end end
  else
    st[key][kind] = st[key][kind] or {}
    st[key][kind][corner] = c
  end
  if not next(st[key]) then st[key] = nil end
  if st.__seen then st.__seen[key] = st[key] and math.floor(os.time() / 86400) or nil end      -- a record we touch is in use
  for i = #(pendingNew[vehId] or {}), 1, -1 do      -- a swap's "new" mark no longer applies to what we now set by hand
    local p = pendingNew[vehId][i]
    if p[1] == kind and p[2] == corner then table.remove(pendingNew[vehId], i) end
  end
  send(vehId, string.format('if slrrWear then slrrWear.setCondition(%q, %q, %g) end', kind, corner, c))
  dirtyAt = dirtyAt or clock
end
local function covers(slotId, kind, corner)
  for _, w in ipairs(rules.slotWear(slotId)) do
    if w.kind == kind then for _, cn in ipairs(w.corners) do if cn == corner then return true end end end
  end
  return false
end
function M.restore(vehId, slotId, record)
  local key = settings.wearEnabled and carKey(vehId)
  if not key or type(slotId) ~= 'string' or type(record) ~= 'table' or type(record.parts) ~= 'table' then return false end
  local n = 0
  for _, p in ipairs(record.parts) do
    local c = type(p) == 'table' and tonumber(p.c)
    if c and c == c and covers(slotId, p.kind, p.corner) then
      setPair(vehId, key, p.kind, p.corner, rules.clamp(c, 0, 1))
      n = n + 1
    end
  end
  return n > 0
end
-- raises every worn pair of the slot to at least `condition` (a recondition never makes a part worse)
function M.recondition(vehId, slotId, condition)
  local key = settings.wearEnabled and carKey(vehId)
  condition = tonumber(condition)
  if not key or type(slotId) ~= 'string' or not condition or condition ~= condition then return false end
  condition = rules.clamp(condition, 0, 1)
  local r = recordFor(loadStore()[key], slotId)
  if not r then return false end
  for _, p in ipairs(r.parts) do if p.c < condition then setPair(vehId, key, p.kind, p.corner, condition) end end
  return true
end
-- the respawned car: the record holds the parts the swap made new (the old car's last report may have put the old wear back), then give(id) hands the record to the new car
local function newAgain(id)
  local list = pendingNew[id]
  pendingNew[id] = nil
  local key = list and carKey(id)
  local rec = key and loadStore()[key]
  if not rec then return end
  for _, p in ipairs(list) do
    if rec[p[1]] then rec[p[1]][p[2]] = nil if not next(rec[p[1]]) then rec[p[1]] = nil end end
  end
  if not next(rec) then loadStore()[key] = nil end
  dirtyAt = dirtyAt or clock
end
-- A part swap in freeroam (the game's parts menu, Wrench Works) fires this BEFORE the respawn: keep the car's record, so a swap is not a free repair of every other part, and set the
-- kinds of the changed slots back to new. A config loaded over the car (onVehicleReplaced) is another car again. (Career cars have explicit keys and are not pinned.)
function M.onPartsTreeConfigChanged(tree)
  local id = be and be:getPlayerVehicleID(0)
  if not (settings.wearEnabled and id and id >= 0) then return end
  if not keyOf[id] and not pinned[id] and scopeNow() == 'free' then pinned[id] = carKey(id) end
  local new = flatten(tree)
  if next(new) then
    local old = chosen[id] or flatten(currentTree())
    if next(old) then swapped(id, old, new) end
    chosen[id], settleAt[id] = new, clock + SETTLE
  end
end
function M.onVehicleReplaced(id) pinned[id], chosen[id] = nil, nil end
M.onVehicleDestroyed = M.forget
function M.onVehicleSpawned(id)
  lookMsc[id] = nil
  racingSent[id] = nil      -- (the car's Lua restarted: its fresh slrrWear is not racing, so the next check says again)
  newAgain(id)
  if settings.wearEnabled and watched[id] then give(id) end
  settleAt[id] = clock + SETTLE      -- (what was remembered stays: after a swap's respawn it is the new parts)
end
function M.onVehicleSwitched(_, newId) if settings.wearEnabled and newId and newId >= 0 and not watched[newId] then M.attach(newId) end end

-- the vehicle's report: its snapshot of the parts below new
function M.onReport(id, blob)
  local key = watched[id] and type(blob) == 'table' and carKey(id)
  if not key then return end
  if pendingNew[id] then      -- a part the swap made new: a report from the old car, sent before it was replaced, still has the old wear
    local keep = {}
    for _, p in ipairs(pendingNew[id]) do
      local t = blob[p[1]]
      if t and t[p[2]] and t[p[2]] < 0.999 then t[p[2]] = nil if not next(t) then blob[p[1]] = nil end keep[#keep + 1] = p end
    end
    pendingNew[id] = #keep > 0 and keep or nil      -- (a report that has it new or not at all: the car has the reset, no more filtering)
  end
  local st = loadStore()
  st[key] = next(blob) and blob or nil
  st.__seen[key] = st[key] and math.floor(os.time() / 86400) or nil
  paint(id)
  dirtyAt = dirtyAt or clock
end

function M.repair(id, kind, corner)
  local key = carKey(id)
  local snap = key and loadStore()[key]
  if snap and snap[kind] then
    if corner then snap[kind][corner] = nil else snap[kind] = nil end
    if snap[kind] and not next(snap[kind]) then snap[kind] = nil end
    dirtyAt = dirtyAt or clock
    paint(id)
  end
  if corner then send(id, string.format('slrrWear.setCondition(%q, %q, 1)', kind, corner))
  else send(id, string.format('for _, c in ipairs({"FL","FR","RL","RR","F","R","all"}) do slrrWear.setCondition(%q, c, 1) end', kind)) end
end

-- For testers and the showcase (store pictures): set a car's stored conditions by hand, { kind = { corner = c } }, e.g. { bearing = { FL = 0.2 }, seat = { all = 0.3 } }. The car is told at once; the looks
-- that are decided at spawn (rims, cabin, metal, engine bay) show after the car is spawned again with the same config. A corner 'all' sets every corner of a kind that has corners (bearing, padF ...).
-- Returns the number of conditions set. Not for other mods' gameplay.
local function validCorner(kind, corner)
  for _, k in ipairs(rules.CORNERS_OF[kind] or {}) do if k == corner then return true end end
  return false
end
function M.setConditions(vehId, tbl)
  local key = settings.wearEnabled and veh(vehId) and carKey(vehId)
  if not key or type(tbl) ~= 'table' then return 0 end
  local n = 0
  for kind, cs in pairs(tbl) do
    if rules.KINDS[kind] and type(cs) == 'table' then
      for corner, c in pairs(cs) do
        local v = tonumber(c)
        if v and v == v then
          v = math.max(0, math.min(1, v))
          -- 'all' on a kind with corners is every corner of it (a tester's shorthand); a corner the kind does not have is refused
          local list = (corner == 'all' and not validCorner(kind, 'all')) and rules.CORNERS_OF[kind] or (validCorner(kind, corner) and { corner }) or {}
          for _, k in ipairs(list) do setPair(vehId, key, kind, k, v) n = n + 1 end
        end
      end
    end
  end
  if n > 0 then paint(vehId) end
  return n
end

-- Using a consumable from the player's inventory (Street Legal's inventory calls this): useItem(vehId, kind, item) -> ok, why.
--   'battery' {charge}: a new battery (Part Wear's battery condition back to new); an electric car's traction battery (type electricBattery) is also set to item.charge. Fuel and N2O tanks are never touched;
--   an ordinary car's 12 V battery is no energy storage in the game, so there only the condition changes
--   'oil': an oil change (Part Wear's oil condition back to new). The game keeps no oil level a mod can refill, so there is nothing else to top up.
--   'coolant': the game's coolant refilled to full. The game has no setter that leaves the radiator alone, so a refill also clears the radiator's damage.
-- Every call into the car is guarded: a car without the part does nothing and still answers ok.
local ITEM_CODE = {
  battery = 'for _, s in pairs(energyStorage and energyStorage.getStorages() or {}) do if s.type == "electricBattery" and s.setRemainingRatio then pcall(s.setRemainingRatio, s, %f) end end',
  coolant = 'for _, d in pairs(powertrain and powertrain.getDevices() or {}) do if d.thermals and d.thermals.setPartConditionRadiator then pcall(d.thermals.setPartConditionRadiator, 0, {}) end end',
}
function M.useItem(vehId, kind, item)
  if not veh(vehId) then return false, 'no such car' end
  item = type(item) == 'table' and item or {}
  if kind == 'battery' then
    local ch = tonumber(item.charge) or 1
    M.repair(vehId, 'battery', 'all')
    send(vehId, string.format(ITEM_CODE.battery, ch ~= ch and 1 or math.max(0, math.min(1, ch))))
    return true, 'battery swapped'
  elseif kind == 'oil' then
    M.repair(vehId, 'oil', 'all')
    return true, 'oil changed (condition only)'
  elseif kind == 'coolant' then
    send(vehId, ITEM_CODE.coolant)
    return true, 'coolant refilled'
  end
  return false, 'unknown item kind'
end

-- ---- Wrench Works garage: worn parts are listed under Services, with their condition and a price; a click pays through the garage's own wallet and sets the part back to new.
-- The money goes through changeMoney (paid at once, not part of the visit, so undoing a visit cannot refund it). Only while part wear is on (otherwise the garage is exactly as it was). Nothing here needs Wrench Works to be installed: without it the two hooks are never called.
local CORNER_NAME = { FL = 'front left', FR = 'front right', RL = 'rear left', RR = 'rear right', F = '', R = '', all = '' }
local WORN_BELOW = 0.9           -- a part above this is not offered
local function garageParts() local ok, p = pcall(require, 'slrr/garageParts') return ok and p or nil end
local function priceMult()
  local ok, S = pcall(require, 'slrr/garageSettings')
  local m = ok and S and S.get and select(2, pcall(S.get, 'priceMultiplier'))
  return type(m) == 'number' and m or 1
end
local function worn(vehId)       -- { {kind, corner, c}, ... } of the car's parts that are worn enough to offer, worst first
  local key = settings.wearEnabled and carKey(vehId)
  local rec = key and loadStore()[key]
  local out = {}
  for kind, t in pairs(rec or {}) do
    if rules.PRICE[kind] then for corner, c in pairs(t) do if c < WORN_BELOW then out[#out + 1] = { kind = kind, corner = corner, c = c } end end end
  end
  table.sort(out, function(a, b) if a.c ~= b.c then return a.c < b.c end if a.kind ~= b.kind then return a.kind < b.kind end return a.corner < b.corner end)
  return out
end
local function label(w) return (rules.NAME[w.kind] or w.kind) .. ((CORNER_NAME[w.corner] or '') ~= '' and (' ' .. CORNER_NAME[w.corner]) or '') end

-- A read-only view of a car's stored conditions for other mods (Street Legal's service and used-car reports): { parts = { { id = 'damper:FL', kind, corner, section, condition (1 = new), name }, ... } }.
-- Only the parts that have wear stored are listed (a part that is not listed is new). Sections are the rules' groups, with the exhaust and the catalyst split off as 'exhaust'.
-- nil while part wear is off (or the car is not watched, for conditionsOf); conditionsOfKey reads the saved record of any car of the current mode or career slot, spawned or not.
local SECTION_OF = { exhaust = 'exhaust', cat = 'exhaust' }
local function conditionsOfRecord(rec)
  local parts = {}
  for kind, t in pairs(rec or {}) do
    local k = rules.KINDS[kind]
    if k and type(t) == 'table' then
      for corner, c in pairs(t) do
        if type(c) == 'number' and c == c then
          parts[#parts + 1] = { id = kind .. ':' .. corner, kind = kind, corner = corner, section = SECTION_OF[kind] or k.group, condition = c, name = rules.NAME[kind] or kind }
        end
      end
    end
  end
  table.sort(parts, function(a, b) return a.id < b.id end)
  return { parts = parts }
end
function M.conditionsOfKey(key) return settings.wearEnabled and key and conditionsOfRecord(loadStore()[key]) or nil end
function M.conditionsOf(vehId) return watched[vehId] and M.conditionsOfKey(carKey(vehId)) or nil end

function M.onWrenchWorksServices(list, vehId)
  if not settings.wearEnabled then return end
  local P = garageParts()
  local money = P and P.getMoney and P.getMoney()
  local mult = priceMult()
  for _, w in ipairs(worn(vehId)) do
    local price = rules.repairPrice(w.kind, w.c, mult)
    local name = (w.kind == 'paint') and 'Restore the paint' or ('Replace ' .. label(w))
    list[#list + 1] = { id = 'pw:' .. w.kind .. ':' .. w.corner, tab = 'services', group = 'Part wear', label = name,
      desc = string.format('%s, %d %% left', rules.stage(w.c), math.floor(w.c * 100 + 0.5)), price = price,
      disabled = not P or (type(money) == 'number' and money < price) }
  end
end

function M.onWrenchWorksService(id, vehId)
  local kind, corner = tostring(id):match('^pw:([%w_]+):([%w_]+)$')
  if not kind or not settings.wearEnabled then return end
  local P = garageParts()
  if not (P and P.changeMoney) then return end        -- changeMoney, not pay: pay counts towards the visit and is refunded when the visit is undone, but the part would stay new
  for _, w in ipairs(worn(vehId)) do
    if w.kind == kind and w.corner == corner then
      local price = rules.repairPrice(kind, w.c, priceMult())
      if P.changeMoney(-price, 'Part wear: ' .. label(w)) then M.repair(vehId, kind, corner) say('repaired ' .. label(w) .. ' for ' .. tostring(price)) end
      return
    end
  end
end

-- the Mods page changed (or the game started): read the settings, switch the cars on or off
function M.reload()
  local was = settings.wearEnabled
  settings = schema.read(jsonReadFile)
  if settings.wearEnabled then
    for id in pairs(watched) do give(id) end
    if not was then
      local p = be and be:getPlayerVehicleID(0)
      if p and p >= 0 then M.attach(p) end
    end
  elseif was then
    for id in pairs(watched) do send(id, 'if slrrWear then slrrWear.setSettings({wearEnabled=false}) end') paint(id, true) end
    saveStore()
  end
  return settings
end

function M.getSettings() return settings end
local checkAt = 0
-- Street Legal's "busy": a race, a job, a chase, a phase switch, a scene or an open lot (freeToStart answers the reason). The player's car is told, so that "No failures during a race" works;
-- outside a running career (free roam) nothing is ever busy.
local function careerBusy()
  local c = rawget(_G, 'sl_career')
  if not (c and c.isActive and c.freeToStart) then return false end
  local ok, active = pcall(c.isActive)
  if not (ok and active) then return false end
  local ok2, reason = pcall(c.freeToStart)
  return ok2 and reason ~= nil
end
function M.onUpdate(dtReal)
  clock = clock + (dtReal or 0)
  if settings.wearEnabled and clock >= checkAt then      -- a career car gets its id a moment after it spawns, or a car changes hands: give it its record when its key is known or has changed
    checkAt = clock + 1
    for id in pairs(watched) do
      local k = carKey(id) or false
      if k ~= givenKey[id] then give(id) end
    end
    local pid = be and be:getPlayerVehicleID(0)
    if pid and watched[pid] then
      local busy = careerBusy()
      if racingSent[pid] ~= busy then
        racingSent[pid] = busy
        send(pid, string.format('if slrrWear and slrrWear.setRacing then slrrWear.setRacing(%s) end', tostring(busy)))
      end
    end
  end
  if settings.wearEnabled and clock >= refreshAt then      -- the player's parts as the game reports them, once they have settled (a swap is judged against these)
    refreshAt = clock + REFRESH
    local id = be and be:getPlayerVehicleID(0)
    if id and watched[id] and clock >= (settleAt[id] or 0) then remember(id) end
  end
  if dirtyAt and clock - dirtyAt >= SAVE_EVERY then saveStore() end
end
function M.onExit() if dirtyAt then saveStore() end end

function M.status()
  local n = 0 for _ in pairs(watched) do n = n + 1 end
  local cars = 0 for k in pairs(loadStore()) do if k ~= '__seen' then cars = cars + 1 end end
  return string.format('part wear %s, %d cars watched, %d cars with stored wear', settings.wearEnabled and 'on' or 'off', n, cars)
end

function M.onSlrrSettingsReady()
  local S = rawget(_G, 'slrr_settings')
  if S and S.register then S.register(schema.build(S, { reload = M.reload })) end
end
function M.onExtensionLoaded() M.reload() M.onSlrrSettingsReady() end

return M
