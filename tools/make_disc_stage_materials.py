"""Worn brake disc stage materials: python tools/make_disc_stage_materials.py <path to BeamNG content/vehicles/common.zip>
The game's brake disc material `disc_brake` (shared by the disc, caliper and hub meshes of every car) gets two variants, slrr_disc_brake_worn and slrr_disc_brake_rusty: its own layers with
a tiled rust detail (colour, normal, roughness) laid over them by tools/make_disc_rust_textures.py. A file under vehicles/common, which the game loads with the first car (a switch target that is not in the
car's spawn set renders flat black); the engine only accepts a switch to a variant that the car carries from spawn, so the game side puts them in the glowMap (slr/partwear.lua, onJbeamLoadingPhase2):
on = worn, on_intense = rusty. The textures are referenced by path.
"""
import json, sys, uuid, zipfile, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'mod')
ART = '/art/slrr_partwear/'
NAME = 'disc_brake'
# state -> (colour detail strength, normal detail strength, roughness detail strength); the strengths are MODELLED: worn = a surface bloom, rusty = a pitted, orange disc
STAGES = {'worn': (0.55, 0.5, 0.5), 'rusty': (1.0, 1.0, 0.8)}
SCALE = [3, 3]          # the rust tiles three times across the disc's own atlas

z = zipfile.ZipFile(sys.argv[1])
src = {}
for n in z.namelist():
    if n.endswith('materials.json'):
        t = z.read(n).decode('utf8', 'ignore')
        if '"%s"' % NAME in t:
            try:
                src.update(json.loads(t))
            except ValueError:
                pass
m = src[NAME]
out = {}
for k, (cs, ns, rs) in STAGES.items():
    stages = []
    for st in m['Stages']:
        s = dict(st)
        if s.get('baseColorMap'):                  # the layers that draw the disc get the rust; an empty stage stays empty
            s.update(detailMap=ART + 'disc_rust_c.data.png', detailBaseColorMapStrength=cs, detailNormalMap=ART + 'disc_rust_n.normal.png', detailNormalMapStrength=ns,
                     roughnessDetailMap=ART + 'disc_rust_r.data.png', detailRoughnessMapStrength=rs, detailScale=SCALE)
        stages.append(s)
    v = {kk: vv for kk, vv in m.items() if kk not in ('Stages', 'name', 'mapTo', 'persistentId')}
    vn = 'slrr_%s_%s' % (NAME, k)
    v.update(name=vn, mapTo=vn, persistentId=str(uuid.uuid5(uuid.NAMESPACE_URL, vn)), Stages=stages)
    out[vn] = v
os.makedirs(os.path.join(OUT, 'vehicles/common/slrrPartWear'), exist_ok=True)
with open(os.path.join(OUT, 'vehicles/common/slrrPartWear/stages.materials.json'), 'w') as f:
    json.dump(out, f, indent=1)
print(len(out), 'variants of', NAME)
