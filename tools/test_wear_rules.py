"""Offline checks of the pure wear rules (mod/lua/common/slrrWearRules.lua).

    python tools/test_wear_rules.py

The rules decide what a worn part does to the car, so the checks are the safety ones: a new part changes nothing, no factor ever goes above the jbeam
value, worse condition never makes an effect weaker, Off is an identity, conditions never rise, steps are limited, one engine cap.
"""
import os
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
lua = LuaRuntime(unpack_returned_tuples=True)
W = lua.execute(open(os.path.join(HERE, "..", "mod", "lua", "common", "slrrWearRules.lua"), encoding="utf8").read())
T = lambda d: {k: v for k, v in d.items()}  # noqa: E731

# (kind, state, "goodness" key: a field that only gets worse as c falls: factors down, amounts up)
DOWN = {"damper": ["rebound", "comp", "fast"], "spring": ["rate"], "swaybar": ["k"], "bushing": ["k", "d"], "balljoint": ["strength"], "steering": ["k", "powerCoef"],
        "padF": ["torque"], "padR": ["torque"], "rotor": ["massCoef"], "engine": ["cap"], "filter": ["cap"], "cat": ["cap"], "mounts": ["k", "d"],
        "clutch": ["lockTorque"], "battery": ["crank"], "alternator": ["charge"],
        "gearbox": ["shiftRate", "lockTorque"], "turbo": ["power"], "radiator": ["integrity"], "master": ["torque"], "lights": ["brightness"]}
DOWN["fuel"], DOWN["intercooler"] = ["cap"], ["cap"]
UP = {"steering": ["deadZone", "lagS"], "lights": ["flicker"], "flywheel": ["inertia"], "spring": ["sagMm"], "bearing": ["humVolume"], "padF": ["squealLow", "glazing"], "engine": ["dynFriction", "misfire"], "ignition": ["misfire"],
      "clutch": ["freePlay"], "gearbox": ["friction"], "diff": ["friction"], "cv": ["friction"], "turbo": ["friction"], "oil": ["dynFriction"], "exhaust": ["gainDb"], "paint": ["fade", "grime", "scuffs", "rust"]}
KINDS = list(W.KINDS.keys())


def eff(kind, c, s, st=None):
    r = W.effects(kind, c, s, lua.table_from(st) if st else None)
    return None if r is None else {k: r[k] for k in r.keys()}


def main():
    real = W.settings("Realistic")
    assert real.wearEnabled and real.lifeScale == 0.1
    light, off = W.settings("Light"), W.settings("Off")
    assert off.effectStrength == 0 and not off.wearEnabled
    over = W.settings("Realistic", lua.table_from({"lifeScale": 5, "springSagMax": -3}))
    assert over.lifeScale == 1 and over.springSagMax == 0, "settings are clamped to their ranges"
    assert W.stage(0.9) == "Good" and W.stage(0.6) == "Worn" and W.stage(0.3) == "Bad" and W.stage(0.1) == "Failing"
    assert W.lookStage(0.5, 1) == 1 and W.lookStage(0.2, 1) == 2 and W.lookStage(0.7, 1) == 0 and W.lookStage(0.2, 0) == 0, "the look stages: worn below 0.6, rusty below 0.3, none with the worn look at 0"
    assert W.mechCondition(lua.eval("{}")) == 1 and W.mechCondition(None) == 1, "no record: the metal is new"
    assert abs(W.mechCondition(lua.eval("{spring = {FL = 0.2}, rotor = {FL = 0}}")) - 0.9) < 1e-9, "the mean over the four corners of springs and dampers; a corner not stored is new; brakes do not count"
    assert abs(W.mechCondition(lua.eval("{spring = {FL = 0, FR = 0, RL = 0, RR = 0}, damper = {FL = 0, FR = 0, RL = 0, RR = 0}}"))) < 1e-9
    assert W.engineCondition(lua.eval("{engine = {all = 0.25}}")) == 0.25 and W.engineCondition(lua.eval("{spring = {FL = 0}}")) == 1 and W.engineCondition(None) == 1, "the engine bay follows the engine internals; new when not stored"

    for preset in ("Realistic", "Light"):
        s = W.settings(preset)
        for kind in DOWN:
            new = eff(kind, 1.0, s)
            for f in DOWN[kind]:
                assert abs(new[f] - 1) < 1e-9, ("a new part changes nothing", kind, f, new[f])
            prev = None
            for i in range(0, 101):
                c = 1 - i / 100
                e = eff(kind, c, s)
                for f in DOWN[kind]:
                    assert e[f] <= 1 + 1e-9, ("a factor above the jbeam value", kind, f, e[f])
                    assert e[f] > 0.1, ("a factor must not reach zero", kind, f, e[f])
                    if prev:
                        assert e[f] <= prev[f] + 1e-9, ("worse condition must not be better", kind, f, c)
                prev = e
        for kind in UP:
            prev = None
            for i in range(0, 101):
                e = eff(kind, 1 - i / 100, s)
                for f in UP[kind]:
                    if prev:
                        assert e[f] >= prev[f] - 1e-9, ("worse condition must not be milder", kind, f)
                prev = e
        assert eff("spring", 1.0, s)["sagMm"] == 0 and eff("spring", 0.0, s)["sagMm"] <= 60
        assert eff("spring", 0.0, s)["sagMm"] <= s.springSagMax * 1.0001, "a fully worn spring sags at most the setting's amount"
        assert eff("spring", 0.0, s, {"rear": True})["sagMm"] <= s.springSagMax * 1.3001
        assert eff("spring", 0.0, s, {"broken": True})["rate"] >= 0.6
        assert abs(eff("damper", 0.0, s)["rebound"] - max(0.15, 1 - s.damperLossMax * min(1, s.effectStrength))) < 1e-9
        assert eff("damper", 0.0, s, {"leaking": True})["rebound"] >= 0.15

    # Off and strength 0: every effect is an identity
    for kind in KINDS:
        assert eff(kind, 0.0, off) is None, ("Off applies nothing", kind)
    zero = W.settings("Realistic", lua.table_from({"effectStrength": 0}))
    for kind in DOWN:
        e = eff(kind, 0.0, zero)
        for f in DOWN[kind]:
            assert abs(e[f] - 1) < 1e-9, ("strength 0 is an identity", kind, f)
    assert eff("spring", 0.0, zero)["sagMm"] == 0 and eff("padF", 0.05, zero)["grind"] is False

    # pads: grind below 10 %, torque never below 0.6
    assert eff("padF", 0.09, real)["grind"] and eff("padF", 0.09, real)["torque"] == 0.6 and not eff("padF", 0.2, real)["grind"]
    # bearings drag only when failing
    assert eff("bearing", 0.5, real)["dragNm"] == 0 and eff("bearing", 0.1, real)["dragNm"] > 5
    assert eff("bearing", 0.25, real)["dragNm"] == 0 and eff("bearing", 0.24, real)["dragNm"] < 3 and abs(eff("bearing", 0.0, real)["dragNm"] - 65) < 1e-9, "a bearing starts to drag from nothing at a quarter of its life, up to 65 Nm: no step"
    # paint: the four layers of the paint wear look follow the visualWear setting and the wear
    p0, p1, pm = eff("paint", 1.0, real), eff("paint", 0.0, real), eff("paint", 0.7, real)
    assert all(abs(p0[k]) < 1e-9 for k in p0) and all(0 < p1[k] <= 1 for k in p1), "new paint shows nothing, worn paint shows every layer"
    assert pm["rust"] == 0 and 0 < pm["fade"] < 0.5 and p1["rust"] > 0.99, "rust only from 40 % worn"
    assert all(abs(eff("paint", 0.0, W.settings("Realistic", lua.table_from({"visualWear": 0})))[k]) < 1e-9 for k in p1), "visualWear 0: no worn look"
    assert eff("paint", 0.0, off) is None
    # brake fluid
    assert eff("fluid", 1.0, real)["curveShiftC"] == 0 and eff("fluid", 0.0, real, {"water": 0.03})["curveShiftC"] == -80

    # wear: never rises, scales with the life setting, abuse and time count
    s = W.settings("Realistic")
    c = 1.0
    inp = lambda **k: lua.table_from(k)  # noqa: E731
    c2 = W.wearStep("padF", c, inp(km=100), s)
    assert 0 < 1 - c2 < 0.5 and c2 < c
    assert abs((1 - c2) - 100 / (40000 * 0.1)) < 1e-9, "100 km at lifeScale 0.1: 2.5 % of a 4000 km pad set"
    c3 = W.wearStep("padF", c, inp(km=100, events=lua.table_from({"hardstop": 5})), s)
    assert c3 < c2, "hard stops wear pads faster"
    assert W.wearStep("padF", 0.5, inp(km=0), s) == 0.5
    assert W.wearStep("padF", 0.5, inp(km=-50), s) <= 0.5 + 1e-12, "negative distance never repairs"
    assert W.wearStep("battery", 1.0, inp(days=365), s) < 1 and W.wearStep("battery", 1.0, inp(km=1000), s) == 1.0, "a battery ages by days, not km"
    assert W.wearStep("padF", 0.0, inp(km=1e6), s) == 0.0
    assert W.wearStep("padF", 1.0, inp(km=1e6), off) == 1.0, "Off: nothing wears"
    assert W.wearStep("nonsense", 0.7, inp(km=100), s) == 0.7

    # failures: none above 0.15, none when the setting is off, more likely the worse it is
    seq = iter([0.0] * 1000)
    rand = lambda: next(seq)  # noqa: E731
    assert not W.failureRoll(0.5, 1, real, rand)
    assert not W.failureRoll(0.05, 1, light, rand), "Light: failures off"
    assert W.failureRoll(0.05, 1, real, lambda: 0.0)
    assert W.failureRoll(0.0, 1, real, lambda: 0.99) is True
    assert W.failureRoll(0.14, 1, real, lambda: 0.5) is False

    # events a part counts, and the failure roll
    ev = lua.table_from({"hardstop": 1, "landing": 2, "hotF_s": 3, "hotR_s": 4, "overheat_s": 5, "limiter_s": 6})
    assert dict(W.eventsFor("padF", "F", ev)) == {"hardstop": 1, "hot_s": 3} and dict(W.eventsFor("padR", "R", ev))["hot_s"] == 4
    assert W.eventsFor("rotor", "RL", ev)["hot_s"] == 4 and W.eventsFor("rotor", "FL", ev)["hot_s"] == 3
    assert dict(W.eventsFor("engine", "all", ev)) == {"overheat_s": 5, "limiter_s": 6} and dict(W.eventsFor("damper", "FL", ev)) == {"landing": 2}
    assert dict(W.eventsFor("diff", "all", ev)) == {}
    c, text = W.failureStep("damper", 0.1, 1, real, lambda: 0.0)
    assert c == W.FAILURE["damper"]["level"] and "shock" in text
    assert W.failureStep("damper", 0.05, 1, real, lambda: 0.0) is None, "an already failed part cannot fail again"
    assert W.failureStep("damper", 0.5, 1, real, lambda: 0.0) is None, "a part above 15 % does not fail"
    assert W.failureStep("damper", 0.1, 1, light, lambda: 0.0) is None, "Light has no breakdowns"
    assert W.failureStep("diff", 0.01, 1, real, lambda: 0.0) is None, "a kind with no failure never fails"
    assert all(0 < W.FAILURE[k]["level"] < 0.15 for k in W.FAILURE.keys()), "a failed part is below the roll threshold"
    # the powertrain kinds: rows, price and name, failures, events; the misfire is the ignition's and not the engine's
    for k in ("gearbox", "diff", "cv", "turbo", "radiator", "ignition", "oil"):
        assert W.KINDS[k] is not None and W.PRICE[k] > 0 and W.NAME[k], ("a powertrain kind has a row, a price and a name", k)
    assert W.KINDS["turbo"].group == "engine" and W.KINDS["oil"].group == "engine" and W.KINDS["oil"].life == 15000
    assert eff("engine", 0.0, real)["misfire"] == 0 and eff("ignition", 0.0, real)["misfire"] > 0, "the engine's misfire moved to the ignition"
    assert eff("gearbox", 0.0, real)["friction"] <= 2.0001 and eff("cv", 0.0, real)["friction"] <= 1.5001, "gearbox and shaft friction stay inside the game's own wear range"
    assert eff("turbo", 0.0, real)["power"] >= 0.6 and eff("turbo", 0.0, real)["friction"] <= 4.0001 and 0.1 * (1 - eff("radiator", 0.0, real)["integrity"]) < 0.015, "the game leaks coolant above a radiator damage of 0.015: never reached"
    assert eff("oil", 0.0, real)["dynFriction"] <= 1.1501 and eff("oil", 1.0, real)["dynFriction"] == 1
    for k in ("gearbox", "cv", "turbo", "radiator", "ignition"):
        assert W.failureStep(k, 0.12, 1, real, lambda: 0.0) is not None and W.failureStep(k, 0.12, 1, real, lambda: 0.0)[0] == W.FAILURE[k]["level"], ("a failure", k)
    assert dict(W.eventsFor("oil", "all", ev)) == {"overheat_s": 5, "limiter_s": 6} and dict(W.eventsFor("turbo", "all", ev)) == {"overheat_s": 5, "limiter_s": 6}
    assert W.wearStep("oil", 1.0, inp(km=300), s) < W.wearStep("gearbox", 1.0, inp(km=300), s), "oil wears much faster than a gearbox"
    assert W.wearStep("radiator", 1.0, inp(km=1000), s) == 1.0 and W.wearStep("radiator", 1.0, inp(days=365), s) < 1, "a radiator ages by days"
    # the chassis kinds
    for k in ("swaybar", "bushing", "bearing", "fluid", "master"):
        assert W.PRICE[k] > 0 and W.NAME[k] and W.failureStep(k, 0.12 if k not in ("swaybar",) else 0.1, 1, real, lambda: 0.0) is not None, ("a chassis kind has a price, a name and a failure", k)
    assert eff("bushing", 0.0, real)["k"] >= 0.85 and eff("bushing", 0.0, real)["d"] >= 0.9, "arms and links stay at 85 % of their rate at worst: the car's shape is not changed"
    assert eff("master", 0.0, real)["torque"] == 0.8 and eff("master", 1.0, real)["torque"] == 1
    assert eff("swaybar", 0.0, real, {"linkBroken": True})["k"] == 0.2 and eff("swaybar", 0.5, real)["k"] > 0.8, "a broken bar link keeps a fifth of the rate, never zero"
    assert W.wornFade(300, 1.0, real, -80) < 1 and W.wornFade(300, 1.0, real) == 1 and abs(W.wornFade(900, 1.0, real, -80) - 1) < 1e-9, "old fluid fades the brakes earlier, only the extra loss"
    assert W.wornFade(500, 1.0, off, -80) == 1, "Off: no extra fade"
    # the engine split and the battery: caps (one cap: the product of ours), a starter factor
    for k in ("fuel", "cat", "intercooler", "battery"):
        assert W.PRICE[k] > 0 and W.NAME[k], ("a price and a name", k)
    for k in ("fuel", "cat", "intercooler", "battery"):
        assert W.failureStep(k, 0.12 if k != "battery" else 0.1, 1, real, lambda: 0.0) is not None, ("a failure", k)
    assert eff("fuel", 0.0, real)["cap"] >= 0.94 and eff("intercooler", 0.0, real)["cap"] >= 0.95 and eff("cat", 0.0, real)["cap"] >= 0.85 and eff("battery", 0.0, real)["crank"] >= 0.6, "the caps are small and bounded"
    assert abs(W.torqueCap(1, eff("fuel", 0.0, real)["cap"], eff("cat", 0.0, real)["cap"], eff("intercooler", 0.0, real)["cap"]) - 0.94 * 0.85 * 0.95) < 0.02, "the caps multiply into one"
    # the last five: steering play, flywheel, bulbs, alternator, exhaust sound
    for k in ("steering", "flywheel", "lights", "alternator", "exhaust"):
        assert W.PRICE[k] > 0 and W.NAME[k], ("a price and a name", k)
    assert eff("steering", 0.0, real)["deadZone"] <= 0.0601 and eff("steering", 0.0, real)["lagS"] <= 0.081 and eff("steering", 1.0, real)["deadZone"] == 0, "steering play: 6 % and 0.08 s at worst, none when new"
    assert eff("flywheel", 0.0, real)["inertia"] <= 1.0801 and eff("lights", 0.0, real)["brightness"] >= 0.6 and eff("lights", 0.5, real)["flicker"] == 0 and eff("lights", 0.0, real)["flicker"] <= 0.25
    assert eff("exhaust", 0.0, real)["mufflingOffset"] >= -0.2001 and eff("exhaust", 0.0, real)["gainDb"] <= 1.501, "inside the game's own sport-exhaust range"
    assert W.failureStep("alternator", 0.1, 1, real, lambda: 0.0) is not None and W.failureStep("steering", 0.12, 1, real, lambda: 0.0) is not None
    # one engine cap
    assert W.torqueCap(0.99, 0.95, 0.99) == 0.95 * 0.99 or abs(W.torqueCap(0.99, 0.95, 0.99) - 0.9405) < 1e-9
    assert W.torqueCap(1, 0.95, 0.99) == 0.95 * 0.99
    assert W.torqueCap(0.5, 0.95, 0.99) == 0.5, "Street Legal's cap wins when it is lower: one cap, the minimum"
    assert W.torqueCap(1) == 1 and W.torqueCap(0.7) == 0.7

    # steps limited to 10 % of the base value
    assert W.brakeFade(200, 1.0, real) == 1 and abs(W.brakeFade(550, 1.0, real) - 0.6) < 1e-9 and W.brakeFade(900, 0.0, real) >= 0.6
    assert W.brakeFade(340, 0.0, real) < W.brakeFade(340, 1.0, real) and W.brakeFade(900, 1.0, off) == 1, 'worn pads fade earlier; Off never fades'
    assert W.wornFade(500, 1.0, real) == 1 and W.wornFade(200, 0.0, real) == 1 and 0.8 < W.wornFade(340, 0.0, real) < 1, 'only the extra loss of a worn pad'
    assert abs(W.wornFade(500, 0.0, real) - W.brakeFade(500, 0.0, real) / W.brakeFade(500, 1.0, real)) < 1e-12
    assert abs(W.limitStep(1.0, 0.0, 1.0) - 0.9) < 1e-9 and abs(W.limitStep(0.0, 5.0, 2.0) - 0.2) < 1e-9 and W.limitStep(0.5, 0.52, 1.0) == 0.52
    # the slots: which wear kinds and corners a parts slot holds, by the slot's name (stock cars)
    def sw(slot):
        r = W.slotWear(slot)
        return sorted((r[i]["kind"], ",".join(r[i]["corners"][j] for j in range(1, len(r[i]["corners"]) + 1))) for i in range(1, len(r) + 1))
    assert sw("covet_coilover_F") == [("damper", "FL,FR"), ("spring", "FL,FR")]
    assert sw("vivace_shock_R_wide") == [("damper", "RL,RR")] and sw("vivace_spring_R") == [("spring", "RL,RR")]
    assert sw("pickup_desert_shock_SFA") == [("damper", "FL,FR")] and sw("pickup_desert_coilover_IFS") == [("damper", "FL,FR"), ("spring", "FL,FR")], "solid and independent front axles are front"
    assert sw("brakepad_F") == [("padF", "F")] and sw("brakepad_R") == [("padR", "R")] and sw("covet_brakepad_RRL") == [("padR", "R")]
    assert sw("etk800_brake_F") == [("rotor", "FL,FR")] and sw("bolide_brake_RR") == [("rotor", "RL,RR")]
    assert sw("vivace_engine_internals_i4_2.0_petrol") == [("engine", "all")] and sw("covet_engine") == [("engine", "all")] and sw("sunburst2_engine_2_0_internals") == [("engine", "all")]
    assert sw("covet_flywheel") == [("clutch", "all"), ("flywheel", "all")]
    assert sw("covet_steering") == [("steering", "all")] and sw("covet_power_steering") == [] and sw("covet_taillight_R_reverse_bulb") == [("lights", "all")]
    assert sw("covet_exhaust") == [("cat", "all"), ("exhaust", "all")] and sw("pickup_muffler") == [("cat", "all"), ("exhaust", "all")] and sw("sunburst2_exhaust_turbo_race") == [("cat", "all"), ("exhaust", "all")] and sw("vivace_exhaust_tips") == []
    assert sw("vivace_fueltank") == [("fuel", "all")] and sw("sunburst2_fuelcell_race") == [("fuel", "all")]
    assert sw("covet_swaybar_F") == [("swaybar", "F")] and sw("pickup_desert_swaybar_SFA") == [("swaybar", "F")] and sw("bolide_swaybar_RR") == [("swaybar", "R")]
    assert sw("covet_hub_F") == [("bearing", "FL,FR")] and sw("covet_hub_R") == [("bearing", "RL,RR")] and sw("covet_3wheel_hub_gears") == [] and sw("bolide_hub_RF") == []
    assert sw("covet_transmission") == [("gearbox", "all")] and sw("covet_differential_F") == [("diff", "F")] and sw("bolide_v6_differential_M") == [("diff", "all")]
    assert sw("covet_halfshafts_R") == [("cv", "R")] and sw("vivace_driveshaft") == [("cv", "F,R")] and sw("covet_radiator") == [("radiator", "all")] and sw("vivace_turbo_i4_1.5_diesel") == [("turbo", "all")]
    for none in ("covet_turbo_airbox", "covet_turbo_downpipe", "vivace_exhaust_tips", "ardente_exhaust_exit", "covet_oilpan", "covet_camshaft_race", "covet_header"):
        assert sw(none) == [], ("holds no wear item", none)
    for none in ("covet_hood", "etk800_strutbrace_F", "covet_strut_bar_F", "vivace_handbrake_race", "covet_pedalbox_clutch", "covet_enginemounts", "sunburst2_engine_1_6_intake", "covet_engine_ecu", "covet_boxutility_springs", ""):
        assert sw(none) == [], ("holds no wear item", none)
    # the slot names of the stock cars (covet, vivace, pickup, etk800, sunburst2, bolide) with the kinds and corners each holds: the table does not regress without the game's files
    import json
    fixture = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "slot_fixture.json"), encoding="utf8"))
    for slot, want in fixture.items():
        got = [[w["kind"], [w["corners"][j] for j in range(1, len(w["corners"]) + 1)]] for w in (W.slotWear(slot)[i] for i in range(1, len(W.slotWear(slot)) + 1))]
        assert got == want, (slot, got, want)
    assert sw("vivace_flywheel_lightweight") == [("clutch", "all"), ("flywheel", "all")], "a word of the slot name, not a part of one, drops a slot"
    print("wear rules ok: %d kinds, %d with factors that fall and %d with amounts that rise, all within bounds" % (len(KINDS), len(DOWN), len(UP)))


if __name__ == "__main__":
    main()
