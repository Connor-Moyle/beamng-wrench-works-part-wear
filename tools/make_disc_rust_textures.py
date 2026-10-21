"""Detail textures of the worn brake disc look, made from a REAL CC0 photograph set of rust (ambientCG Rust005, see docs/TEXTURE_CREDITS.md).

    python tools/make_disc_rust_textures.py <raw folder with Rust005/ (Color, NormalGL, Roughness jpg)> [out folder]

The raw folder is OUTSIDE the mod (the downloads are untrusted). Writes to mod/art/slrr_partwear/: three 512 x 512 detail maps that tile (ambientCG's sets are seamless, the patch mask is periodic):
  disc_rust_c.data.png   colour detail: 0.5 = no change; the engine adds (d * 2 - 1) x strength to the base colour (linear): orange-brown rust patches where the mask is high
  disc_rust_n.normal.png normal detail: the photograph's pitting, laid over the disc's own normal
  disc_rust_r.data.png   roughness detail: rust is rougher than polished steel
Textures are PNG here; the game cooks them to BC7 / BC5 DDS on first use, and the DDS replace the PNGs once cooked (the tyre overlays' rule: tools/make_tyre_stage_textures.py in Car Surface FX).
"""
import os, sys, glob
import numpy as np
from PIL import Image

N = 512
RAW = sys.argv[1] if len(sys.argv) > 1 else r'C:\Dev\csfx-textures-raw\rust\disc'
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), '..', 'mod', 'art', 'slrr_partwear')


def load(pattern, mode='RGB'):
    p = glob.glob(os.path.join(RAW, '*', pattern))
    if not p:
        sys.exit('missing ' + pattern + ' in ' + RAW)
    return np.asarray(Image.open(p[0]).convert(mode).resize((N, N), Image.LANCZOS), np.float32) / 255.0


def periodic_noise(rng, cells, octaves=4):
    """smooth noise 0..1 that tiles (grids wrap round)"""
    acc, amp, tot = np.zeros((N, N), np.float32), 1.0, 0.0
    for o in range(octaves):
        g = cells * 2 ** o
        a = rng.random((g, g)).astype(np.float32)
        big = np.tile(a, (3, 3))                                        # wrap: take the middle copy after resizing
        im = Image.fromarray((big * 255).astype(np.uint8)).resize((3 * N, 3 * N), Image.BICUBIC)
        acc += np.asarray(im, np.float32)[N:2 * N, N:2 * N] / 255.0 * amp
        tot += amp
        amp *= 0.5
    return acc / tot


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def save(a, name):
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(OUT, name), optimize=True)


def main():
    rng = np.random.default_rng(5)
    colour = load('*_Color.jpg') ** 2.2                                      # sRGB photograph to linear
    mask = smooth(periodic_noise(rng, 4, 5), 0.38, 0.62)                       # patches of rust, not an even film
    delta = colour * 1.5 * (0.35 + 0.65 * mask)[..., None]                    # additive colour, linear: the photograph's own rust colour and variation
    save(0.5 + 0.5 * np.clip(delta, 0, 1), 'disc_rust_c.data.png')
    n = load('*_NormalGL.jpg')
    flat = np.array([0.5, 0.5, 1.0], np.float32)
    save(flat + (n - flat) * (0.5 + 0.5 * mask)[..., None], 'disc_rust_n.normal.png')
    r = load('*_Roughness.jpg', 'L')
    save((0.5 + 0.5 * (0.25 + 0.5 * r) * mask)[..., None].repeat(3, -1), 'disc_rust_r.data.png')
    print('wrote disc_rust_c.data.png, disc_rust_n.normal.png, disc_rust_r.data.png to', os.path.abspath(OUT))


main()
