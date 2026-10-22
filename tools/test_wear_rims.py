"""The worn wheel look's stage materials (made by tools/make_disc_stage_materials.py): every rim material of the list (mod/lua/common/slrrWearLookList.lua) has a worn and a rusty variant,
named and mapped alike with its own persistent id, the rim's own maps kept and a detail layer added to the stages that draw it (brake dust and scuffs for worn, the metal rust for rusty).

    python tools/test_wear_rims.py
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mod')
stages = json.load(open(os.path.join(ROOT, 'vehicles', 'common', 'slrrPartWear', 'stages.materials.json')))
text = open(os.path.join(ROOT, 'lua', 'common', 'slrrWearLookList.lua')).read()
rims = re.findall(r"^  '([^']+)',$", text, re.M)
bad = []
if len(rims) < 30:
    bad.append('the list has only %d rim materials' % len(rims))
ids = set()
for v in stages.values():
    ids.add(v['persistentId'])
if len(ids) != len(stages):
    bad.append('persistent ids are not unique')
for r in rims:
    if '.skin' in r or r == 'disc_brake':
        bad.append(r + ' is not a plain rim material')
    for state, tex in (('worn', 'rim_grime'), ('rusty', 'mech_rust')):
        n = 'slrr_%s_%s' % (r, state)
        m = stages.get(n)
        if not m:
            bad.append(n + ' is missing')
            continue
        if m['name'] != n or m['mapTo'] != n:
            bad.append(n + ': name and mapTo must be the variant name')
        drawn = [s for s in m['Stages'] if s.get('baseColorMap')]
        if not drawn:
            bad.append(n + ' draws nothing')
        for s in drawn:
            if not s.get('detailMap', '').endswith('/' + tex + '_c.data.png') or not s.get('detailNormalMap', '').endswith('/' + tex + '_n.normal.png') or 'roughnessDetailMap' not in s:
                bad.append(n + ': the detail layer is not the ' + tex + ' set')
            if not all(0 < s[k] <= 1 for k in ('detailBaseColorMapStrength', 'detailNormalMapStrength', 'detailRoughnessMapStrength')):
                bad.append(n + ': a detail strength is out of 0..1')
        for s in m['Stages']:
            if not s.get('baseColorMap') and ('detailMap' in s):
                bad.append(n + ': an empty stage got a detail layer')
if bad:
    print('wear rims FAIL:')
    for b in bad:
        print('  ' + b)
    sys.exit(1)
print('wear rims ok: %d rim materials, worn and rusty variants, %d stage materials in all' % (len(rims), len(stages)))
