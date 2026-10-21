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
        -- (the rear springs are NORMAL beams, as on the vivace, the front ones bounded)
        v.data.beams[cid] = {beamType = i > 2 and 0 or 2, id1 = i, beamSpring = 80000, beamDamp = 400, beamPrecompression = 1.1, partPath = '/vivace_body/suspension_F/spring/'} cid = cid + 1
        v.data.beams[cid] = {beamType = 2, id1 = i, beamSpring = 0, beamDamp = 3000, beamDampRebound = 5000, beamDampFast = 1500, beamDampReboundFast = 2500,
                             beamDampVelocitySplit = 0.1, beamDampVelocitySplitRebound = 0.1, partPath = '/damper/'} cid = cid + 1
      end
      -- what the shape tests alone would take for suspension, found on the vivace: door hinge springs and steering beams
      v.data.beams[210] = {beamType = 2, id1 = 1, beamSpring = 800, beamDamp = 200, beamPrecompression = 1.2, partPath = '/vivace_body/ardente_door_L/ardente_door_L'}
      v.data.beams[211] = {beamType = 2, id1 = 1, beamSpring = 0, beamDamp = 900, beamDampRebound = 900, beamDampVelocitySplit = 0.1, partPath = '/vivace_body/ardente_suspension_F/vivace_steering_wide/vivace_steering_wide_sport'}
      -- the alignment (toe) link of the vivace's rear suspension: a NORMAL beam with a spring and a precompression near 1, in a part that says suspension but not spring
      v.data.beams[212] = {beamType = 0, id1 = 3, beamSpring = 14000000, beamDamp = 100, beamPrecompression = 1.003, partPath = '/vivace_body/ardente_suspension_R/vivace_suspension_R_wide'}
      v.data.beams[213] = {beamType = 0, id1 = 3, beamSpring = 90000, beamDamp = 100, beamPrecompression = 1.05, partPath = '/vivace_body/ardente_suspension_R/vivace_camber_link_spring'}
      v.data.beams[214] = {beamType = 0, id1 = 1, beamSpring = 20000, beamDamp = 0, beamPrecompression = 1.15, partPath = '/vivace_body/ardente_suspension_F/vivace_strut_F'}      -- the vivace's front spring, in the strut part
      v.data.beams[215] = {beamType = 4, id1 = 4, beamSpring = 265140, beamDamp = 1880, beamPrecompression = 0.957, partPath = '/pickup_body/pickup_axle_R/pickup_spring_R_base'}   -- a leaf spring (L-beam)
      v.data.beams[216] = {beamType = 4, id1 = 4, beamSpring = 900000, beamDamp = 10, partPath = '/pickup_body/wheel_RL/pickup_tire_RL'}   -- a tyre L-beam: not a spring
      v.data.beams[200] = {beamType = 2, id1 = 1, beamSpring = 0, beamDamp = 20000, beamDampRebound = 0, beamDampVelocitySplit = 2, partPath = '/bumpstop/'}
      rest = {}
      obj = {getBeamRestLength = function(_, c) return 0.4 end,
             setBoundedBeamDamp = function(_, c, ...) calls[#calls + 1] = {'damp', c, ...} end,
             setBeamSpringDamp = function(_, c, k, d) calls[#calls + 1] = {'spring', c, k, d} end,
             setBeamLength = function(_, c, l) calls[#calls + 1] = {'len', c, l} end}
      dev = {name = 'mainEngine', outputTorqueState = 1}
      clutchDev = {wearLockTorqueCoef = 1, wearClutchFreePlayCoef = 1}
      dctDev = {wearLockTorqueCoef = 1}
      tcDev = {wearLockupClutchTorqueCoef = 1}
      powertrain = {getDevice = function(n) return n == 'mainEngine' and dev or nil end, getOrderedDevices = function() return {dev, clutchDev, dctDev, tcDev} end}
      package.preload['slrrWearRules'] = function() return assert(loadfile('@ROOT@/common/slrrWearRules.lua'))() end
    """.replace("@ROOT@", ROOT.replace("\\", "/")))
    P = lua.execute(open(os.path.join(ROOT, "vehicle", "extensions", "slrrWearProbe.lua"), encoding="utf8").read())
    springs, dampers, nw = P.detect()
    assert (springs, dampers, nw) == (6, 4, 4), ("found", springs, dampers, nw)
    assert not [m for m in lua.eval("logs") .values() if "bumpstop" in m], "the bump stop is not listed"
    # the part words are whole words, and for NORMAL beams only: stock suspensions that say 4link, multilink or sit under an arm/alarm ancestor are still found; the alignment and anti-roll links are not
    for path, normal, want in (
            ("/pickup_body/pickup_coilover_4link_F/pickup_coilover_4link_F", True, True),      # the pickup's front: a 4-link axle (found by a survey of the stock part names)
            ("/etk_body/multilink_suspension_R/multilink_spring_R", True, True),
            ("/x/alarm_suspension/shock_R", False, True),
            ("/x/rear_arm_suspension/damper_R", False, True),       # (a bounded damper under an 'arm' ancestor: the link words only apply to NORMAL beams)
            ("/vivace_body/ardente_suspension_R/vivace_camber_link_spring", True, False),
            ("/vivace_body/ardente_suspension_R/vivace_toe_link", True, False),
            ("/simple_traffic_body/simple_traffic_swaybar_F_strut", True, False),
            ("/vivace_body/ardente_door_L/ardente_door_L", False, False),
            ("/vivace_body/ardente_suspension_F/vivace_steering_wide", False, False)):
        assert P.suspensionPart(path, normal) == want, (path, normal, want)
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
    # the strut-front spring (NORMAL, in the strut part) sags; the leaf spring (L-beam) only softens, its length is never set, a tyre L-beam is not touched
    lua.execute("calls = {}")
    P.spring("all", 0.3)
    for _ in range(80):
        P.updateGFX(1 / 60)
    al = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    assert any(c[1] == "spring" and c[2] == 214 for c in al) and any(c[1] == "len" and c[2] == 214 for c in al), "the strut spring sags"
    assert any(c[1] == "spring" and c[2] == 215 and c[3] < 265140 for c in al) and not any(c[2] == 215 and c[1] == "len" for c in al), "the leaf softens, no length"
    assert not any(c[2] == 216 for c in al), "a tyre L-beam is no spring"
    P.clear()
    # a NORMAL rear spring (the vivace's) sags too, and the door hinge and steering beams are never touched
    lua.execute("calls = {}")
    P.spring("RL", 0.3)
    for _ in range(60):
        P.updateGFX(1 / 60)
    rl = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    assert any(c[1] == "len" for c in rl) and all(c[2] not in (210, 211, 212, 213) for c in rl), "a NORMAL spring sags; the door and steering beams are not touched"
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
    # settings table, clutch, rotor and the extra fade of a worn pad when the brake is hot
    P.setSettings(lua.eval("require('slrrWearRules').settings('Realistic')"))
    P.clutch(0.0)
    P.updateGFX(1 / 60)
    assert lua.eval("clutchDev.wearLockTorqueCoef") < 1 and lua.eval("clutchDev.wearClutchFreePlayCoef") > 1, "clutch wear coefficients"
    assert lua.eval("dctDev.wearLockTorqueCoef") < 1 and lua.eval("tcDev.wearLockupClutchTorqueCoef") < 1, "dual-clutch and torque converter lock wear"
    lua.execute("wheels.wheels[1].brakeSurfaceTemperature = 20")
    for _ in range(60): P.updateGFX(1 / 60)
    cold = lua.eval("wheels.wheels[1].brakeTorque")
    P.rotor("F", 0.0)
    lua.execute("wheels.wheels[1].brakeSurfaceTemperature = 500")
    for _ in range(60): P.updateGFX(1 / 60)
    assert lua.eval("wheels.wheels[1].brakeTorque") < cold, "worn pad and rotor fade more when hot"
    # clear: every value back
    lua.execute("calls = {}")
    P.clear()
    assert lua.eval("clutchDev.wearLockTorqueCoef") == 1 and lua.eval("dctDev.wearLockTorqueCoef") == 1 and lua.eval("tcDev.wearLockupClutchTorqueCoef") == 1
    assert lua.eval("wheels.wheels[1].brakeTorque") == 1000 and lua.eval("dev.outputTorqueState") == 1 and lua.eval("dev.wearDynamicFrictionCoef") == 1
    back = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    assert any(c[1] == "damp" and abs(c[4] - 5000) < 1e-9 for c in back), "the damper is back at its jbeam value"
    print("wear probe ok: found %d springs and %d dampers, steps within 10 %%, nothing above jbeam, reapplied after a reset, cleared" % (springs, dampers))


if __name__ == "__main__":
    main()
