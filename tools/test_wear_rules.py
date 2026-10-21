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
        "clutch": ["lockTorque"], "battery": ["crank"], "alternator": ["charge"]}
UP = {"spring": ["sagMm"], "bearing": ["humVolume"], "padF": ["squealLow", "glazing"], "engine": ["dynFriction", "misfire"], "ignition": ["misfire"],
      "clutch": ["freePlay"], "gearbox": ["friction"], "diff": ["friction"], "exhaust": ["gainDb"]}
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
    print("wear rules ok: %d kinds, %d with factors that fall and %d with amounts that rise, all within bounds" % (len(KINDS), len(DOWN), len(UP)))


if __name__ == "__main__":
    main()
