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
ZIPS = None          # every zip next to common.zip (the other models' own materials are in their own zips)
# the strengths (colour, normal, roughness detail) per state are MODELLED: worn = a surface bloom (discs) or grime with a little rust (metal), rusty = pitted orange rust
DISC = {'worn': (0.55, 0.5, 0.5), 'rusty': (1.0, 1.0, 0.8)}
MECH = {'worn': (0.3, 0.35, 0.5), 'rusty': (0.45, 0.8, 0.7)}      # (the colour detail adds to the base: at 1.0 the patches glowed like embers on the Vivace's black floor pan, 80's frame)
# shortcut: the detail colour is additive (the game tiles only the detail maps: a blended layer with its own rust map would be sampled with the atlas UVs untiled, so it would have to ship
# at atlas size, about 11 MB a set), so a dark atlas needs a lower strength than a light one: the Vivace's mechanical atlas is near-black and still glowed like embers at 0.45 (80's frame).
# Upgrade when the engine takes a per-layer tiling for a blended layer.
MECH_DARK = {'worn': (0.1, 0.35, 0.5), 'rusty': (0.15, 0.8, 0.7)}
# the rims: 'worn' = brake dust and kerb scuffs (rim_grime), 'rusty' = the steel rim's rust (mech_rust); a strengths entry may name its own texture set as a 4th value
RIM = {'worn': (0.7, 0.5, 0.5, 'rim_grime'), 'rusty': (0.45, 0.8, 0.7, 'mech_rust')}
# the cabin and seats: 'worn' = faded, lightly creased; 'rusty' = the heavy wear (the stage names are the file's: no rust on upholstery). Only materials with no detail layer of their own and no
# emissive stage (a detail layer would replace theirs; the dash lights stay as they are): the Covet, Vivace and pickup interiors and the seat materials of the game's racing, offroad and vintage seats
INT = {'worn': (0.35, 0.35, 0.4, 'seat_wear'), 'rusty': (0.7, 0.7, 0.6, 'seat_wear')}
INTERIOR = ['covet_interior', 'covet_interior_flocked', 'vivace_interior', 'pickup_interior', 'racing_seat', 'racing_seat_blue', 'racing_seat_green', 'racing_seat_red', 'racingseat',
            'offroad_seat', 'offroad_seat_blue', 'offroad_seat_red', 'offroad_seat_yellow', 'vintageseat_01', 'vintageseat_01_red', 'vintageseat_01_tan']
# the other models of the car pool (82's survey of the stock cars' exhaust meshes: Graph docs/data/exhaust_mesh_materials_by_car.json): the metal (suspension, frame, exhaust) and the engine material
# of each; the metal gets the low strengths of the Vivace's near-black atlas (their atlases were not measured: 80 tunes each in the game), the engine the bay strengths. model = the JBeam folder name.
MODELS = {
    'bastion': {'metal': 'bastion_mechanical'}, 'racetruck': {'engine': 'bastion_engine'}, 'atv': {'engine': 'atv_engine'}, 'autobello': {'engine': 'autobello_engine'},
    'bolide': {'metal': 'bolide_mechanical', 'engine': 'bolide_engine'}, 'legran': {'metal': 'bruckell_mechanical', 'engine': 'bruckell_engine'},
    'lansdale': {'metal': 'bruckell_mechanical', 'engine': 'bruckell_engine'}, 'wendover': {'metal': 'bruckell_mechanical', 'engine': 'bruckell_engine'},
    'burnside': {'engine': 'burnside_v8'}, 'bx': {'metal': 'bx_mechanicals', 'engine': 'ibishu_engine'}, 'etki': {'metal': 'etki_mechanicals', 'engine': 'etki_engine'},
    'midsize': {'metal': 'midsize_mechanical', 'engine': 'midsize_engines'}, 'midtruck': {'engine': 'midtruck_engine_petrol'}, 'miramar': {'engine': 'miramar_engine'},
    'moonhawk': {'engine': 'moonhawk_engines'}, 'nine': {'metal': 'nine_mechanicals', 'engine': 'flathead_engines'}, 'pessima': {'engine': 'pessima_engine'},
    'pigeon': {'engine': 'pigeon_engine'}, 'wigeon': {'engine': 'pigeon_engine'}, 'sbr': {'engine': 'boxer_engine'}, 'scintilla': {'engine': 'scintilla_engine'},
    'sunburst2': {'metal': 'sunburst2_mechanicals'}, 'utv': {'engine': 'utv_engine'}, 'van': {'metal': 'trucks_mechanical', 'engine': 'gavril_v8'}, 'fullsize': {'engine': 'gavril_v8'},
    'dumptruck': {'metal': 'dumptruck_frame', 'engine': 'dumptruck_engine'}, 'wl40': {'metal': 'dumptruck_frame', 'engine': 'dumptruck_engine'}, 'percheron': {'engine': 'percheron_engine'},
}
BAY = {'worn': (0.5, 0.25, 0.5), 'rusty': (1.0, 0.4, 1.0)}        # the engine bay: 'worn' = dust with a little oil, 'rusty' = heavy oily grime (the stage names are the file's, not rust)
# (material, texture set, strengths, detail scale: the set tiles this many times across the material's own atlas)
MATERIALS = [('disc_brake', 'disc_rust', DISC, 3), ('covet_mechanical', 'mech_rust', MECH, 4), ('vivace_mechanical', 'mech_rust', MECH_DARK, 4), ('trucks_mechanical', 'mech_rust', MECH, 4),
             ('ibishu_engine', 'bay_grime', BAY, 4), ('vivace_engine', 'bay_grime', BAY, 4), ('gavril_v8', 'bay_grime', BAY, 4)]


MATERIALS += [(i, None, INT, 5) for i in INTERIOR]
_have = {m[0] for m in MATERIALS}
for _model, _mats in sorted(MODELS.items()):
    for _kind, _mat in sorted(_mats.items()):
        if _mat not in _have:
            _have.add(_mat)
            MATERIALS.append((_mat, 'mech_rust' if _kind == 'metal' else 'bay_grime', MECH_DARK if _kind == 'metal' else BAY, 4))


def rim_materials(folder):
    """the rim materials of the stock wheels of the test cars: each wheel part of every stock configuration (.pc) is named <rim material>_<size>_<F|R>..., so the part name with its size
    and axle left off is the material, if the game has one (the zips' materials.json)"""
    import re
    names = set()
    for zn in ('covet.zip', 'vivace.zip', 'pickup.zip'):
        z = zipfile.ZipFile(os.path.join(folder, zn))
        for n in z.namelist():
            if n.endswith('.pc'):
                try:
                    parts = json.loads(z.read(n).decode('utf8', 'ignore')).get('parts', {})
                except ValueError:
                    continue
                for slot, part in parts.items():
                    if part and re.match(r'(wheel_[FR]_|.*sparewheel)', slot):
                        names.add(re.sub(r'_\d+x\d+(\.\d+)?(_\d+)?(_[FR])?(_.*)?$', '', part))
    return names


wanted = {m[0] for m in MATERIALS}
src = {}
folder = os.path.dirname(os.path.abspath(sys.argv[1]))
ZIPS = sorted(f for f in os.listdir(folder) if f.endswith('.zip'))
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
rims = rim_materials(folder)
rimsFound = set()
for zn in ZIPS:
    z = zipfile.ZipFile(os.path.join(folder, zn))
    for n in z.namelist():
        if n.endswith('materials.json'):
            t = z.read(n).decode('utf8', 'ignore')
            if any('"%s"' % w in t for w in rims):
                try:
                    found = {k: v for k, v in json.loads(t).items() if k in rims and v.get('Stages') and v['Stages'][0].get('baseColorMap')}
                except ValueError:
                    continue
                src.update(found)
                rimsFound.update(found)
MATERIALS += [(r, None, RIM, 3) for r in sorted(rimsFound)]
wanted |= rimsFound
missing = wanted - set(src)
assert not missing, 'not found in the zips: %s' % sorted(missing)
out = {}
for name, tex, strengths, scale in MATERIALS:
    m = src[name]
    for k, st3 in strengths.items():
        cs, ns, rs = st3[:3]
        tex = st3[3] if len(st3) > 3 else tex
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
# the list for the game side (slrr/partwear.lua, onJbeamLoadingPhase2): the rim materials that have worn and rusty variants (the stock wheels of the Covet, Vivace and pickup)
with open(os.path.join(OUT, 'lua/common/slrrWearLookList.lua'), 'w') as f:
    f.write('-- made by tools/make_disc_stage_materials.py: the rim materials that have slrr_<name>_worn / _rusty stage variants (the stock wheels of the Covet, Vivace and pickup)\n')
    f.write('return { rims = {\n')
    for r in sorted(rimsFound):
        f.write("  '%s',\n" % r)
    f.write('}, models = {\n')
    for model, mats in sorted(MODELS.items()):
        f.write("  %s = { %s },\n" % (model, ', '.join("%s = '%s'" % (k, v) for k, v in sorted(mats.items()))))
    f.write('}, interior = {\n')
    for r in INTERIOR:
        f.write("  '%s',\n" % r)
    f.write('} }\n')
print(len(out), 'variants of', ', '.join(m[0] for m in MATERIALS))
print(len(rimsFound), 'rim materials')
