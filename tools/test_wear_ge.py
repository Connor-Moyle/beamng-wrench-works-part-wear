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
      paintCalls, glassCalls, wiperCalls = {}, {}, {}
      carSurfaceFx = {setPaintWear = function(id, t) paintCalls[#paintCalls + 1] = {id = id, fade = t.fade, rust = t.rust} end,
                      setGlassWear = function(id, t) glassCalls[#glassCalls + 1] = {id = id, pits = t.pits, haze = t.haze} end,
                      setWiperWear = function(id, f) wiperCalls[#wiperCalls + 1] = {id = id, factor = f or -1} end}
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
    # gameplay presets: looks are graphics, the rest gameplay; every preset value has the row's type and lies inside its range
    for i in range(len(reg["fields"])):
        f = reg["fields"][i + 1]
        assert f["scope"] == ("graphics" if f["tab"] == "looks" else "gameplay"), (f["id"], f["scope"])
        gp = f["gameplay"]
        if gp is None:
            continue
        for name in ("easy", "hardcore", "realistic", "sandbox"):
            v = gp[name]
            if v is None:
                continue
            assert name in ("easy", "hardcore", "realistic", "sandbox")
            if f["type"] == "bool":
                assert isinstance(v, bool), (f["id"], name, v)
            else:
                assert f["min"] <= v <= f["max"], (f["id"], name, v, f["min"], f["max"])
    f0 = reg["fields"][1]
    assert f0["id"] == "wearEnabled" and f0["default"] is False and f0["feature"] is True, "the master switch is first, off by default"
    G.attach(7)
    assert lua.eval("#cmds") == 0, "attach does nothing while off"
    # on: the player's car gets the extensions and the settings; a saved state comes with them
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = true, preset = 'Realistic'}")
    G.reload()
    c = cmds(lua)
    assert not any("setExtensionUnloadMode" in x for x in c), "the car's Lua has no setExtensionUnloadMode (game side only): the whole command would stop there (found in the game)"
    assert any("extensions.load('slrrWear')" in x for x in c) and any("setSettings" in x and "[\"wearEnabled\"]=true" in x for x in c), c
    assert any("restoreSnapshot" in x and '"damper"' in x and "0.4" in x for x in c), "the saved condition goes to the car"
    # the career's busy state (a race, a job, a chase) is told to the player's car, once per change; free roam and an idle career are not busy
    lua.execute("cmds = {} sl_career = {isActive = function() return false end, freeToStart = function() return 'no career' end}")
    G.onUpdate(2)
    assert not any("setRacing" in x for x in cmds(lua)) or any("setRacing(false)" in x for x in cmds(lua)), "no career: not busy"
    lua.execute("cmds = {} sl_career.isActive = function() return true end sl_career.freeToStart = function() return 'a race is on' end")
    G.onUpdate(2)
    assert any("setRacing(true)" in x for x in cmds(lua)), cmds(lua)
    lua.execute("cmds = {}")
    G.onUpdate(2)
    assert not any("setRacing" in x for x in cmds(lua)), "told once per change"
    lua.execute("cmds = {} sl_career.freeToStart = function() return nil end")
    G.onUpdate(2)
    assert any("setRacing(false)" in x for x in cmds(lua)), "free again"
    lua.execute("sl_career = nil")
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
    # inventory items: a battery swap resets the battery condition and charges the game's battery; oil resets the oil condition; coolant refills; bad input is refused
    lua.execute("cmds = {}")
    ok, why = G.useItem(7, "battery", lua.eval("{charge = 0.5}"))
    sent = " ".join(cmds(lua))
    assert ok and 'slrrWear.setCondition("battery", "all", 1)' in sent and "setRemainingRatio, s, 0.500000" in sent, sent
    assert 's.type == "electricBattery"' in sent, "only the traction battery is charged: a fuel tank under useItem('battery') stays as it is"
    # run the car-side code against stand-in storages: the fuel tank and the N2O tank are not touched, the battery is
    lua.execute("""
      local function store(t, r) return {type = t, ratio = r, setRemainingRatio = function(s, x) s.ratio = x end} end
      tank, n2o, batt = store('fuelTank', 0.2), store('n2oTank', 0.4), store('electricBattery', 0.1)
      energyStorage = {getStorages = function() return {tank, n2o, batt} end}
    """)
    lua.globals().CODE = [c for c in cmds(lua) if "setRemainingRatio" in c][0]
    lua.execute("assert(load(CODE))()")
    assert lua.eval("tank.ratio") == 0.2 and lua.eval("n2o.ratio") == 0.4 and lua.eval("batt.ratio") == 0.5, "fuel and N2O unchanged, the traction battery set"
    lua.execute("cmds = {}")
    assert G.useItem(7, "oil", None)[0] and 'slrrWear.setCondition("oil", "all", 1)' in " ".join(cmds(lua))
    lua.execute("cmds = {}")
    assert G.useItem(7, "coolant", None)[0] and "setPartConditionRadiator" in " ".join(cmds(lua))
    assert G.useItem(7, "jerry", None)[0] is False and G.useItem(99, "oil", None)[0] is False
    # off again: the car is told to switch off
    # a part swap in freeroam respawns the car with a changed part config: the car keeps its record (no free repair of the other parts); a config loaded over the car is another car
    k0 = G.carKey(7)
    G.onPartsTreeConfigChanged()
    lua.execute("car.partConfig = '{\"partsTree\":{\"swapped\":true}}'")
    assert G.carKey(7) == k0, "a part swap keeps the car's record"
    G.onVehicleReplaced(7)
    assert G.carKey(7) != k0, "another config loaded over the car is another car"
    lua.execute("car.partConfig = 'vehicles/covet/base.pc'")
    # a new part in a slot is new, and only that slot's kinds and corners: swap the front coilovers, the rear dampers and the front pads keep their wear
    lua.execute("""
      local old = {children = {covet_coilover_F = {chosenPartName = 'cf1'}, covet_coilover_R = {chosenPartName = 'cr1'}, brakepad_F = {chosenPartName = 'pf1'}, covet_hood = {chosenPartName = 'h1'}}}
      oldTree = old
      treeNow = old
      core_vehicle_partmgmt = {getConfig = function() return {partsTree = treeNow} end}
      swapNew = {children = {covet_coilover_F = {chosenPartName = 'cf2'}, covet_coilover_R = {chosenPartName = 'cr1'}, brakepad_F = {chosenPartName = 'pf1'}, covet_hood = {chosenPartName = ''}}}
      cmds = {}""")
    # the game's parts tree is not the new car's right after a spawn (80's run: it still held the car that was replaced, and a swap then reset the wrong parts): the parts are taken a few
    # seconds after the attach, and the game edits its own tree in place, so a swap is only seen against what was remembered then
    lua.execute("treeNow = {children = {covet_coilover_F = {chosenPartName = 'stale'}, brakepad_F = {chosenPartName = 'stale'}}}")
    G.attach(7)
    G.onUpdate(1)                                  # (inside the settling time: nothing is taken)
    lua.execute("treeNow = oldTree")
    G.onUpdate(6)                                  # (the parts as the game reports them now)
    lua.execute("treeNow = swapNew")      # (and by the time the swap is announced the game's own tree already holds the new parts)
    lua.execute("cmds = {}")
    G.onReport(7, lua.eval("{damper = {FL = 0.3, FR = 0.3, RL = 0.25, RR = 0.3}, padF = {F = 0.2}}"))
    lua.execute("shelfHooks = {} extensions = {hook = function(n, ...) shelfHooks[#shelfHooks + 1] = {n, ...} end}")
    G.onPartsTreeConfigChanged(lua.eval("swapNew"))
    h = lua.eval("shelfHooks")
    assert len(h) == 1 and h[1][1] == "onSlrrPartWearSwapped", "the swap announces the parts that came off"
    ch = h[1][3][1]
    assert ch["slot"] == "covet_coilover_F" and ch["oldPart"] == "cf1" and ch["newPart"] == "cf2", dict(ch)
    assert abs(ch["record"]["condition"] - 0.3) < 1e-9 and len(ch["record"]["parts"]) == 2, "the old part's damper wear, before it was set back to new"
    sent = " ".join(cmds(lua))
    for want in ('("damper", "FL", 1)', '("damper", "FR", 1)', '("spring", "FL", 1)', '("spring", "FR", 1)'):
        assert want in sent, ("the swapped front coilovers are new", want, sent)
    assert any("slots changed: covet_coilover_F" in m for m in lua.eval("logs").values()) and any("parts remembered: 4 slots" in m for m in lua.eval("logs").values()), "the log says what the snapshot saw and which slots the swap changed"
    for no in ('"RL"', '"RR"', 'padF'):
        assert no not in sent, ("the rest of the car keeps its wear", no, sent)
    # the old car reports its old wear once more before it is replaced: the swapped corners stay new in the record, the rest keeps its wear
    G.onReport(7, lua.eval("{damper = {FL = 0.3, FR = 0.3, RL = 0.25, RR = 0.3}, padF = {F = 0.2}}"))
    lua.execute("treeNow = swapNew")      # (the game reports the new parts after the respawn)
    G.onVehicleSpawned(7)
    G.onUpdate(11)
    st = lua.eval("files['/settings/slrrPartWear_state.json'][KEY]")
    assert st["damper"]["FL"] is None and st["damper"]["FR"] is None, "the swapped front shock absorbers are new in the record"
    assert st["damper"]["RL"] == 0.25 and st["damper"]["RR"] == 0.3 and st["padF"]["F"] == 0.2, "the other parts keep their wear"
    G.onReport(7, lua.eval("{paint = {all = 0.1}}"))      # (the record as it was before this block)
    lua.execute("cmds = {}")
    G.onPartsTreeConfigChanged(lua.eval("swapNew"))
    assert not cmds(lua), "the same parts again change nothing"
    G.onVehicleReplaced(7)      # (the pin of the swap ends)
    # the shelf: recordOf reads the wear of one slot's part (nil for a slot with no wear kind), restore writes it back, recondition only raises
    G.onReport(7, lua.eval("{damper = {FL = 0.3, FR = 0.4}, spring = {FL = 0.5}, padF = {F = 0.2}}"))
    r = G.recordOf(7, "covet_coilover_F")
    assert abs(r["condition"] - 0.3) < 1e-9 and len(r["parts"]) == 3, "worst of its pairs, only stored ones"
    assert G.recordOf(7, "covet_hood") is None and G.recordOf(7, 5) is None
    assert G.recordOf(7, "covet_coilover_R")["condition"] == 1 and len(G.recordOf(7, "covet_coilover_R")["parts"]) == 0, "nothing stored: new"
    lua.execute("cmds = {}")
    assert G.recondition(7, "covet_coilover_F", 0.95) is True
    r = G.recordOf(7, "covet_coilover_F")
    assert abs(r["condition"] - 0.95) < 1e-9 and any('setCondition("damper", "FL", 0.95)' in x for x in cmds(lua)), "recondition raised the pairs and told the car"
    assert G.recondition(7, "covet_coilover_F", 7) is True and G.recordOf(7, "covet_coilover_F")["condition"] == 1, "a condition above 1 is held to 1: the part is new"
    assert G.recondition(7, "covet_coilover_F", "x") is False and G.recondition(7, "covet_coilover_F", 0/0 if False else float("nan")) is False and G.recondition(7, "covet_hood", 0.9) is False, "not a number, not a wear slot"
    G.restore(7, "covet_coilover_F", lua.eval("{parts = {{kind = 'damper', corner = 'FL', c = 0.95}, {kind = 'damper', corner = 'FR', c = 0.95}, {kind = 'spring', corner = 'FL', c = 0.95}}}"))
    assert G.recondition(7, "covet_coilover_F", 0.5) is True and abs(G.recordOf(7, "covet_coilover_F")["condition"] - 0.95) < 1e-9, "never worse"
    rec = lua.eval("{condition = 0.4, parts = {{kind = 'damper', corner = 'FL', c = 0.4}, {kind = 'padF', corner = 'F', c = 0.1}, {kind = 'damper', corner = 'ZZ', c = 0.1}}}")
    assert G.restore(7, "covet_coilover_F", rec) is True
    r = G.recordOf(7, "covet_coilover_F")
    assert abs(r["condition"] - 0.4) < 1e-9 and len(r["parts"]) == 3, "restored; the front pads and the made-up corner are not this slot's: ignored"
    assert G.restore(7, "covet_coilover_F", lua.eval("{}")) is False and G.restore(7, "covet_coilover_F", None) is False
    # the windows and the wiper blades follow the stored glass and wiper conditions (Car Surface FX's hooks), and a new car clears them
    G.onReport(7, lua.eval("{glass = {all = 0.2}, wipers = {all = 0.3}}"))
    gc, wc = lua.eval("glassCalls[#glassCalls]"), lua.eval("wiperCalls[#wiperCalls]")
    assert gc["pits"] > 0.3 and gc["haze"] > 0.2 and 0.5 <= wc["factor"] < 1, ("worn glass pits and hazes, worn blades clear less", dict(gc), dict(wc))
    G.onReport(7, lua.eval("{glass = {all = 1}}"))
    gc, wc = lua.eval("glassCalls[#glassCalls]"), lua.eval("wiperCalls[#wiperCalls]")
    assert gc["pits"] == 0 and gc["haze"] == 0 and wc["factor"] == 1, "new glass and new blades: cleared"
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
    # Wrench Works garage: worn parts are listed with their condition and a price, a click pays and sets the part back to new; nothing while part wear is off
    G.setCarKey(7, key)
    lua.execute("paid = {} garageParts = {getMoney = function() return money end, changeMoney = function(a, l) if money + a < 0 then return false end money = money + a paid[#paid + 1] = -a return true end} money = 1000 "
                "package.preload['slrr/garageParts'] = function() return garageParts end sl_career = nil career_career = nil")
    G.reload()
    G.onReport(7, lua.eval("{damper = {FL = 0.2}, padF = {F = 0.5}, spring = {RR = 0.95}}"))
    lua.execute("list = {}")
    G.onWrenchWorksServices(lua.eval("list"), 7)
    n = lua.eval("#list")
    assert n == 2, ("two worn parts are offered, the nearly new spring is not", n)
    e1, e2 = lua.eval("list[1]"), lua.eval("list[2]")
    assert e1["id"] == "pw:damper:FL" and e1["label"] == "Replace shock absorber front left" and e1["price"] == 129 and "Failing" in e1["desc"], dict(e1)
    assert e2["id"] == "pw:padF:F" and e2["label"] == "Replace front brake pads" and e2["price"] == 58, dict(e2)
    G.onWrenchWorksService("pw:damper:FL", 7)
    assert lua.eval("money") == 871 and lua.eval("#paid") == 1, "the price is paid through the garage"
    lua.execute("list = {}")
    G.onWrenchWorksService("pw:damper:FL", 7)
    G.onWrenchWorksServices(lua.eval("list"), 7)
    assert lua.eval("#list") == 1 and lua.eval("#paid") == 1, "repaired: not offered again, not charged twice"
    # freeroam records untouched for 30 days are dropped at load; career records are kept; a record without a day starts counting
    G.setScope("free")
    G.reload()
    G.setScope("sl2"); G.conditionsOfKey("x")       # (the store in memory is written and dropped when the scope changes; the preset file below is read when we come back)
    lua.execute("files['/settings/slrrPartWear_state.json'] = {old = {damper = {FL = 0.5}}, fresh = {damper = {FL = 0.5}}, nodate = {damper = {FL = 0.5}}, "
                "__seen = {old = math.floor(os.time() / 86400) - 31, fresh = math.floor(os.time() / 86400) - 29, gone = 5}}")
    G.setScope("free")
    G.setCarKey(7, "fresh")
    assert G.conditionsOfKey("old")["parts"][1] is None and G.conditionsOfKey("fresh")["parts"][1] is not None and G.conditionsOfKey("nodate")["parts"][1] is not None, "old freeroam record pruned, the others kept"
    assert lua.eval("files['/settings/slrrPartWear_state.json'].__seen.gone") is None and lua.eval("files['/settings/slrrPartWear_state.json'].__seen.nodate") is not None
    G.onReport(7, lua.eval("{damper = {FL = 0.1}}"))
    assert lua.eval("files['/settings/slrrPartWear_state.json'].__seen.fresh") >= lua.eval("math.floor(os.time() / 86400)")
    # the career's wear rate: sent with the settings to cars that exist and cars that come later; not a number above 0: ignored; not touching stored conditions
    lua.execute("cmds = {}")
    assert G.getWearRate() == 1 and G.setWearRate(2) == 2 and G.getWearRate() == 2
    assert any("[\"wearRate\"]=2," in x.replace(" ", "") for x in cmds(lua)), cmds(lua)
    assert G.setWearRate(0) == 2 and G.setWearRate(-1) == 2 and G.setWearRate("x") == 2 and G.setWearRate(0/0 if False else float("nan")) == 2
    assert G.setWearRate(1000) == 20
    lua.execute("cmds = {}")
    G.attach(7)
    assert any("[\"wearRate\"]=20," in x.replace(" ", "") for x in cmds(lua)), "a car spawned later gets the rate"
    G.onUpdate(100)      # (the store is written)
    assert lua.eval("files['/settings/slrrPartWear.json'].wearRate") is None and not lua.eval("(function() for _, f in pairs(files) do if type(f) == 'table' and f.wearRate ~= nil then return true end end end)()"), "the rate is never saved"
    G.setWearRate(1)
    # a record handed to a car at spawn counts as used, even before the car has reported
    lua.execute("files['/settings/slrrPartWear_state.json'].nodate.damper = {FL = 0.4} files['/settings/slrrPartWear_state.json'].__seen.nodate = math.floor(os.time() / 86400) - 29")
    G.setCarKey(7, "nodate")
    G.attach(7)
    assert lua.eval("files['/settings/slrrPartWear_state.json'].__seen.nodate") >= lua.eval("math.floor(os.time() / 86400)"), "a record given to a car is refreshed"
    G.setCarKey(7, key)
    # the read-only view for other mods: sorted rows with a stable id and a section; nil when the car is not watched or wear is off
    G.onReport(7, lua.eval("{damper = {FL = 0.2}, padF = {F = 0.5}, exhaust = {all = 0.7}}"))
    cv = lua.eval("(function(c) local o = {} for i, p in ipairs(c.parts) do o[i] = p.id .. '/' .. p.section .. '/' .. p.condition end return table.concat(o, ' ') end)")
    assert cv(G.conditionsOfKey(key)) == "damper:FL/suspension/0.2 exhaust:all/exhaust/0.7 padF:F/brakes/0.5", cv(G.conditionsOfKey(key))
    assert G.conditionsOf(99) is None and G.conditionsOfKey(None) is None
    assert len(G.conditionsOfKey("no such car")["parts"]) == 0
    lua.execute("money = 10 list = {}")
    G.onWrenchWorksServices(lua.eval("list"), 7)
    assert lua.eval("list[1].disabled") is True, "too little money: disabled"
    G.onWrenchWorksService("pw:padF:F", 7)
    assert lua.eval("#paid") == 1, "not paid, not repaired"
    lua.execute("files['/settings/slrrPartWear.json'] = {wearEnabled = false} list = {}")
    G.reload()
    G.onWrenchWorksServices(lua.eval("list"), 7)
    assert lua.eval("#list") == 0, "part wear off: the garage is as it was"
    # a NaN or inf condition never reaches the car's command
    G.onReport(7, lua.eval("{damper = {FL = 0/0, FR = 1/0}}"))
    G.repair(7, "spring", None)
    lua.execute("cmds = {}")
    G.reload()
    assert all("nan" not in x.lower() and "inf" not in x.lower() for x in cmds(lua)), cmds(lua)
    print("wear game side ok: off by default, page registered, cars get extensions + settings + saved state, reports stored, repair, off")


if __name__ == "__main__":
    main()
