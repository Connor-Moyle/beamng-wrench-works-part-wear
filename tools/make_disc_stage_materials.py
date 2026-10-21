"""Worn stage materials of the part wear look: python tools/make_disc_stage_materials.py <path to BeamNG content/vehicles/common.zip>
Every material in MATERIALS gets two variants, slrr_<name>_worn and slrr_<name>_rusty: the game's own layers with a tiled detail (colour, normal, roughness) laid over them from the
named texture set (disc_rust: tools/make_disc_rust_textures.py; mech_rust: tools/make_mech_rust_textures.py). The brake disc material `disc_brake` is shared by the disc, caliper and hub
meshes of every car; the mechanical materials carry a model's suspension, frame and exhaust (read from the game's vehicle files). One file under vehicles/common, which the game loads with the first car (a
switch target that is not in the car's spawn set renders flat black); the engine only accepts a switch to a variant that the car carries from spawn, so the game side puts them in the
glowMap (slr/partwear.lua, onJbeamLoadingPhase2): the discs on = worn, on_intense = rusty; the mechanical materials off = the stage. The textures are referenced by path. The source
materials are read from the zips next to common.zip (ZIPS).
"""
import json, sys, uuid, zipfile, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'mod')
ART = '/art/slrr_partwear/'
ZIPS = ['common.zip', 'covet.zip', 'vivace.zip']
# the strengths (colour, normal, roughness detail) per state are MODELLED: worn = a surface bloom (discs) or grime with a little rust (metal), rusty = pitted orange rust
DISC = {'worn': (0.55, 0.5, 0.5), 'rusty': (1.0, 1.0, 0.8)}
MECH = {'worn': (0.3, 0.35, 0.5), 'rusty': (0.45, 0.8, 0.7)}      # (the colour detail adds to the base: at 1.0 the patches glowed like embers on the Vivace's black floor pan, 80's frame)
MECH_DARK = {'worn': (0.1, 0.35, 0.5), 'rusty': (0.15, 0.8, 0.7)}   # the Vivace's mechanical atlas is near-black: the added colour that reads as rust on the Covet's and pickup's lighter metal still glowed at 0.45 (80's second frame)
BAY = {'worn': (0.5, 0.25, 0.5), 'rusty': (1.0, 0.4, 1.0)}        # the engine bay: 'worn' = dust with a little oil, 'rusty' = heavy oily grime (the stage names are the file's, not rust)
# (material, texture set, strengths, detail scale: the set tiles this many times across the material's own atlas)
MATERIALS = [('disc_brake', 'disc_rust', DISC, 3), ('covet_mechanical', 'mech_rust', MECH, 4), ('vivace_mechanical', 'mech_rust', MECH_DARK, 4), ('trucks_mechanical', 'mech_rust', MECH, 4),
             ('ibishu_engine', 'bay_grime', BAY, 4), ('vivace_engine', 'bay_grime', BAY, 4), ('gavril_v8', 'bay_grime', BAY, 4)]

wanted = {m[0] for m in MATERIALS}
src = {}
folder = os.path.dirname(os.path.abspath(sys.argv[1]))
for zn in ZIPS:
    z = zipfile.ZipFile(os.path.join(folder, zn))
    for n in z.namelist():
        if n.endswith('materials.json'):
            t = z.read(n).decode('utf8', 'ignore')
            if any('"%s"' % w in t for w in wanted):
                try:
                    src.update({k: v for k, v in json.loads(t).items() if k in wanted})
                except ValueError:
                    pass
missing = wanted - set(src)
assert not missing, 'not found in the zips: %s' % sorted(missing)
out = {}
for name, tex, strengths, scale in MATERIALS:
    m = src[name]
    for k, (cs, ns, rs) in strengths.items():
        stages = []
        for st in m['Stages']:
            s = dict(st)
            if s.get('baseColorMap'):                  # the layers that draw the part get the detail; an empty stage stays empty
                s.update(detailMap=ART + tex + '_c.data.png', detailBaseColorMapStrength=cs, detailNormalMap=ART + tex + '_n.normal.png', detailNormalMapStrength=ns,
                         roughnessDetailMap=ART + tex + '_r.data.png', detailRoughnessMapStrength=rs, detailScale=[scale, scale])
            stages.append(s)
        v = {kk: vv for kk, vv in m.items() if kk not in ('Stages', 'name', 'mapTo', 'persistentId')}
        vn = 'slrr_%s_%s' % (name, k)
        v.update(name=vn, mapTo=vn, persistentId=str(uuid.uuid5(uuid.NAMESPACE_URL, vn)), Stages=stages)
        out[vn] = v
os.makedirs(os.path.join(OUT, 'vehicles/common/slrrPartWear'), exist_ok=True)
with open(os.path.join(OUT, 'vehicles/common/slrrPartWear/stages.materials.json'), 'w') as f:
    json.dump(out, f, indent=1)
print(len(out), 'variants of', ', '.join(m[0] for m in MATERIALS))
