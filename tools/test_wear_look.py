"""The worn brake disc look: the vehicle side (slrrWearLook.lua) against a stand-in car, and the game side's glowMap hook and switch (slr/partwear.lua).

    python tools/test_wear_look.py
"""
import os
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "mod", "lua")


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
      sent = {}
      v = {data = {nodes = {[1] = {pos = {x = 0.7, y = 0, z = 0}}, [2] = {pos = {x = -0.7, y = 0, z = 0}}, [3] = {pos = {x = 0.7, y = 2.5, z = 0}}, [4] = {pos = {x = -0.7, y = 2.5, z = 0}}},
                   -- the flexbody order is the reverse of the wheel order on purpose
                   flexbodies = {{mesh = 'disc_RR', _group_nodes = {4}}, {mesh = 'disc_RL', _group_nodes = {3}}, {mesh = 'disc_FR', _group_nodes = {2}}, {mesh = 'disc_FL', _group_nodes = {1}}, {mesh = 'body', _group_nodes = {9}}}}}
      wheels = {wheels = {[0] = {name = 'a', node1 = 1}, [1] = {name = 'b', node1 = 2}, [2] = {name = 'c', node1 = 3}, [3] = {name = 'd', node1 = 4}}}
      obj = {getMeshesContainingMaterial = function(_, m) return m == 'disc_brake' and 'disc_FL disc_FR disc_RL disc_RR' or '' end, getId = function() return 7 end,
             queueGameEngineLua = function(_, c) sent[#sent + 1] = c end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
      conds = {}
      function get(kind, corner) return (conds[kind] or {})[corner] or 1 end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    L = lua.execute(open(os.path.join(ROOT, "vehicle", "extensions", "slrrWearLook.lua"), encoding="utf8").read())
    lua.globals().L_ = L
    S = lua.table(visualWear=1)
    L.update(lua.globals().get, S)
    assert lua.eval("#sent") == 0, "new discs: nothing to send"
    lua.execute("sent = {}")
    lua.execute("conds = {rotor = {FL = 0.5}, padF = {F = 0.8}}")
    L.update(lua.globals().get, S)
    s = [lua.eval("sent")[i + 1] for i in range(lua.eval("#sent"))]
    assert any("look(7,0,1,{{\"disc_brake\",\"disc_FL\"}})" in x for x in s), s
    assert not any("look(7,1,1" in x for x in s), "the front right disc is fine"
    lua.execute("sent = {} conds = {rotor = {FL = 0.2}, padF = {F = 0.8}}")
    L.update(lua.globals().get, S)
    assert "look(7,0,2,{{\"disc_brake\",\"disc_FL\"}})" in lua.eval("sent[1]") and lua.eval("#sent") == 1, "rusty below 30 %"
    lua.execute("sent = {}")
    L.update(lua.globals().get, S)
    assert lua.eval("#sent") == 0, "no repeat while the stage is the same"
    # worn pads make both discs of the axle look worn (the worse of disc and pads)
    lua.execute("sent = {} conds = {padR = {R = 0.4}}")
    L.update(lua.globals().get, S)
    s = [lua.eval("sent")[i + 1] for i in range(lua.eval("#sent"))]
    assert any("look(7,2,1,{{\"disc_brake\",\"disc_RL\"}})" in x for x in s) and any("look(7,3,1,{{\"disc_brake\",\"disc_RR\"}})" in x for x in s), s
    # a reset: every material switch is put back by the game, so the stages go out again
    lua.execute("sent = {}")
    L.onReset()
    L.update(lua.globals().get, S)
    assert lua.eval("#sent") >= 2, "after a reset the worn discs are switched again"
    # the worn look at 0: no change; restore puts every disc back
    lua.execute("sent = {}")
    L.update(lua.globals().get, lua.table(visualWear=0))
    assert all("look(7,%d,0" % wi in "".join(lua.eval("sent")[i + 1] for i in range(lua.eval("#sent"))) for wi in (2, 3)), "visualWear 0: back to the car's own"
    lua.execute("sent = {}")
    L.update(lua.globals().get, S)
    L.restore()
    assert any("look(7,2,0" in lua.eval("sent")[i + 1] for i in range(lua.eval("#sent"))), "restore"
    # a teardown writes nothing: unloading drops the state and sends no material change
    lua.execute("sent = {} conds = {rotor = {FL = 0.2}}")
    L.update(lua.globals().get, S)
    lua.execute("sent = {}")
    L.onExtensionUnloaded()
    assert lua.eval("#sent") == 0 and L.stages() == "", "unload is a state drop, no engine write"
    # the corner of a wheel is its position, the same rule as the apply layer's (wheel names are not used: a mirrored or oddly named car still agrees with the probe)
    lua.execute("wheels.wheels[0].name = 'FR' wheels.wheels[1].name = 'FL' sent = {} conds = {rotor = {FL = 0.5}}")
    L = lua.execute(open(os.path.join(ROOT, "vehicle", "extensions", "slrrWearLook.lua"), encoding="utf8").read())
    L.update(lua.globals().get, S)
    assert "look(7,0,1,{{\"disc_brake\",\"disc_FL\"}})" in lua.eval("sent[1]") and lua.eval("#sent") == 1, "the disc at the front-left position shows front-left wear whatever its wheel is called"
    # game side: glowMap entry only while part wear and its worn look are on; the switch per mesh
    lua.execute("""
      logs, files, cmds = {}, {}, {}
      function log(l, t, m) logs[#logs + 1] = m end
      jsonReadFile = function(f) return files[f] end
      jsonWriteFile = function(f, t) files[f] = t end
      switched, resets, made = {}, {}, 0
      car = {JBeam = 'covet', partConfig = 'x', queueLuaCommand = function(_, c) cmds[#cmds + 1] = c end,
             getSwitchableMaterial = function(_, o, o2, mesh) made = made + 1 return made end,
             switchMaterial = function(_, msc, name) switched[#switched + 1] = {msc, name} end, resetMaterials = function(_, msc) resets[#resets + 1] = msc end}
      be = {getObjectByID = function(_, id) return id == 7 and car or nil end, getPlayerVehicleID = function() return 7 end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
      package.preload['slrr/partwearSchema'] = function() return assert(loadfile('@ROOT@/ge/extensions/slrr/partwearSchema.lua'))() end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    G = lua.execute(open(os.path.join(ROOT, "ge", "extensions", "slrr", "partwear.lua"), encoding="utf8").read())
    G.onExtensionLoaded()
    veh = lua.eval("{}")
    G.onJbeamLoadingPhase2(None, 7, veh)
    assert veh["glowMap"] is None, "part wear off: the car is untouched"
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = true, preset = 'Realistic'}")
    G.reload()
    veh = lua.eval("{}")
    G.onJbeamLoadingPhase2(None, 7, veh)
    gm = veh["glowMap"]["disc_brake"]
    assert gm["on"] == "slrr_disc_brake_worn" and gm["on_intense"] == "slrr_disc_brake_rusty" and gm["off"] == "disc_brake", dict(gm)
    # the discs themselves: the existing brake glow entries get their `off` target from the saved condition, at spawn
    key = G.carKey(7)
    lua.globals().KEY = key
    lua.execute("files['/settings/slrrPartWear_state.json'] = {[KEY] = {rotor = {FL = 0.2, FR = 0.5, RL = 0.9}, padF = {F = 0.9}}}")
    G2 = lua.execute(open(os.path.join(ROOT, "ge", "extensions", "slrr", "partwear.lua"), encoding="utf8").read())
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = true, preset = 'Realistic'}")
    G2.reload()
    veh = lua.eval("{glowMap = {disc_brake_FL = {off = 'disc_brake', on = 'disc_brake_glow'}, disc_brake_FR = {off = 'disc_brake', on = 'disc_brake_glow'}, disc_brake_RL = {off = 'disc_brake', on = 'disc_brake_glow'}, headlight = {off = 'a', on = 'b'}}}")
    G2.onJbeamLoadingPhase2(None, 7, veh)
    gm = veh["glowMap"]
    assert gm["disc_brake_FL"]["off"] == "slrr_disc_brake_rusty" and gm["disc_brake_FR"]["off"] == "slrr_disc_brake_worn", "worn discs: their off material is the worn look"
    assert gm["disc_brake_FL"]["on"] == "disc_brake_glow" and gm["disc_brake_RL"]["off"] == "disc_brake" and gm["headlight"]["off"] == "a", "the glow stays, a good disc and other entries are untouched"
    assert gm["disc_brake"]["on"] == "slrr_disc_brake_worn", "calipers and hubs: the runtime switch entry"
    # another config is another car (found in the game: a respawn with another config has another record): its discs are the car's own, and the first config finds its record again
    lua.execute("car.partConfig = 'a different config'")
    veh = lua.eval("{glowMap = {disc_brake_FL = {off = 'disc_brake', on = 'disc_brake_glow'}}}")
    G2.onJbeamLoadingPhase2(None, 7, veh)
    assert veh["glowMap"]["disc_brake_FL"]["off"] == "disc_brake", "another config: no record, the car's own disc"
    lua.execute("car.partConfig = 'x'")
    veh = lua.eval("{glowMap = {disc_brake_FL = {off = 'disc_brake', on = 'disc_brake_glow'}}}")
    G2.onJbeamLoadingPhase2(None, 7, veh)
    assert veh["glowMap"]["disc_brake_FL"]["off"] == "slrr_disc_brake_rusty", "the same config finds its record"
    # the suspension, frame and exhaust metal: the model's mechanical material gets one entry, its off target from the mean spring and damper condition, for the whole car; one worn
    # corner of eight does not rust the car; an entry the car already carries under that name and a model the survey does not know get none
    def spawn(record, veh_lua="{}"):          # a fresh game side (the store is read once per module) with this record under the car's key, then the car spawns
        lua.execute("files['/settings/slrrPartWear_state.json'] = {[KEY] = %s}" % record)
        G3 = lua.execute(open(os.path.join(ROOT, "ge", "extensions", "slrr", "partwear.lua"), encoding="utf8").read())
        G3.reload()
        veh = lua.eval(veh_lua)
        G3.onJbeamLoadingPhase2(None, 7, veh)
        return veh["glowMap"]
    gm = spawn("{spring = {FL = 0.1, FR = 0.1, RL = 0.1, RR = 0.1}, damper = {FL = 0.1, FR = 0.1, RL = 0.1, RR = 0.1}}")
    m = gm["covet_mechanical"]
    assert m["off"] == "slrr_covet_mechanical_rusty" and m["on"] == m["off"] and m["simpleFunction"] == "slrr_never", dict(m)
    assert gm["disc_brake_FL"] is None, "no disc glow entry was invented"
    gm = spawn("{spring = {FL = 0.1, FR = 0.1, RL = 0.1, RR = 0.1}}", "{glowMap = {disc_brake_FL = {off = 'disc_brake', on = 'disc_brake_glow'}}}")      # springs worn, dampers new: the mean is 0.55
    assert gm["covet_mechanical"]["off"] == "slrr_covet_mechanical_worn" and gm["disc_brake_FL"]["off"] == "disc_brake", "worn metal, the discs untouched"
    assert spawn("{spring = {FL = 0.1}}")["covet_mechanical"] is None, "one worn corner of eight: the car's own metal"
    gm = spawn("{damper = {FL = 0, FR = 0, RL = 0, RR = 0}}", "{glowMap = {covet_mechanical = {off = 'theirs', on = 'x'}}}")
    assert gm["covet_mechanical"]["off"] == "theirs", "an entry the car already has under the material's name is left alone"
    lua.execute("car.JBeam = 'etk800'")
    gm = spawn("{damper = {FL = 0, FR = 0, RL = 0, RR = 0}}")
    assert gm["etk800_mechanical"] is None and gm["covet_mechanical"] is None, "a model outside the survey: nothing"
    lua.execute("car.JBeam = 'covet'")
    # the engine bay: the model's engine material follows the engine condition, the metal row is untouched by it
    gm = spawn("{engine = {all = 0.2}}")
    assert gm["ibishu_engine"]["off"] == "slrr_ibishu_engine_rusty" and gm["ibishu_engine"]["on"] == gm["ibishu_engine"]["off"] and gm["covet_mechanical"] is None, "a worn-out engine: heavy oily grime on the bay, the suspension metal untouched"
    assert spawn("{engine = {all = 0.5}}")["ibishu_engine"]["off"] == "slrr_ibishu_engine_worn", "a tired engine: dust with a little oil"
    gm = spawn("{engine = {all = 0.2}, spring = {FL = 0.1, FR = 0.1, RL = 0.1, RR = 0.1}, damper = {FL = 0.1, FR = 0.1, RL = 0.1, RR = 0.1}}")
    assert gm["ibishu_engine"]["off"] == "slrr_ibishu_engine_rusty" and gm["covet_mechanical"]["off"] == "slrr_covet_mechanical_rusty", "both rows at once"
    lua.execute("car.JBeam = 'pickup'")
    lua.globals().KEY = G.carKey(7)          # (the record key carries the model: a pickup's record is its own)
    assert spawn("{engine = {all = 0.1}}")["gavril_v8"]["off"] == "slrr_gavril_v8_rusty", "the pickup's bay material"
    lua.execute("car.JBeam = 'covet'")
    lua.globals().KEY = key
    lua.execute("files['/settings/slrrPartWear_state.json'] = {}")
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = true, preset = 'Realistic', visualWear = 0}")
    G.reload()
    veh = lua.eval("{}")
    G.onJbeamLoadingPhase2(None, 7, veh)
    assert veh["glowMap"] is None, "worn look at 0: no glowMap entry"
    G.look(7, 0, 1, lua.eval("{{'disc_brake', 'disc_FL'}}"))
    G.look(7, 0, 2, lua.eval("{{'disc_brake', 'disc_FL'}}"))
    G.look(7, 0, 0, lua.eval("{{'disc_brake', 'disc_FL'}}"))
    sw = [lua.eval("switched")[i + 1] for i in range(3 - 1)]
    assert sw[0][2] == "slrr_disc_brake_worn" and sw[1][2] == "slrr_disc_brake_rusty" and lua.eval("made") == 1 and lua.eval("#resets") == 1, "one switch per mesh, stages worn, rusty, own"
    print("wear disc look ok: stages from disc and pads, per wheel by node, no repeat, reset, restore; glowMap only while on; switch per mesh")


if __name__ == "__main__":
    main()
