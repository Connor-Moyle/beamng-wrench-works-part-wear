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
      v.data.beams[314] = {beamType = 0, id1 = 1, beamSpring = 20000, beamDamp = 0, beamPrecompression = 1.15, partPath = '/vivace_body/ardente_suspension_F/vivace_strut_F'}      -- the vivace's front spring, in the strut part
      v.data.beams[315] = {beamType = 4, id1 = 4, beamSpring = 265140, beamDamp = 1880, beamPrecompression = 0.957, partPath = '/pickup_body/pickup_axle_R/pickup_spring_R_base'}   -- a leaf spring (L-beam)
      v.data.beams[316] = {beamType = 4, id1 = 4, beamSpring = 900000, beamDamp = 10, partPath = '/pickup_body/wheel_RL/pickup_tire_RL'}   -- a tyre L-beam: not a spring
      v.data.beams[317] = {beamType = 0, id1 = 2, beamSpring = 100, beamDamp = 10, beamPrecompression = 1.2, partPath = '/lansdale_body/lansdale_suspension_R/lansdale_strut_R'}   -- the "beam for sound" of a rear strut
      v.data.beams[318] = {beamType = 0, id1 = 2, beamSpring = 7200, beamDamp = 10, beamPrecompression = 1.6, partPath = '/wigeon_body/wigeon_canopy_strut'}   -- a canopy gas strut
      -- a camber link beam of its own part, and an anti-roll bar and two other torsionbars
      v.data.beams[214] = {beamType = 0, id1 = 3, beamSpring = 14000000, beamDamp = 100, beamPrecompression = 1.004, partPath = '/vivace_body/ardente_suspension_R/vivace_toe_link'}
      v.data.beams[215] = {beamType = 0, id1 = 3, beamSpring = 14000000, beamDamp = 100, partPath = '/vivace_body/rear_arm_suspension/vivace_subframe_R'}   -- an ancestor says arm, the part itself does not
      v.data.beams[200] = {beamType = 2, id1 = 1, beamSpring = 0, beamDamp = 20000, beamDampRebound = 0, beamDampVelocitySplit = 2, partPath = '/bumpstop/'}
      rest = {}
      tors = {}
      obj = {setTorsionbarSpringDamp = function(_, cid, k, d) tors[#tors + 1] = {cid, k, d} end, getBeamRestLength = function(_, c) return 0.4 end,
             setBoundedBeamDamp = function(_, c, ...) calls[#calls + 1] = {'damp', c, ...} end,
             setBeamSpringDamp = function(_, c, k, d) calls[#calls + 1] = {'spring', c, k, d} end,
             setBeamLength = function(_, c, l) calls[#calls + 1] = {'len', c, l} end}
      dev = {name = 'mainEngine', outputTorqueState = 1}
      clutchDev = {wearLockTorqueCoef = 1, wearClutchFreePlayCoef = 1}
      -- the powertrain parts: a gearbox (the game gave it a wear coefficient from its odometer: 1.3), an automatic, two differentials, two shaft kinds, a turbo and a radiator on the engine
      gbox = {type = 'manualGearbox', name = 'gearbox', wearFrictionCoef = 1.3}
      auto = {type = 'automaticGearbox', name = 'gearbox2', wearFrictionCoef = 1, wearGearRatioChangeRateCoef = 1}
      diffF, diffR = {type = 'differential', name = 'differential_F', wearFrictionCoef = 1}, {type = 'differential', name = 'differential_R', wearFrictionCoef = 1}
      shaftF, shaftR, shaftC = {type = 'shaft', name = 'halfshaft_FL', wearFrictionCoef = 1}, {type = 'shaft', name = 'halfshaft_RL', wearFrictionCoef = 1}, {type = 'shaft', name = 'driveshaft', wearFrictionCoef = 1}
      turboState = {damageFrictionCoef = 1.5, damageExhaustPowerCoef = 0.9}
      turboCalls, radCalls = {}, {}
      dev.turbocharger = {isExisting = true, getPartCondition = function() return 1, {damageFrictionCoef = turboState.damageFrictionCoef, damageExhaustPowerCoef = turboState.damageExhaustPowerCoef} end,
                          setPartCondition = function(odo, st, vis) turboCalls[#turboCalls + 1] = {odo, st.damageFrictionCoef, st.damageExhaustPowerCoef, vis} end}
      dev.thermals = {setPartConditionRadiator = function(odo, integrity, vis) radCalls[#radCalls + 1] = {odo, integrity, vis} end}
      dctTyped = {type = 'dctGearbox', wearFrictionCoef = 1, wearLockTorqueCoef = 1}      -- a dual-clutch box: its clutch wear and its gearbox wear both act on the lock torque
      dctDev = {wearLockTorqueCoef = 1}      -- a dual-clutch box with no type field here: only the clutch wear reaches it
      tcDev = {wearLockupClutchTorqueCoef = 1}
      powertrain = {getDevice = function(n) return n == 'mainEngine' and dev or (n == 'clutch' and clutchDev or nil) end,
                    getOrderedDevices = function() return {gbox, auto, diffF, diffR, shaftF, shaftR, shaftC, dev, clutchDev, dctDev, tcDev, dctTyped} end}
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
            ("/wigeon_body/wigeon_canopy_strut", True, False),
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
    assert any(c[1] == "spring" and c[2] == 314 for c in al) and any(c[1] == "len" and c[2] == 314 for c in al), "the strut spring sags"
    assert any(c[1] == "spring" and c[2] == 315 and c[3] < 265140 for c in al) and not any(c[2] == 315 and c[1] == "len" for c in al), "the leaf softens, no length"
    assert not any(c[2] in (316, 317, 318) for c in al), "a tyre L-beam, a sound beam and a canopy strut are no springs"
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
    # the powertrain parts: the game's own wear fields of the devices, by type and axle, put back by clear(); the fuel tank and the number form of setPartCondition are never touched
    P.gearbox(0.0)
    P.diff("R", 0.0)
    P.cv("F", 0.0)
    P.turbo(0.0)
    P.radiator(0.0)
    P.ignition(0.0)
    P.oil(0.0)
    for _ in range(3): P.updateGFX(1 / 60)
    assert lua.eval("dctTyped.wearLockTorqueCoef") < lua.eval("dctDev.wearLockTorqueCoef"), "a dual-clutch box with a worn clutch and a worn gearbox: both factors, not the last writer"
    P.engine(0.2, 0.5)
    P.updateGFX(1 / 60)
    assert lua.eval("gbox.wearFrictionCoef") == 2 and lua.eval("auto.wearFrictionCoef") == 2 and abs(lua.eval("auto.wearGearRatioChangeRateCoef") - 0.5) < 1e-9, "every gearbox: friction, and the shift rate on the automatic"
    assert lua.eval("gbox.wearGearRatioChangeRateCoef") is None, "a manual box has no shift rate field: none is made"
    assert lua.eval("diffR.wearFrictionCoef") == 2 and lua.eval("diffF.wearFrictionCoef") == 1, "only the rear differential"
    assert abs(lua.eval("shaftF.wearFrictionCoef") - 1.5) < 1e-9 and lua.eval("shaftR.wearFrictionCoef") == 1 and abs(lua.eval("shaftC.wearFrictionCoef") - 1.5) < 1e-9, "front shafts; a single driveshaft takes the worse axle; rear shafts untouched"
    last = lua.eval("turboCalls[#turboCalls]")
    assert last[1] == 0 and abs(last[2] - 4) < 1e-9 and abs(last[3] - 0.6) < 1e-9 and last[4] == 1, "the turbo through its own call with a table, never a number"
    assert lua.eval("radCalls[#radCalls][1]") == 0 and abs(lua.eval("radCalls[#radCalls][2]") - 0.86) < 1e-9, "the radiator integrity through the module's call"
    assert lua.eval("dev.slowIgnitionErrorChance") > 0.07, "the ignition misfire"
    assert abs(lua.eval("dev.wearDynamicFrictionCoef") - 1.4 * 1.15) < 1e-9, "engine and oil friction multiply"
    lua.execute("turboCalls, radCalls = {}, {}")
    P.onReset()
    for _ in range(4): P.updateGFX(1 / 60)
    assert lua.eval("#turboCalls") >= 1 and lua.eval("#radCalls") >= 1 and lua.eval("diffR.wearFrictionCoef") == 2, "reapplied after a reset"
    P.clear()
    assert lua.eval("gbox.wearFrictionCoef") == 1.3 and lua.eval("auto.wearGearRatioChangeRateCoef") == 1 and lua.eval("diffR.wearFrictionCoef") == 1 and lua.eval("shaftC.wearFrictionCoef") == 1, "the game's own values are back, not 1"
    back2 = lua.eval("turboCalls[#turboCalls]")
    assert abs(back2[2] - 1.5) < 1e-9 and abs(back2[3] - 0.9) < 1e-9, "the turbo's own damage state is back"
    assert lua.eval("radCalls[#radCalls][2]") == 1, "the radiator is new again"
    assert lua.eval("dev.slowIgnitionErrorChance") == 0 and lua.eval("dev.wearDynamicFrictionCoef") == 1
    P.clutch(0.0)
    P.updateGFX(1 / 60)
    # the chassis: arms and links (rate only, length stays), anti-roll bars (torsionbars), wheel bearings (drag next to the pads'), brake fluid and master cylinder (through the pads' torque)
    lua.execute("v.data.torsionbars = {[1] = {cid = 7, id1 = 1, spring = 900, damp = 5, vkTag = 'arb_F'}, [2] = {cid = 8, id1 = 3, spring = 700, damp = 5, vkTag = 'arb_R'}, [3] = {cid = 9, id1 = 1, spring = 150000, damp = 0, vkTag = 'rigidify'}}")
    P.clear()
    lua.execute("calls, tors = {}, {}")
    assert P.armPart("/a/b/vivace_toe_link") and P.armPart("/x/camber_link_R") and not P.armPart("/a/rear_arm_suspension/vivace_subframe_R") and not P.armPart("/a/vivace_swaybar_link_F") and not P.armPart("/a/steering_arm_F"), "arm parts by the part's own name"
    P.bushing("RL", 0.0)
    for _ in range(40): P.updateGFX(1 / 60)
    ar = [lua.eval("calls")[i + 1] for i in range(len(lua.eval("calls")))]
    assert ar and all(c[2] == 214 for c in ar) and all(c[1] == "spring" for c in ar), "only the toe link beam, and only its rate: no length change"
    assert abs(ar[-1][3] - 14000000 * 0.85) < 1, ("85 % of the rate at worst", ar[-1][3])
    P.swaybar("F", 0.0)
    for _ in range(40): P.updateGFX(1 / 60)
    assert lua.eval("#tors") > 0 and all(t[1] == 7 for t in [lua.eval("tors")[i + 1] for i in range(len(lua.eval("tors")))]), "only the front anti-roll bar: not the rear one, not a rigidify torsionbar"
    assert abs(lua.eval("tors[#tors][2]") - 900 * 0.2) < 1e-6 and lua.eval("tors[#tors][3]") == 5, "a broken bar link keeps a fifth of the rate"
    P.pads("F", 1.0)
    lua.execute("wheels.wheels[1].brakeSurfaceTemperature = 300")
    for _ in range(40): P.updateGFX(1 / 60)
    t1 = lua.eval("wheels.wheels[1].brakeTorque")
    P.fluid("F", 0.0)
    for _ in range(60): P.updateGFX(1 / 60)
    t2 = lua.eval("wheels.wheels[1].brakeTorque")
    assert t2 < t1 - 1 and lua.eval("wheels.wheels[3].brakeTorque") == 1000, "old fluid fades the front brakes earlier, only the front"
    P.master(0.0)
    for _ in range(60): P.updateGFX(1 / 60)
    assert lua.eval("wheels.wheels[1].brakeTorque") < t2 * 0.9, "a weak master cylinder lowers the torque at the pedal"
    P.bearing("FL", 0.0)
    P.updateGFX(1 / 60)
    assert lua.eval("wheels.wheels[1].frictionTorque") > 40 and lua.eval("wheels.wheels[2].frictionTorque") == 0, "the failing bearing drags its own wheel"
    P.clear()
    assert abs(lua.eval("tors[#tors][2]") - 900) < 1e-9, "the anti-roll bar is back"
    assert lua.eval("wheels.wheels[1].frictionTorque") == 0 and lua.eval("wheels.wheels[1].brakeTorque") == 1000, "bearing drag and brake torque are back"
    P.clutch(0.0)
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
