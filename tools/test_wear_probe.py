"""Smoke test of the vehicle-side probe (mod/lua/vehicle/extensions/slrrWearProbe.lua) against a stand-in car: finds the springs and dampers (not the
bump stops), steps a worn damper in by at most 10 % per frame, never above the jbeam value, reapplies after a reset and puts everything back on clear().

    python tools/test_wear_probe.py
"""
import os
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "mod", "lua")


def main():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("""
      logs = {}
      function log(l, t, m) logs[#logs + 1] = m end
      calls = {}
      v = {data = {nodes = {}, beams = {}, torsionbars = {}}}
      -- four wheels at +-0.7 x, y 0 (front) and 2.5 (rear); a strut spring and a damper and a bump stop at each front, rear spring+damper
      local function node(id, x, y) v.data.nodes[id] = {pos = {x = x, y = y, z = 0}} end
      node(1, 0.7, 0) node(2, -0.7, 0) node(3, 0.7, 2.5) node(4, -0.7, 2.5)
      wheels = {wheels = {}, wheelRotators = {}}
      for i = 1, 4 do
        local w = {name = 'W' .. i, node1 = i, brakeTorque = 1000, initialBrakeTorque = 1000, padGlazingFactor = 0, squealCoefLowSpeed = 0.1, frictionTorque = 0}
        wheels.wheels[i] = w wheels.wheelRotators[i] = w
      end
      local cid = 100
      for i = 1, 4 do
        v.data.beams[cid] = {beamType = 2, id1 = i, beamSpring = 80000, beamDamp = 400, beamPrecompression = 1.1, partPath = '/spring/'} cid = cid + 1
        v.data.beams[cid] = {beamType = 2, id1 = i, beamSpring = 0, beamDamp = 3000, beamDampRebound = 5000, beamDampFast = 1500, beamDampReboundFast = 2500,
                             beamDampVelocitySplit = 0.1, beamDampVelocitySplitRebound = 0.1, partPath = '/damper/'} cid = cid + 1
      end
      v.data.beams[200] = {beamType = 2, id1 = 1, beamSpring = 0, beamDamp = 20000, beamDampRebound = 0, beamDampVelocitySplit = 2, partPath = '/bumpstop/'}
      rest = {}
      obj = {getBeamRestLength = function(_, c) return 0.4 end,
             setBoundedBeamDamp = function(_, c, ...) calls[#calls + 1] = {'damp', c, ...} end,
             setBeamSpringDamp = function(_, c, k, d) calls[#calls + 1] = {'spring', c, k, d} end,
             setBeamLength = function(_, c, l) calls[#calls + 1] = {'len', c, l} end}
      dev = {name = 'mainEngine', outputTorqueState = 1}
      powertrain = {getDevice = function(n) return n == 'mainEngine' and dev or nil end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    P = lua.execute(open(os.path.join(ROOT, "vehicle", "extensions", "slrrWearProbe.lua"), encoding="utf8").read())
    springs, dampers, nw = P.detect()
    assert (springs, dampers, nw) == (4, 4, 4), ("found", springs, dampers, nw)
    assert not [m for m in lua.eval("logs") .values() if "bumpstop" in m], "the bump stop is not listed"
    base = lua.eval("v.data.beams[101].beamDampRebound")
    P.damper("FL", 0.3)
    for _ in range(40):
        P.updateGFX(1 / 60)
    calls = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    damps = [c for c in calls if c[1] == "damp"]
    assert damps, "no damper was set"
    prev = None
    for c in damps:
        for i, jb in ((3, 3000), (4, 5000), (5, 1500), (6, 2500)):
            assert c[i] <= jb + 1e-9, ("a damper above its jbeam value", c)
        if prev:
            assert abs(c[4] - prev[4]) <= 0.10 * 5000 + 1e-6, ("a step over 10 % of the base", prev[4], c[4])
        prev = c
    assert prev[4] < 5000 * 0.6, ("the worn rebound was reached", prev[4])
    assert len({c[2] for c in damps}) == 1, "only one damper (front left) was touched"
    # a spring: sags, never stiffer
    lua.execute("calls = {}")
    P.spring("FR", 0.3)
    for _ in range(60):
        P.updateGFX(1 / 60)
    sp = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    ks = [c for c in sp if c[1] == "spring"]
    ls = [c for c in sp if c[1] == "len"]
    assert ks and all(c[3] <= 80000 + 1e-9 for c in ks) and ls and ls[-1][3] < 0.4, ("sag and a softer spring", ls[-1:] if ls else None)
    # a reset: everything is applied again after two frames
    lua.execute("calls = {}")
    P.onReset()
    P.updateGFX(1 / 60); P.updateGFX(1 / 60); P.updateGFX(1 / 60)
    assert lua.eval("#calls") > 0, "nothing was reapplied after a reset"
    # pads and engine
    P.pads("F", 0.05)
    for _ in range(40):
        P.updateGFX(1 / 60)
    assert lua.eval("wheels.wheels[1].brakeTorque") < 1000 * 0.7 and lua.eval("wheels.wheels[3].brakeTorque") == 1000, "front pads only"
    P.engine(0.2, 0.5)
    P.updateGFX(1 / 60)
    assert 0.8 < lua.eval("dev.outputTorqueState") < 1 and lua.eval("dev.wearDynamicFrictionCoef") > 1
    # clear: every value back
    lua.execute("calls = {}")
    P.clear()
    assert lua.eval("wheels.wheels[1].brakeTorque") == 1000 and lua.eval("dev.outputTorqueState") == 1 and lua.eval("dev.wearDynamicFrictionCoef") == 1
    back = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    assert any(c[1] == "damp" and abs(c[4] - 5000) < 1e-9 for c in back), "the damper is back at its jbeam value"
    print("wear probe ok: found %d springs and %d dampers, steps within 10 %%, nothing above jbeam, reapplied after a reset, cleared" % (springs, dampers))


if __name__ == "__main__":
    main()
