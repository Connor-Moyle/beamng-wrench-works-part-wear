-- Part wear: the Mods menu page "Part wear" (Wrench Works' slrr_settings registry, docs/MODS_MENU.md there). One file, FILE, holds the settings in the shape of
-- slrrWearRules.settings(): { wearEnabled = false, lifeScale = 0.1, ... }. A key the file lacks is the rules' value for the preset in it (Realistic when none). The whole feature is OFF until
-- wearEnabled is switched on (or a preset other than Off is picked).
local M = {}
local rules = require('slrrWearRules')

M.FILE = '/settings/slrrPartWear.json'
M.ENABLED_DEFAULT = false

M.TABS = {
  { id = 'wear', title = 'Wear', description = 'Part wear: every part of the car has a condition that goes down as you drive, and a worn part changes how the car drives. Off until you switch it on.' },
  { id = 'effects', title = 'Effects', description = 'How much a fully worn part changes the car.' },
  { id = 'looks', title = 'Looks', description = 'How worn parts look.' },
}

-- tab, key, label, tooltip, min, max, step, unit
local ROWS = {
  { 'wear', 'lifeScale', 'Wear speed', 'How much of a real part\'s life one kilometre uses. 0.1 means parts last a tenth of their real life: a 40,000 km set of pads lasts 4,000 km.', 0.01, 1, 0.01, 'x' },
  { 'wear', 'abuseScale', 'Rough driving', 'How much hard stops, launches and jumps add to the wear. 0 ignores them.', 0, 3, 0.1, 'x' },
  { 'wear', 'ageScale', 'Age', 'How much the passing of time (brake fluid, battery, exhaust, radiator) adds to the wear.', 0, 3, 0.1, 'x' },
  { 'effects', 'effectStrength', 'Effect strength', 'Multiplies every effect of a worn part. 0 means worn parts feel like new ones.', 0, 2, 0.1, 'x' },
  { 'effects', 'springSagMax', 'Spring sag', 'How far a fully worn spring lets its corner of the car sink.', 0, 40, 1, 'mm' },
  { 'effects', 'springRateLoss', 'Spring softening', 'How much softer a fully worn spring gets.', 0, 0.4, 0.01, '%' },
  { 'effects', 'damperLossMax', 'Shock absorbers', 'How much of its damping a fully worn shock absorber loses: the car floats and bounces more.', 0, 0.9, 0.05, '%' },
  { 'effects', 'brakeTorqueLoss', 'Brake pads', 'How much braking force fully worn pads lose, before they are down to the metal.', 0, 0.3, 0.01, '%' },
  { 'effects', 'enginePowerLoss', 'Engine', 'How much power a fully worn engine loses.', 0, 0.3, 0.01, '%' },
  { 'effects', 'judder', 'Brake judder', 'How much worn brake discs shake the car under braking.', 0, 2, 0.1, 'x' },
  { 'effects', 'failureRate', 'Breakdown chance', 'How often a part that is nearly gone breaks (a snapped spring, a seized brake). Only when breakdowns are on.', 0, 3, 0.1, 'x' },
  { 'looks', 'visualWear', 'Worn look', 'How strongly worn parts show it: rust, fading paint, grime. 0 means no change to how parts look.', 0, 1, 0.05, '%' },
}

-- the settings read from the file, over the preset in it
function M.read(readJson)
  local f = readJson and readJson(M.FILE)
  f = type(f) == 'table' and f or {}
  local s = rules.settings(f.preset, f)
  s.wearEnabled = f.wearEnabled == true
  return s
end

function M.build(S, opts)
  opts = opts or {}
  local function json(path) return { kind = 'json', file = M.FILE, path = path } end
  local function changed() if opts.reload then opts.reload() end end
  local real = rules.PRESETS.Realistic
  local fields = {}
  fields[#fields + 1] = { id = 'wearEnabled', tab = 'wear', group = 'Part wear', type = 'bool', label = 'Part wear', feature = true, default = false, store = json('wearEnabled'), apply = 'live', onChange = changed,
    tooltip = 'Parts of the car wear out as you drive and a worn part changes how the car drives. Off: the car is exactly as the game makes it.' }
  local options = {}
  for _, name in ipairs({ 'Off', 'Light', 'Realistic' }) do
    local sets = {}
    for k, v in pairs(rules.PRESETS[name]) do sets[k] = v end
    options[#options + 1] = { id = name, label = name, sets = sets }
  end
  fields[#fields + 1] = { id = 'preset', tab = 'wear', group = 'Part wear', type = 'enum', label = 'Preset', default = 'Off', options = options, store = json('preset'), apply = 'live', onChange = changed,
    tooltip = 'Off: no wear. Light: slow wear, small effects, no breakdowns. Realistic: the full effects.' }
  fields[#fields + 1] = { id = 'failures', tab = 'effects', group = 'Breakdowns', type = 'bool', label = 'Parts can break', default = real.failures, store = json('failures'), apply = 'live', onChange = changed,
    tooltip = 'A part that is nearly gone can break: a snapped spring, a seized brake. Off: parts only get worse.' }
  for _, r in ipairs(ROWS) do
    local key = r[2]
    fields[#fields + 1] = { id = key, tab = r[1], group = r[1] == 'wear' and 'Speed of wear' or (r[1] == 'effects' and 'Effects' or 'Looks'), type = 'slider', label = r[3], tooltip = r[4], min = r[5], max = r[6], step = r[7],
      unit = r[8] == '%' and '%' or r[8], scale = r[8] == '%' and 100 or 1, default = real[key], store = json(key), apply = 'live', onChange = changed,
      advanced = key ~= 'lifeScale' and key ~= 'effectStrength' }
  end
  return { mod = 'slrr_partwear', title = 'Part wear', icon = 'wrench', order = 42, tabs = M.TABS, fields = fields }
end

return M
