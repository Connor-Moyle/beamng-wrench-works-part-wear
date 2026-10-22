"""Random failures on the vehicle side (slrrWear.lua with slrrFailRules): a worn engine on a hot, revving, driving car gets its warning and then the game's own head-gasket flag; a cancel when
stopped; a broken driveshaft; a plain condition drop; nothing with the setting off or while racing with the never-racing switch; the old roll no longer owns the covered kinds.

    python tools/test_wear_failapply.py
"""
import os
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "mod", "lua")


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
      logs, hooks, flags, broken, locked, msgs = {}, {}, {}, {}, 0, {}
      function log(l, t, m) logs[#logs + 1] = m end
      guihooks = {message = function(t) msgs[#msgs + 1] = t end}
      electrics = {values = {wheelspeed = 20, rpm = 4000, watertemp = 120, fuel = 0.5}}
      obj = {getId = function() return 5 end, queueGameEngineLua = function(_, c) hooks[#hooks + 1] = c end}
      slrrWearProbe = {}
      for _, k in ipairs({'damper', 'spring', 'rotor', 'pads', 'engine', 'clutch', 'gearbox', 'diff', 'cv', 'turbo', 'radiator', 'ignition', 'oil', 'swaybar', 'bushing', 'bearing', 'fluid', 'master', 'fuel', 'cat', 'intercooler', 'battery', 'steering', 'flywheel', 'lights', 'alternator', 'exhaust', 'body', 'glass', 'seat', 'door', 'setSettings', 'clear'}) do
        slrrWearProbe[k] = function() end
      end
      slrrWearProbe.detect = function() return 4, 4, 4 end
      extensions = {load = function() end}
      local eng = {maxRPM = 6000, lockUp = function() locked = locked + 1 end,
                   thermals = {setPartConditionThermals = function(_, tbl) for k in pairs(tbl) do flags[#flags + 1] = k end end}}
      local shaft = {type = 'shaft', onBreak = function(d) d.isBroken = true broken[#broken + 1] = 'shaft' end}
      powertrain = {getDevice = function() return eng end, getDevices = function() return {eng = eng, shaft = shaft} end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
      package.preload['slrrFailRules'] = function() return assert(loadfile('@ROOT@/common/slrrFailRules.lua'))() end
      function run(seconds) for _ = 1, seconds * 2 do W_.updateGFX(0.5) end end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    W = lua.execute(open(os.path.join(ROOT, "vehicle", "extensions", "slrrWear.lua"), encoding="utf8").read())
    lua.globals().W_ = W
    W.setRandom(lua.eval("function() return 0 end"))       # every roll succeeds
    S = dict(wearEnabled=True, lifeScale=0.0001, abuseScale=0, ageScale=0, effectStrength=1, springSagMax=25, springRateLoss=0.05, damperLossMax=0.8,
             brakeTorqueLoss=0.08, enginePowerLoss=0.15, failures=True, failureRate=3, judder=1, visualWear=1)
    W.setSettings(lua.table(**S))
    W.setCondition("engine", "all", 0.05)
    W.setCondition("oil", "all", 0.05)
    W.setCondition("radiator", "all", 0.05)
    # a minute of driving rolls: a warning first (the temperature is creeping up), then, after the warning time, the game's flag
    lua.execute("run(61)")
    assert any("temperature is creeping" in m for m in lua.eval("msgs").values()), list(lua.eval("msgs").values())
    assert lua.eval("#flags") == 0, "nothing applied during the warning"
    lua.execute("run(100)")
    assert "headGasketBlown" in lua.eval("flags").values(), list(lua.eval("flags").values())
    assert any("onSlrrPartWearFailure" in h and "headGasket" in h for h in lua.eval("hooks").values()), list(lua.eval("hooks").values())
    # a driveshaft: the game's own onBreak on a shaft device
    W.setCondition("cv", "F", 0.05)
    lua.execute("run(61) run(40)")
    assert list(lua.eval("broken").values()) == ["shaft"], list(lua.eval("broken").values())
    # the old roll no longer drops a covered kind on its own: the clutch is covered, and with every roll succeeding it drops only through the rules (warning 0 = at once)
    W.setCondition("clutch", "all", 0.05)
    lua.execute("run(61)")
    assert W.getCondition("clutch", "all") <= 0.08
    # stopped with the engine off cancels a pending warning
    W.setCondition("fuel", "all", 0.05)
    for _ in range(130):
        lua.execute("run(1)")
        if any("stuttering under load" in m for m in lua.eval("msgs").values()):
            break
    assert any("stuttering under load" in m for m in lua.eval("msgs").values()), "the fuel pump warns"
    lua.execute("electrics.values.rpm = 0 electrics.values.wheelspeed = 0 run(12)")
    assert any("noise has stopped" in m for m in lua.eval("msgs").values()), "stopping cancels the warning"
    assert W.getCondition("fuel", "all") > 0.04, "a cancelled failure drops nothing more than the wear"
    # hard landings are counted over the last minute and handed to the rules (the car's vertical speed falls, then stops hard)
    lua.execute("vz = 0 obj.getVelocity = function() return {x = 0, y = 0, z = vz} end")
    lua.execute("vz = -6 W_.updateGFX(0.016) vz = 1 W_.updateGFX(0.016) vz = 0 run(1)")
    # off: nothing; racing with the never-racing switch: nothing
    lua.execute("msgs = {} flags = {} electrics.values.rpm = 4000 electrics.values.wheelspeed = 20")
    W.setSettings(lua.table(**dict(S, failures=False)))
    W.setCondition("alternator", "all", 0.05)
    lua.execute("run(200)")
    assert lua.eval("#msgs") == 0, "failures off: no messages"
    W.setSettings(lua.table(**dict(S, failureNeverRacing=True)))
    W.setRacing(True)
    lua.execute("run(200)")
    assert lua.eval("#msgs") == 0, "never during a race"
    print("wear failures (vehicle side) ok: warning then the game's flag, driveshaft, plain drop, cancel when stopped, off, never racing")


if __name__ == "__main__":
    main()
