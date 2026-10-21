-- Part wear, game side (global slrr_partwear). Reads the Mods page's settings (slrr/partwearSchema.lua), gives every watched car the vehicle extensions (slrrWear + the apply layer
-- slrrWearProbe), sends the settings and the car's saved conditions, and stores the conditions each car reports (every few seconds while they change).
-- OFF until wearEnabled: no extension is loaded in any car. The store is one file, STATE_FILE: { [carKey] = { kind = { corner = c } } }; carKey is the car's model and part config,
-- or what a caller gives with setCarKey(id, key) (a career car's own id).
--   slrr_partwear.attach(id)         watch a car (the player's car is attached by itself while part wear is on)
--   slrr_partwear.repair(id, kind, corner)   set one part back to new (corner nil = all corners of the kind)
--   slrr_partwear.status()           what is stored and watched
local M = {}
local rules = require('slrrWearRules')
local schema = require('slrr/partwearSchema')

local STATE_FILE = '/settings/slrrPartWear_state.json'
local SAVE_EVERY = 10
local settings = rules.settings('Off')
local watched, keyOf, store = {}, {}, nil
local dirtyAt, clock = nil, 0

local function veh(id) return be and be:getObjectByID(id) end
local function lit(v)      -- a Lua literal of a JSON-safe table (numbers, strings, booleans, tables)
  if type(v) == 'table' then
    local t = {}
    for k, x in pairs(v) do t[#t + 1] = string.format('[%q]=%s', tostring(k), lit(x)) end
    return '{' .. table.concat(t, ',') .. '}'
  elseif type(v) == 'string' then return string.format('%q', v) end
  return tostring(v)
end
local function loadStore()
  if not store then
    store = jsonReadFile and jsonReadFile(STATE_FILE)
    if type(store) ~= 'table' then store = {} end
  end
  return store
end
local function saveStore() if store and jsonWriteFile then jsonWriteFile(STATE_FILE, store, true) end dirtyAt = nil end

local function carKey(id)
  if keyOf[id] then return keyOf[id] end
  local o = veh(id)
  return o and (tostring(o.JBeam) .. '|' .. tostring(o.partConfig):sub(1, 200)) or ('car' .. tostring(id))
end
function M.setCarKey(id, key) keyOf[id] = key end

-- the paint wear look of a car: the layers of the stored paint condition go to Car Surface FX (nothing happens without it, or without its setPaintWear)
local function paint(id, off)
  local C = rawget(_G, 'carSurfaceFx')
  if not (C and C.setPaintWear) then return end
  local blob = loadStore()[carKey(id)]
  local c = blob and blob.paint and blob.paint.all or 1
  local e = (not off) and rules.effects('paint', c, settings) or nil
  pcall(C.setPaintWear, id, e or { fade = 0, rust = 0, scuffs = 0, grime = 0 })
end
local function send(id, code) local o = veh(id) if o then o:queueLuaCommand(code) end end

local function give(id)       -- the extensions, the settings, then the car's saved conditions
  send(id, "setExtensionUnloadMode('slrrWearProbe','manual') extensions.load('slrrWearProbe') setExtensionUnloadMode('slrrWear','manual') extensions.load('slrrWear')")
  send(id, 'slrrWear.setSettings(' .. lit(settings) .. ')')
  local blob = loadStore()[carKey(id)]
  if blob then send(id, 'slrrWear.restoreSnapshot(' .. lit(blob) .. ')') end
  paint(id)
end

function M.attach(id)
  if not settings.wearEnabled then return end
  watched[id] = true
  give(id)
end
function M.forget(id) watched[id], keyOf[id] = nil, nil end
M.onVehicleDestroyed = M.forget
function M.onVehicleSpawned(id) if settings.wearEnabled and watched[id] then give(id) end end
function M.onVehicleSwitched(_, newId) if settings.wearEnabled and newId and newId >= 0 and not watched[newId] then M.attach(newId) end end

-- the vehicle's report: its snapshot of the parts below new
function M.onReport(id, blob)
  if not watched[id] or type(blob) ~= 'table' then return end
  loadStore()[carKey(id)] = next(blob) and blob or nil
  paint(id)
  dirtyAt = dirtyAt or clock
end

function M.repair(id, kind, corner)
  local snap = loadStore()[carKey(id)]
  if snap and snap[kind] then
    if corner then snap[kind][corner] = nil else snap[kind] = nil end
    if snap[kind] and not next(snap[kind]) then snap[kind] = nil end
    dirtyAt = dirtyAt or clock
  end
  if corner then send(id, string.format('slrrWear.setCondition(%q, %q, 1)', kind, corner))
  else send(id, string.format('for _, c in ipairs({"FL","FR","RL","RR","F","R","all"}) do slrrWear.setCondition(%q, c, 1) end', kind)) end
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
function M.onUpdate(dtReal)
  clock = clock + (dtReal or 0)
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
