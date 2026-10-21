"""The vehicle-side state of part wear (mod/lua/vehicle/extensions/slrrWear.lua) against a stand-in apply layer: off by default, wear by distance and hard stops,
changes handed on only when they are at least 0.01, the snapshot and its restore (string keys), reports to the game side, off puts everything back.

    python tools/test_wear_state.py
"""
import os
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "mod", "lua")


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
      logs, calls, sent = {}, {}, {}
      function log(l, t, m) logs[#logs + 1] = m end
      electrics = {values = {wheelspeed = 0}}
      obj = {getId = function() return 5 end, queueGameEngineLua = function(_, c) sent[#sent + 1] = c end}
      slrrWearProbe = {}
      for _, k in ipairs({'damper', 'spring', 'rotor', 'pads', 'engine', 'clutch', 'setSettings', 'clear'}) do
        slrrWearProbe[k] = function(...) calls[#calls + 1] = {k, ...} end
      end
      extensions = {load = function() end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    W = lua.execute(open(os.path.join(ROOT, "vehicle", "extensions", "slrrWear.lua"), encoding="utf8").read())
    lua.execute("function run(n, v, dt) for _ = 1, n do electrics.values.wheelspeed = v W_.updateGFX(dt or 0.5) end end")
    lua.globals().W_ = W
    # off by default: nothing wears, nothing is applied
    lua.execute("run(20, 30)")
    assert lua.eval("#calls") == 0 and W.status().startswith("wear off"), W.status()
    # on: a part set worn is handed to the apply layer once
    W.setSettings(lua.table(wearEnabled=True, lifeScale=0.1, abuseScale=1, ageScale=1, effectStrength=1, springSagMax=25, springRateLoss=0.05, damperLossMax=0.8,
                            brakeTorqueLoss=0.08, enginePowerLoss=0.15, failures=False, failureRate=0, judder=1, visualWear=1))
    assert W.status().startswith("wear on")
    W.setCondition("damper", "FL", 0.4)
    lua.execute("calls = {}")
    lua.execute("run(1, 0)")
    c = lua.eval("calls")
    assert len(c) == 1 and c[1][1] == "damper" and c[1][2] == "FL" and abs(c[1][3] - 0.4) < 1e-9, [list(x.values()) for x in c.values()]
    # distance wears: 20 km at lifeScale 0.1 takes 20 / 10000 = 0.2 % of a damper (life 100000 km), so drive 100 km at 30 m/s (6000 s)
    lua.execute("calls = {}")
    lua.execute("run(12000, 30)")   # 6000 s at 30 m/s = 180 km
    d = W.getCondition("damper", "FR")
    assert 0.98 < d < 0.995, ("the damper wore by the distance", d)
    fr = [x for x in lua.eval("calls").values() if x[1] == "damper" and x[2] == "FR"]
    assert 1 <= len(fr) <= 3 and fr[-1][3] < 1, ("a change of 0.01 or more is handed on, not every tick", len(fr))
    # a hard stop costs the front pads more than the same distance would
    before = W.getCondition("padF", "F")
    lua.execute("electrics.values.wheelspeed = 30 W_.updateGFX(0.5) electrics.values.wheelspeed = 20 W_.updateGFX(0.5)")
    assert W.getCondition("padF", "F") < before - 0.001, "a hard stop wears the pads"
    # the snapshot holds only worn parts, and a restore with string keys brings them back
    snap = W.snapshot()
    assert "damper" in snap.keys() and "FL" in snap["damper"].keys()
    W.restoreSnapshot(lua.eval("{damper = {FL = 0.25}, padF = {F = '0.5'}, junk = {x = 1}}"))
    assert abs(W.getCondition("damper", "FL") - 0.25) < 1e-9 and abs(W.getCondition("padF", "F") - 0.5) < 1e-9 and W.getCondition("damper", "FR") == 1
    # a report goes up to the game side while the state is changing
    lua.execute("sent = {} run(30, 0)")
    lua.execute("W_.setCondition('spring', 'RR', 0.7) run(12, 0)")
    assert len(lua.eval("sent")) >= 1 and "slrr_partwear.onReport(5," in lua.eval("sent[1]") and "spring" in lua.eval("sent[#sent]"), lua.eval("sent[#sent]")
    # off: the apply layer is cleared, and nothing wears any more
    lua.execute("calls = {}")
    W.setSettings(lua.table(wearEnabled=False))
    assert lua.eval("calls[#calls][1]") == "clear"
    c0 = W.getCondition("damper", "FL")
    lua.execute("run(40, 30)")
    assert W.getCondition("damper", "FL") == c0, "no wear while off"
    # NaN / inf never get into a condition or a snapshot
    W.setSettings(lua.table(wearEnabled=True, lifeScale=0.1, abuseScale=1, ageScale=1, effectStrength=1, springSagMax=25, springRateLoss=0.05, damperLossMax=0.8,
                            brakeTorqueLoss=0.08, enginePowerLoss=0.15, failures=False, failureRate=0, judder=1, visualWear=1))
    W.restoreSnapshot(lua.eval("{damper = {FL = 0/0, FR = 1/0}, spring = {RL = -1/0}}"))
    assert W.getCondition("damper", "FL") == 1 and W.getCondition("damper", "FR") == 1 and W.getCondition("spring", "RL") == 1, "a non-finite condition is new"
    # a reset: every part is handed to the apply layer again a few frames later, whatever the order of the two onReset handlers
    W.setCondition("damper", "FL", 0.5)
    lua.execute("run(2, 0) calls = {}")
    W.onReset()
    lua.execute("run(4, 0, 0.01)")
    assert any(x[1] == "damper" and x[2] == "FL" for x in lua.eval("calls").values()), "handed over again after a reset"
    # one error in the tick switches part wear off for the car, once, and clears the apply layer
    lua.execute("calls = {} obj.queueGameEngineLua = function() error('boom') end W_.setCondition('spring', 'RR', 0.5)")
    lua.execute("run(30, 0)")
    assert W.status().startswith("wear off"), W.status()
    assert lua.eval("calls[#calls][1]") == "clear" and any("switched off after an error" in m for m in lua.eval("logs").values())
    n = lua.eval("#logs")
    lua.execute("run(30, 0)")
    assert lua.eval("#logs") == n, "the error is said once"
    print("wear state ok: off by default, wear by distance and hard stops, steps handed on, snapshot restore, report, off clears")


if __name__ == "__main__":
    main()
