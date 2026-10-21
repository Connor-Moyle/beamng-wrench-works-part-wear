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
local idKey = {}                  -- vehicle id -> the key its record was last read or written under (a respawn keeps the id; the car's config may not be readable yet while its jbeam loads)
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
local function loadStore()
  local now = scopeNow()
  if store and storeScope ~= now then saveStore() store = nil end       -- another mode or career slot: the old state is written, the new one read
  if not store then
    storeScope = now
    store = jsonReadFile and jsonReadFile(stateFile(now))
    if type(store) ~= 'table' then store = {} end
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
  if not (C and C.setPaintWear) then return end
  local key = carKey(id)
  local blob = key and loadStore()[key]
  local c = blob and blob.paint and blob.paint.all or 1
  local e = (not off) and rules.effects('paint', c, settings) or nil
  pcall(C.setPaintWear, id, e or { fade = 0, rust = 0, scuffs = 0, grime = 0 })
end
local function send(id, code) local o = veh(id) if o then o:queueLuaCommand(code) end end

local function give(id)       -- the extensions, the settings, then the car's saved conditions
  send(id, "extensions.load('slrrWearProbe') extensions.load('slrrWearLook') extensions.load('slrrWear')")
  send(id, 'slrrWear.setSettings(' .. lit(settings) .. ')')
  local key = carKey(id)
  givenKey[id] = key or false
  if key then idKey[id] = key say('car ' .. tostring(id) .. ' record key ' .. key) end
  local blob = key and loadStore()[key]
  if blob then send(id, 'slrrWear.restoreSnapshot(' .. lit(blob) .. ')') end
  paint(id)
end

-- The worn brake disc look: the car must carry the worn and rusty variants of disc_brake from spawn, so they go in its glowMap while part wear and its worn look are on
-- (the variants are in vehicles/common/slrrPartWear/stages.materials.json, loaded with the first car; made by tools/make_disc_stage_materials.py). Cars spawned earlier keep their own discs.
local DISC = 'disc_brake'
function M.onJbeamLoadingPhase2(_, objID, vehicle)
  if not (settings.wearEnabled and (settings.visualWear or 0) > 0) or type(vehicle) ~= 'table' then return end
  vehicle.glowMap = vehicle.glowMap or {}
  if not vehicle.glowMap[DISC] then vehicle.glowMap[DISC] = { off = DISC, on = 'slrr_disc_brake_worn', on_intense = 'slrr_disc_brake_rusty', simpleFunction = 'slrr_never' } end      -- calipers and hubs: switched while driving
  -- The discs themselves are not plain disc_brake: brakepads.jbeam gives every wheel a brake glow entry (disc_brake_FR ... off = disc_brake, on = the glowing disc), which the engine switches
  -- with the brake temperature. They are not switched by us while driving (we would fight the engine); their `off` material is set HERE, once, from the saved condition: the look of a disc changes at the
  -- next spawn or garage visit, the red-hot glow is untouched. The wheel in the entry's name (FR, FL, RR, RL, or F / R for an axle) names the corner.
  local key = idKey[objID] or carKey(objID)
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
        local st = rules.discStage(math.min(rot, pad), settings.visualWear)
        if st > 0 then e.off = st == 2 and 'slrr_disc_brake_rusty' or 'slrr_disc_brake_worn' set = set + 1 end
      end
    end
  end
  say('worn disc look: glowMap entry added for car ' .. tostring(objID) .. ', ' .. set .. ' disc(s) worn at spawn, record key ' .. tostring(key) .. (rec and next(rec) and '' or ' (no record under it)'))
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

function M.attach(id)
  if not settings.wearEnabled then return end
  watched[id] = true
  give(id)
end
function M.forget(id) watched[id], keyOf[id], givenKey[id], lookMsc[id], idKey[id] = nil, nil, nil, nil, nil end
M.onVehicleDestroyed = M.forget
function M.onVehicleSpawned(id) lookMsc[id] = nil if settings.wearEnabled and watched[id] then give(id) end end
function M.onVehicleSwitched(_, newId) if settings.wearEnabled and newId and newId >= 0 and not watched[newId] then M.attach(newId) end end

-- the vehicle's report: its snapshot of the parts below new
function M.onReport(id, blob)
  local key = watched[id] and type(blob) == 'table' and carKey(id)
  if not key then return end
  loadStore()[key] = next(blob) and blob or nil
  idKey[id] = key
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
function M.onUpdate(dtReal)
  clock = clock + (dtReal or 0)
  if settings.wearEnabled and clock >= checkAt then      -- a career car gets its id a moment after it spawns, or a car changes hands: give it its record when its key is known or has changed
    checkAt = clock + 1
    for id in pairs(watched) do
      local k = carKey(id) or false
      if k ~= givenKey[id] then give(id) end
    end
  end
  if dirtyAt and clock - dirtyAt >= SAVE_EVERY then saveStore() end
end
function M.onExit() if dirtyAt then saveStore() end end

function M.status()
  local n = 0 for _ in pairs(watched) do n = n + 1 end
  local cars = 0 for _ in pairs(loadStore()) do cars = cars + 1 end
  return string.format('part wear %s, %d cars watched, %d cars with stored wear', settings.wearEnabled and 'on' or 'off', n, cars)
end

function M.onSlrrSettingsReady()
  local S = rawget(_G, 'slrr_settings')
  if S and S.register then S.register(schema.build(S, { reload = M.reload })) end
end
function M.onExtensionLoaded() M.reload() M.onSlrrSettingsReady() end

return M
