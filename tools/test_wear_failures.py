"""Offline checks of the random failure rules (mod/lua/common/slrrFailRules.lua, docs/FAILURES.md).

    python tools/test_wear_failures.py

The safety checks: a healthy or serviced part never fails, the chance only rises as the part wears and with stress, frequency 0 is never, the switches and the master switch hold, a failure is
announced first (and cancelled by stopping), a failed part cannot fail twice, garbage inputs never raise, and every rule has the texts and a result the car side can apply.
"""
import math, os, random
from lupa.luajit21 import LuaRuntime

HERE = os.path.dirname(os.path.abspath(__file__))
lua = LuaRuntime(unpack_returned_tuples=True)
F = lua.execute(open(os.path.join(HERE, "..", "mod", "lua", "common", "slrrFailRules.lua"), encoding="utf8").read())
KINDS = lua.execute(open(os.path.join(HERE, "..", "mod", "lua", "common", "slrrWearRules.lua"), encoding="utf8").read()).KINDS
T = lua.table_from
ORDER = [F.ORDER[i] for i in range(1, len(F.ORDER) + 1)]
S = lambda **kw: T(dict({"failures": True, "failureRate": 1}, **kw))  # noqa: E731


def check(cond, what):
    if not cond:
        raise SystemExit("wear failures FAIL: " + what)


# the wear term
check(F.wear(1) == 0 and F.wear(0.5) == 0 and F.wear(0.9) == 0, "a part at 0.5 or better has no wear term")
check(abs(F.wear(0.25) - 0.25) < 1e-9 and abs(F.wear(0.1) - 0.64) < 1e-9 and F.wear(0) == 1, "the wear term is squared below 0.5")
check(all(F.wear(a / 100) >= F.wear(b / 100) for a, b in zip(range(0, 100), range(1, 101))), "a worse part never has a smaller wear term")
check(F.wear(None) == 0 and F.wear(float("nan")) == 0 and F.wear(-3) == 1 and F.wear(9) == 0, "garbage conditions are clamped")

# the rules: every id has what the car side needs
for i in ORDER:
    r = F.RULES[i]
    check(r.base > 0 and r.base < 0.05, i + ": a plausible base hazard")
    check(r.failText and len(r.failText) > 10, i + ": a failure text")
    check(r.warn == 0 or (r.warnText and r.warn >= 10 and r.warn <= 120), i + ": a warning text and time, or sudden")
    res = r.result
    check(res.game or res.drop, i + ": a result")
    if res.drop:
        check(res.drop in KINDS and 0 < res.level < 0.2, i + ": the drop is a real kind at a low level")
    for k in [r.kinds[j] for j in range(1, len(r.kinds) + 1)]:
        check(k in KINDS, i + ": reads the real kind " + k)
    check(r.group in ("engine", "drive", "electrics"), i + ": a known group")

# healthy and serviced: never
conds = T({"cv": 0.5, "engine": 0.9, "oil": 1, "radiator": 0.5})
check(all(F.hazard(i, F.conditionOf(i, conds), T({"coolantC": 130, "rpmFrac": 1, "launches": 9}), S()) == 0 for i in ORDER), "a part at 0.5 or better has no hazard however hard it is driven")
rng = random.Random(1)
st = F.newState()
fails = 0
for _ in range(20000):                                    # 20000 minutes of the worst driving on healthy parts
    ev = F.tick(st, conds, T({"coolantC": 130, "rpmFrac": 1, "launches": 9}), 60, S(), rng.random, T({"driving": True}))
    fails += sum(1 for k in range(1, len(ev) + 1) if ev[k].event in ("warn", "fail"))
check(fails == 0, "healthy parts never fail or warn over 20000 minutes of the worst use")

# the chance rises with the wear and with the stress
worn = {"engine": 0.2, "oil": 0.2, "radiator": 0.2, "cv": 0.2, "diff": 0.2, "gearbox": 0.2, "clutch": 0.2, "turbo": 0.2, "fuel": 0.2, "alternator": 0.2}
for i in ORDER:
    h = [F.hazard(i, F.conditionOf(i, T({k: c / 100 for k in worn})), T({}), S()) for c in (50, 40, 30, 20, 10, 0)]
    check(h[0] == 0 and all(a <= b for a, b in zip(h, h[1:])) and h[-1] > 0, i + ": the hazard rises as the part wears")
check(F.stress("head_gasket", T({"coolantC": 80})) < F.stress("head_gasket", T({"coolantC": 100})) < F.stress("head_gasket", T({"coolantC": 115})) < F.stress("head_gasket", T({"coolantC": 125})),
      "overheating raises the head gasket stress")
check(F.stress("head_gasket", T({"coolantC": 500})) == 10 and F.stress("head_gasket", T({"coolantC": 20})) >= 0.1, "the stress is capped and floored")
check(F.stress("rod_bearings", T({"oilLevel": 0.2, "oil": 0.1, "rpmFrac": 1})) > F.stress("rod_bearings", T({"oilLevel": 1, "oil": 1, "rpmFrac": 0.3})), "low oil and high revs raise the bottom-end stress")
check(F.stress("axle", T({"launches": 3, "landings": 2})) > F.stress("axle", T({})), "launches and landings raise the axle stress")
check(F.stress("nope", T({})) == 1 and F.stress("axle", None) == 1 and F.stress("axle", T({"launches": "x"})) == 1, "unknown rules and garbage inputs are stress 1")

# frequency, master switch, groups
cw = T({"engine": 0.1, "oil": 0.1, "radiator": 0.1})
h1 = F.hazard("head_gasket", 0.1, T({"coolantC": 110}), S(failureRate=1))
check(F.hazard("head_gasket", 0.1, T({"coolantC": 110}), S(failureRate=0)) == 0, "frequency 0 is never")
check(abs(F.hazard("head_gasket", 0.1, T({"coolantC": 110}), S(failureRate=3)) - 3 * h1) < 1e-12 and F.hazard("head_gasket", 0.1, T({"coolantC": 110}), S(failureRate=9)) == F.hazard("head_gasket", 0.1, T({"coolantC": 110}), S(failureRate=3)), "frequency scales the hazard and is capped at 3")
check(F.hazard("head_gasket", 0.1, T({}), T({"failures": False, "failureRate": 1})) == 0 and F.hazard("head_gasket", 0.1, T({}), None) == 0, "the master switch off: no hazard")
check(F.hazard("head_gasket", 0.1, T({}), S(failEngine=False)) == 0 and F.hazard("axle", 0.1, T({}), S(failEngine=False)) > 0, "a group off silences only that group")
check(F.hazard("axle", 0.1, T({}), S(failDrive=False)) == 0 and F.hazard("alternator", 0.1, T({}), S(failElectrics=False)) == 0, "the drive and electrics groups")

# the chance maths
check(F.chance(0, 5) == 0 and abs(F.chance(1, 1) - (1 - math.exp(-1))) < 1e-12 and F.chance(1e9, 1) == 1 and F.chance(-1, 1) == 0 and F.chance(None, 1) == 0, "the chance of a roll")
check(F.expectedMinutes(0) == math.inf and abs(F.expectedMinutes(0.1) - 10) < 1e-9, "the expected minutes")


# the machine: a worn part, the worst stress: warn, then fail after the warning, and only once
def run(seed, minutes, conds, inp, settings, ctx, dt=1.0):
    r = random.Random(seed)
    st = F.newState()
    log = []
    for sec in range(int(minutes * 60 / dt)):
        ev = F.tick(st, conds, inp, dt, settings, r.random, ctx)
        for k in range(1, len(ev) + 1):
            log.append((sec * dt, ev[k].id, ev[k].event))
    return st, log


bad = T({"engine": 0.02, "oil": 0.02, "radiator": 0.02})
hot = T({"coolantC": 125, "rpmFrac": 1, "oilLevel": 0.2, "oil": 0.02})
st, log = run(7, 300, bad, hot, S(failureRate=3), T({"driving": True}))
byid = {}
for t, i, e in log:
    byid.setdefault(i, []).append((t, e))
check("head_gasket" in byid and byid["head_gasket"][0][1] == "warn" and byid["head_gasket"][1][1] == "fail", "a worn overheating engine warns first and then fails")
check(abs((byid["head_gasket"][1][0] - byid["head_gasket"][0][0]) - F.RULES.head_gasket.warn) <= 2, "the failure comes after the warning time")
check(sum(1 for t, e in byid["head_gasket"] if e == "fail") == 1 and st.failed["head_gasket"], "a failed part fails once")
# warnings off: sudden
st, log = run(7, 300, bad, hot, S(failureRate=3, failureWarnings=False), T({"driving": True}))
check(log and all(e == "fail" for _, _, e in log), "with warnings off every failure is sudden")
# a sudden kind (the clutch) never warns
st, log = run(3, 300, T({"clutch": 0.02}), T({"launches": 5}), S(failureRate=3), T({"driving": True}))
check(log and all(e == "fail" for _, i, e in log if i == "clutch"), "the clutch fails without a warning")
# nothing happens when not driving, with the master off, or racing with never-racing on
for name, sett, ctx in (("parked", S(failureRate=3), T({"driving": False})), ("master off", T({"failures": False, "failureRate": 3}), T({"driving": True})),
                        ("racing", S(failureRate=3, failureNeverRacing=True), T({"driving": True, "racing": True}))):
    st, log = run(7, 300, bad, hot, sett, ctx)
    check(not log, name + ": no failure")
st, log = run(7, 300, bad, hot, S(failureRate=3, failureNeverRacing=False), T({"driving": True, "racing": True}))
check(log, "racing with never-racing off: failures can happen")
# stopping with the engine off cancels a pending failure and gives a cooldown
st = F.newState()
ev = F.force(st, "rod_bearings", S())
check(ev[1].event == "warn" and st.pending["rod_bearings"] == F.RULES.rod_bearings.warn, "force starts the warning")
r = random.Random(1)
for _ in range(12):
    ev = F.tick(st, bad, hot, 1.0, S(), r.random, T({"stopped": True}))
check(st.pending["rod_bearings"] is None and st.cooldown["rod_bearings"] is not None and not st.failed["rod_bearings"], "stopping with the engine off cancels the failure and rests the kind")
check(len(F.force(st, "rod_bearings", S())) == 1, "forced again after a cancel is allowed (a debug call)")
# a forced failure runs through to the end; a failed part cannot be forced or fail again
st = F.newState()
F.force(st, "axle", S())
r = random.Random(2)
out = []
for _ in range(20):
    ev = F.tick(st, T({}), T({}), 1.0, S(), r.random, T({"driving": True}))
    out += [ev[k].event for k in range(1, len(ev) + 1)]
check(out == ["fail"] and st.failed["axle"], "a forced failure ends in one failure after the warning")
check(len(F.force(st, "axle", S())) == 0, "a failed part cannot be forced")
F.clearFailed(st, "axle")
check(len(F.force(st, "axle", S())) == 1, "a repaired part can fail again")
check(len(F.force(st, "nope", S())) == 0, "an unknown rule is ignored")
# garbage never raises (nil, strings, NaN, huge steps, no settings)
st = F.newState()
nan = float("nan")
for conds_, inp_, dt_, set_, ctx_ in ((None, None, None, None, None), (T({"cv": "x", "engine": nan}), T({"coolantC": "x", "rpmFrac": nan}), 1e9, S(), T({"driving": True})),
                                     (T({"cv": -5}), T({"launches": -1}), -5, T({"failures": True, "failureRate": "x"}), T({"driving": True, "stopped": True}))):
    try:
        F.tick(st, conds_, inp_, dt_, set_, random.random, ctx_)
        F.report(conds_, inp_, set_)
    except Exception as e:  # noqa: BLE001
        raise SystemExit("wear failures FAIL: garbage raised: %s" % e)
rep = F.report(T({"engine": 0.1, "oil": 0.1}), T({"coolantC": 110}), S())
check(len(rep) == len(ORDER) and rep[1].id == "head_gasket" and rep[1].perMinute > 0, "the debug report lists every rule")
# the expected time to failure of the doc: a worn-out part under the worst stress
h = F.hazard("head_gasket", 0, T({"coolantC": 200}), S())
check(abs(F.expectedMinutes(h) - 10) < 1e-6, "the doc's example: a dead head gasket at the stress cap fails in about 10 minutes")
print("wear failures ok: %d rules, healthy parts never fail, warnings, cancel, switches, seeded" % len(ORDER))
