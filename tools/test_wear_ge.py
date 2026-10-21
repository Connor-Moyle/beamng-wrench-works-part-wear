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
      car = {JBeam = 'covet', partConfig = 'vehicles/covet/base.pc', queueLuaCommand = function(_, c) cmds[#cmds + 1] = c end}
      be = {getObjectByID = function(_, id) return id == 7 and car or nil end, getPlayerVehicleID = function() return 7 end}
      paintCalls = {}
      carSurfaceFx = {setPaintWear = function(id, t) paintCalls[#paintCalls + 1] = {id = id, fade = t.fade, rust = t.rust} end}
      slrr_settings = {register = function(s) registered = s end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
      package.preload['slrr/partwearSchema'] = function() return assert(loadfile('@ROOT@/ge/extensions/slrr/partwearSchema.lua'))() end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    G = lua.execute(open(os.path.join(ROOT, "ge", "extensions", "slrr", "partwear.lua"), encoding="utf8").read())
    key = G.carKey(7)
    assert key.startswith("covet|") and len(key.split("|")) == 3, key
    lua.globals().KEY = key
    lua.execute("files['/settings/slrrPartWear_state.json'] = {[KEY] = {damper = {FL = 0.4}}}")
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
    st = lua.eval("files['/settings/slrrPartWear_state.json'][KEY]")
    assert st["spring"]["RR"] == 0.7, "the report is saved"
    # paint wear goes to Car Surface FX as the four layers of the stored paint condition
    G.onReport(7, lua.eval("{paint = {all = 0.1}}"))
    pc = lua.eval("paintCalls[#paintCalls]")
    assert pc["id"] == 7 and pc["fade"] > 0.8 and pc["rust"] > 0.5, "worn paint: fade and rust layers"
    # repair: one part back to new, in the store and in the car
    lua.execute("cmds = {}")
    G.repair(7, "spring", "RR")
    assert cmds(lua)[0].startswith('slrrWear.setCondition("spring", "RR", 1)'), cmds(lua)
    # off again: the car is told to switch off
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = false} cmds = {}")
    G.reload()
    assert "wearEnabled=false" in cmds(lua)[0] and "off" in G.status()
    pc = lua.eval("paintCalls[#paintCalls]")
    assert pc["fade"] == 0 and pc["rust"] == 0, "off: the paint look is cleared"
    # the key hashes the whole part config: two configs that start alike are two records, the same config is one
    lua.execute("car.partConfig = string.rep('x', 300) .. 'A'")
    ka = G.carKey(7)
    lua.execute("car.partConfig = string.rep('x', 300) .. 'B'")
    kb = G.carKey(7)
    assert ka != kb and ka.split("|")[0] == kb.split("|")[0], "configs that share their first 200 characters get different keys"
    # a career slot has its own file: the freeroam record is not seen in it and its file is not written by the slot
    lua.execute("car.partConfig = 'vehicles/covet/base.pc' sl_career = {isActive = function() return true end, getSlot = function() return 2 end}")
    G.reload()
    assert G.scope() == "sl2"
    G.setCarKey(7, key)      # (an explicit key wins over the car id)
    G.onReport(7, lua.eval("{damper = {RR = 0.2}}"))
    G.onUpdate(11)
    assert lua.eval("files['/settings/slrrPartWear_state_sl2.json'][KEY].damper.RR") == 0.2
    assert lua.eval("(files['/settings/slrrPartWear_state.json'][KEY].damper or {}).RR") is None, "freeroam untouched by a career slot"
    lua.execute("sl_career = {isActive = function() return true end, getSlot = function() return 3 end}")
    G.onReport(7, lua.eval("{spring = {FL = 0.9}}"))
    assert G.scope() == "sl3" and lua.eval("files['/settings/slrrPartWear_state_sl3.json'] == nil or files['/settings/slrrPartWear_state_sl3.json'][KEY].damper == nil"), "slot 3 starts empty"
    G.setCarKey(7, None)
    # Street Legal's career: the key is the player's car id, so two identical cars never share wear; a car with no id yet stores and restores nothing until it has one
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = true, preset = 'Realistic'}")
    lua.execute("sl_career = {isActive = function() return true end, getSlot = function() return 2 end} "
                "fleet = {} sl_fleet = {carOfVehicle = function(v) return fleet[v] end} "
                "car2 = {JBeam = 'covet', partConfig = 'vehicles/covet/base.pc', queueLuaCommand = function(_, c) cmds[#cmds + 1] = c end} "
                "be.getObjectByID = function(_, i) if i == 7 then return car elseif i == 8 then return car2 end end")
    G.reload()
    G.attach(8)
    lua.execute("cmds = {}")
    G.onReport(8, lua.eval("{damper = {FL = 0.1}}"))
    lua.execute("fleet[7] = 11 fleet[8] = 12")
    G.onReport(7, lua.eval("{damper = {FL = 0.6}}"))
    G.onUpdate(2)      # the key of car 8 is known now: it is given its (empty) record
    G.onReport(8, lua.eval("{damper = {FL = 0.3}}"))
    G.onUpdate(11)
    sl2 = lua.eval("(function() local t = {} for k, v in pairs(files['/settings/slrrPartWear_state_sl2.json']) do t[#t + 1] = k end table.sort(t) return table.concat(t, ',') end)()")
    assert "slcar11" in sl2 and "slcar12" in sl2 and lua.eval("files['/settings/slrrPartWear_state_sl2.json'].slcar11.damper.FL") == 0.6 and lua.eval("files['/settings/slrrPartWear_state_sl2.json'].slcar12.damper.FL") == 0.3, sl2
    assert lua.eval("files['/settings/slrrPartWear_state_sl2.json'].slcar12.damper.FL ~= 0.1"), "the report from a car with no id was not stored"
    # the game's career: the inventory id
    lua.execute("sl_career = nil career_career = {isActive = function() return true end} career_modules_inventory = {getInventoryIdFromVehicleId = function(v) return v == 7 and 41 or nil end}")
    G.reload()
    assert G.scope() == "stock"
    G.onReport(7, lua.eval("{spring = {RR = 0.5}}"))
    G.onUpdate(11)
    assert lua.eval("files['/settings/slrrPartWear_state_stock.json'].inv41.spring.RR") == 0.5
    lua.execute("career_career = nil career_modules_inventory = nil sl_fleet = nil")
    # a NaN or inf condition never reaches the car's command
    G.onReport(7, lua.eval("{damper = {FL = 0/0, FR = 1/0}}"))
    G.repair(7, "spring", None)
    lua.execute("cmds = {}")
    G.reload()
    assert all("nan" not in x.lower() and "inf" not in x.lower() for x in cmds(lua)), cmds(lua)
    print("wear game side ok: off by default, page registered, cars get extensions + settings + saved state, reports stored, repair, off")


if __name__ == "__main__":
    main()
