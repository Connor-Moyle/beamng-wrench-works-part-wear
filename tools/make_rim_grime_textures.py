"""Detail textures of the worn wheel look: brake dust and kerb scuffs on the rim's own material, from a CC0 photograph (ambientCG Asphalt033 for the dust's grain and tone;
docs/TEXTURE_CREDITS.md) and drawn scratches. The 'rusty' stage of a rim reuses the mech_rust set (a steel rim rusts like the suspension); this set is the 'worn' stage.

    python tools/make_rim_grime_textures.py [raw folder with grime/Asphalt033/] [out folder]

Writes to mod/art/slrr_partwear/ three 512 x 512 detail maps that tile (the stage materials lay them over the rim's own maps at detailScale 3):
  rim_grime_c.data.png   colour detail: 0.5 = no change; below it brake dust darkens the metal in a warm brown film, above it kerb scuffs show as bright bare-metal scratches
  rim_grime_n.normal.png normal detail: the scratches cut grooves, the dust has the photograph's fine grain
  rim_grime_r.data.png   roughness detail: dust is rougher (matte), the scratches are rougher too (torn metal)
PNG here; the game cooks them to DDS on first use and the DDS replace the PNGs (tools/test_wear_textures.py).
"""
import glob, os, sys
import numpy as np
from PIL import Image, ImageDraw
from make_disc_rust_textures import periodic_noise, smooth, save, OUT, N

RAW = sys.argv[1] if len(sys.argv) > 1 else r'C:\Dev\csfx-textures-raw'


def photo(sub, mode='RGB'):
    p = glob.glob(os.path.join(RAW, sub))
    if not p:
        sys.exit('missing ' + sub + ' in ' + RAW)
    return np.asarray(Image.open(p[0]).convert(mode).resize((N, N), Image.LANCZOS), np.float32) / 255.0


def scratches(rng, count):
    """short thin lines 0..1 that tile: each is drawn nine times, shifted by the tile size, and the middle copy is kept"""
    im = Image.new('L', (3 * N, 3 * N), 0)
    d = ImageDraw.Draw(im)
    for _ in range(count):
        x, y = rng.random() * N, rng.random() * N
        ang = rng.normal(0.6, 0.5)                                     # kerb rash runs in one rough direction
        ln = 10 + rng.random() * 60
        for ox in (0, N, 2 * N):
            for oy in (0, N, 2 * N):
                d.line([(x + ox, y + oy), (x + ox + ln * np.cos(ang), y + oy + ln * np.sin(ang))], fill=int(120 + rng.random() * 135), width=1 + int(rng.random() * 1.5))
    return np.asarray(im, np.float32)[N:2 * N, N:2 * N] / 255.0


# MODELLED: brake dust is a fine, even brown-black film that gathers in blotches; kerb scuffs are scattered short scratches
rng = np.random.default_rng(73)
blotch = smooth(periodic_noise(rng, 4, 5), 0.35, 0.75)
film = 0.4 + 0.6 * blotch
grain = photo('grime/Asphalt033/*_Color.jpg', 'L') ** 2.2                    # sRGB photograph to linear
scuff = scratches(rng, 140)
dust = film * (0.55 + 0.45 * grain)
delta = -0.5 * dust[..., None] * np.array([0.8, 0.9, 1.0], np.float32) + 0.35 * scuff[..., None]
save(0.5 + 0.5 * np.clip(delta, -1, 1), 'rim_grime_c.data.png')
n = photo('grime/Asphalt033/*_NormalGL.jpg')
flat = np.array([0.5, 0.5, 1.0], np.float32)
gy, gx = np.gradient(scuff)
groove = np.stack([0.5 - 6 * gx, 0.5 - 6 * gy, np.ones_like(scuff)], -1)
save(flat + (n - flat) * (0.3 * film)[..., None] + (np.clip(groove, 0, 1) - flat) * (scuff > 0.05)[..., None], 'rim_grime_n.normal.png')
save((0.5 + 0.5 * np.clip(0.45 * dust + 0.4 * scuff, -1, 1))[..., None].repeat(3, -1), 'rim_grime_r.data.png')
print('wrote rim_grime_c.data.png, rim_grime_n.normal.png, rim_grime_r.data.png to', os.path.abspath(OUT))
