-- GE console probe (not shipped): for the player's car, every fitted flexbody mesh grouped by the materials it uses, one log line per group:
--   'pwprobe: {materials...} N meshes: a b c ...'. The calls are the ones the game's own common/jbeam/materials.lua uses (vehicleObj:getMeshsMaterialsTbl(mesh), the vehicle data's vdata.flexbodies).
-- Paste into the GE console (one line, see the README of this folder); then read the lines from beamng.log. For the part wear stage materials: which material the suspension, exhaust and engine meshes of a car use.
local o = be:getPlayerVehicle(0)
local vd = core_vehicle_manager.getVehicleData(o:getID())
local groups, order = {}, {}
for _, fb in pairs(vd.vdata.flexbodies or {}) do
  if fb.mesh then
    local key = dumps(o:getMeshsMaterialsTbl(fb.mesh))
    if not groups[key] then groups[key] = {} order[#order + 1] = key end
    table.insert(groups[key], fb.mesh)
  end
end
for _, key in ipairs(order) do
  local l = groups[key]
  table.sort(l)
  log('I', 'pwprobe', key:gsub('%s+', ' ') .. ' ' .. #l .. ' meshes: ' .. table.concat(l, ' ', 1, math.min(#l, 40)))
end
