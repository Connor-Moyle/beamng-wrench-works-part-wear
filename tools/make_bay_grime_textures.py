"""Detail textures of the worn engine bay look: oily grime and dust on the engine's own material, from CC0 photographs (ambientCG Asphalt033 for the grime's tone and grain, Ground080 for
the dust's tint; docs/TEXTURE_CREDITS.md). Not rust: a tired, oily engine.

    python tools/make_bay_grime_textures.py <raw folder with grime/Asphalt033/ and dirt/Ground080/> [out folder]

Writes to mod/art/slrr_partwear/ three 512 x 512 detail maps that tile (the stage materials lay them over the engine's own atlas at detailScale 4):
  bay_grime_c.data.png   colour detail: 0.5 = no change; below it oily grime darkens the metal in blotches, a little above it a warm dust film everywhere
  bay_grime_n.normal.png normal detail: a faint grain under the grime (the photograph's), flat elsewhere
  bay_grime_r.data.png   roughness detail: the oily blotches are smoother (they shine), the dust is rougher (matte)
PNG here; the game cooks them to DDS on first use and the DDS replace the PNGs (tools/test_wear_textures.py).
"""
import glob, os, sys
import numpy as np
from PIL import Image
from make_disc_rust_textures import periodic_noise, smooth, save, OUT, N

RAW = sys.argv[1] if len(sys.argv) > 1 else r'C:\Dev\csfx-textures-raw'


def photo(sub, mode='RGB'):
    p = glob.glob(os.path.join(RAW, sub))
    if not p:
        sys.exit('missing ' + sub + ' in ' + RAW)
    return np.asarray(Image.open(p[0]).convert(mode).resize((N, N), Image.LANCZOS), np.float32) / 255.0


# MODELLED: oil and road grime gather in blotches (round gaskets, the lower block); dust is a fine, even film
oily = smooth(periodic_noise(np.random.default_rng(31), 3, 5), 0.42, 0.72)
dust = 0.35 + 0.65 * periodic_noise(np.random.default_rng(47), 8, 3)
grain = photo('grime/Asphalt033/*_Color.jpg', 'L') ** 2.2                                   # sRGB photograph to linear
tint = photo('dirt/Ground080/*_Color.jpg', 'L') ** 2.2
delta = -0.6 * (oily * (0.5 + 0.5 * grain))[..., None] + (0.12 * dust * (0.6 + 0.4 * tint))[..., None] * np.array([0.9, 0.75, 0.5], np.float32)
save(0.5 + 0.5 * np.clip(delta, -1, 1), 'bay_grime_c.data.png')
n = photo('grime/Asphalt033/*_NormalGL.jpg')
flat = np.array([0.5, 0.5, 1.0], np.float32)
save(flat + (n - flat) * (0.35 * oily)[..., None], 'bay_grime_n.normal.png')
save((0.5 + 0.5 * np.clip(-0.5 * oily + 0.4 * dust, -1, 1))[..., None].repeat(3, -1), 'bay_grime_r.data.png')
print('wrote bay_grime_c.data.png, bay_grime_n.normal.png, bay_grime_r.data.png to', os.path.abspath(OUT))
