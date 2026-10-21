-- slrrWearLook: how worn each wheel's brake disc looks. From the disc and pad conditions (slrrWear.update hands over a reader) each wheel gets a stage: 0 the car's own disc, 1 worn (a
-- surface bloom of rust), 2 rusty. The wheel's disc meshes (the flexbodies with the material disc_brake that hold the wheel's hub nodes) are switched on the game side
-- (slr_partwear.look): called from the car's Lua a material switch has no effect on the screen (found with the tyre look of Car Surface FX), and a switch target must have been in the
-- car's glowMap at spawn (slr_partwear.onJbeamLoadingPhase2): a car spawned before part wear and its worn look were switched on keeps its own discs.
local M = {}

local MATERIAL = 'disc_brake'
local WORN_BELOW, RUSTY_BELOW = 0.6, 0.3        -- condition of the worse of disc and pads: MODELLED
local sw                                         -- wheel index -> { {orig, mesh}, ... } once built
local axle                                       -- wheel index -> 'F' / 'R', and corner 'FL' ..
local corner = {}
local stageOf = {}

local function hasNode(fb, id)
  for _, key in ipairs({ '_group_nodes', 'nodes', 'cids' }) do
    if type(fb[key]) == 'table' then for _, n in pairs(fb[key]) do if n == id then return true end end end
  end
  return false
end

local function build()
  sw, axle, corner = {}, {}, {}
  local ys, n = 0, 0
  for _, w in pairs(wheels and wheels.wheels or {}) do local nd = v.data.nodes[w.node1] if nd and nd.pos then ys, n = ys + nd.pos.y, n + 1 end end
  local meshes = {}
  for m in tostring(obj:getMeshesContainingMaterial(MATERIAL) or ''):gmatch('%S+') do meshes[m] = true end
  for wi, wd in pairs(wheels and wheels.wheels or {}) do
    local nd = v.data.nodes[wd.node1]
    local front = nd and nd.pos and n > 0 and nd.pos.y < ys / n
    axle[wi] = front and 'F' or 'R'
    corner[wi] = (front and 'F' or 'R') .. ((nd and nd.pos and nd.pos.x > 0) and 'L' or 'R')      -- jbeam +x is the car's left, y grows backward
    local list = {}
    for _, fb in ipairs(v.data.flexbodies or {}) do
      if fb.mesh and meshes[fb.mesh] and (hasNode(fb, wd.node1) or (wd.node2 and hasNode(fb, wd.node2))) then list[#list + 1] = { orig = MATERIAL, mesh = fb.mesh } end
    end
    sw[wi] = list
  end
end

local function stageFor(c, visual)
  if (visual or 0) <= 0 then return 0 end
  return c < RUSTY_BELOW and 2 or (c < WORN_BELOW and 1 or 0)
end
M.stageFor = stageFor

local function send(wi, stage)
  local pairsOut = {}
  for _, s in ipairs(sw[wi] or {}) do pairsOut[#pairsOut + 1] = string.format('{%q,%q}', s.orig, s.mesh) end
  if #pairsOut > 0 and obj and obj.queueGameEngineLua then
    obj:queueGameEngineLua(string.format('if slrr_partwear then slrr_partwear.look(%d,%d,%d,{%s}) end', obj:getId(), wi, stage, table.concat(pairsOut, ',')))
  end
end

-- get(kind, corner) -> condition 0..1 (slrrWear's store); settings.visualWear 0..1 (0 = no worn look)
function M.update(get, settings)
  if not sw or not next(sw) then build() end
  for wi in pairs(sw) do
    local c = math.min(get('rotor', corner[wi]), get(axle[wi] == 'F' and 'padF' or 'padR', axle[wi]))
    local stage = stageFor(c, settings and settings.visualWear)
    if (stageOf[wi] or 0) ~= stage then       -- (a disc not yet seen is the car's own: stage 0 needs no message, and after a reset the game has put every switch back)
      stageOf[wi] = stage
      send(wi, stage)
    end
  end
end

function M.restore()                  -- every disc back to the car's own: only for the player switching part wear or the worn look off (the car is alive)
  for wi, stage in pairs(stageOf) do if stage ~= 0 then send(wi, 0) end end
  stageOf = {}
end
function M.stages() local t = {} for wi, s in pairs(stageOf) do t[#t + 1] = wi .. '=' .. s end table.sort(t) return table.concat(t, ' ') end
function M.onReset() stageOf = {} end      -- the game puts every material switch back on a reset: the worn ones go out again on the next update
function M.drop() stageOf = {} end                -- state only: at a level end or when the car is destroyed nothing is written to the engine's materials
function M.onExtensionUnloaded() M.drop() end

return M
