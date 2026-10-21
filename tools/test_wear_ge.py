"""The game side of part wear (mod/lua/ge/extensions/slrr/partwear.lua) with mocks: off until the settings say on, the cars get the extensions, the settings and their saved conditions,
a report is stored and saved, a repair clears a part, and the Mods page schema registers.

    python tools/test_wear_ge.py
"""
import os
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "mod", "lua")


def cmds(lua):
    return [lua.eval("cmds")[i + 1] for i in range(lua.eval("#cmds"))]


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
      logs, cmds, files, registered = {}, {}, {}, nil
      function log(l, t, m) logs[#logs + 1] = m end
      jsonReadFile = function(f) return files[f] end
      jsonWriteFile = function(f, t) files[f] = t end
      local car = {JBeam = 'covet', partConfig = 'vehicles/covet/base.pc', queueLuaCommand = function(_, c) cmds[#cmds + 1] = c end}
      be = {getObjectByID = function(_, id) return id == 7 and car or nil end, getPlayerVehicleID = function() return 7 end}
      slrr_settings = {register = function(s) registered = s end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
      package.preload['slrr/partwearSchema'] = function() return assert(loadfile('@ROOT@/ge/extensions/slrr/partwearSchema.lua'))() end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    lua.execute("files['/settings/slrrPartWear_state.json'] = {['covet|vehicles/covet/base.pc'] = {damper = {FL = 0.4}}}")
    G = lua.execute(open(os.path.join(ROOT, "ge", "extensions", "slrr", "partwear.lua"), encoding="utf8").read())
    G.onExtensionLoaded()
    assert "off" in G.status() and lua.eval("#cmds") == 0, "off by default: no car gets anything"
    reg = lua.eval("registered")
    assert reg["mod"] == "slrr_partwear" and len(reg["fields"]) >= 10, "the Mods page is registered"
    f0 = reg["fields"][1]
    assert f0["id"] == "wearEnabled" and f0["default"] is False and f0["feature"] is True, "the master switch is first, off by default"
    G.attach(7)
    assert lua.eval("#cmds") == 0, "attach does nothing while off"
    # on: the player's car gets the extensions and the settings; a saved state comes with them
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = true, preset = 'Realistic'}")
    G.reload()
    c = cmds(lua)
    assert any("extensions.load('slrrWear')" in x for x in c) and any("setSettings" in x and "[\"wearEnabled\"]=true" in x for x in c), c
    assert any("restoreSnapshot" in x and '"damper"' in x and "0.4" in x for x in c), "the saved condition goes to the car"
    # a report is stored and saved after a while
    G.onReport(7, lua.eval("{spring = {RR = 0.7}}"))
    G.onUpdate(11)
    st = lua.eval("files['/settings/slrrPartWear_state.json']['covet|vehicles/covet/base.pc']")
    assert st["spring"]["RR"] == 0.7, "the report is saved"
    # repair: one part back to new, in the store and in the car
    lua.execute("cmds = {}")
    G.repair(7, "spring", "RR")
    assert cmds(lua)[0].startswith('slrrWear.setCondition("spring", "RR", 1)'), cmds(lua)
    # off again: the car is told to switch off
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = false} cmds = {}")
    G.reload()
    assert "wearEnabled=false" in cmds(lua)[0] and "off" in G.status()
    print("wear game side ok: off by default, page registered, cars get extensions + settings + saved state, reports stored, repair, off")


if __name__ == "__main__":
    main()
