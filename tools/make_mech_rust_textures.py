"""Detail textures of the worn suspension, frame and exhaust metal look, from the same CC0 photograph set of rust as the discs (ambientCG Rust005, docs/TEXTURE_CREDITS.md).

    python tools/make_mech_rust_textures.py <raw folder with Rust005/ (Color, NormalGL, Roughness jpg)> [out folder]

Writes to mod/art/slrr_partwear/ three 512 x 512 detail maps that tile (the stage materials lay them over the car's own mechanical atlas at detailScale 4):
  mech_rust_c.data.png   colour detail: 0.5 = no change; below it road grime and soot darken the metal in broad patches, above it orange-brown rust in fewer, bigger areas than on a disc
  mech_rust_n.normal.png normal detail: the photograph's pitting under the rust only
  mech_rust_r.data.png   roughness detail: rust and grime are rougher than the painted or bare metal
PNG here; the game cooks them to DDS on first use and the DDS replace the PNGs (tools/test_wear_textures.py).
"""
import os
import numpy as np
from make_disc_rust_textures import load, periodic_noise, smooth, save, OUT

# MODELLED: a frame rusts in areas where water sat, so bigger and fewer patches than a disc's bloom; grime is broad and soft
rng = np.random.default_rng(11)
rust = smooth(periodic_noise(rng, 3, 5), 0.48, 0.7)
grime = smooth(periodic_noise(np.random.default_rng(23), 2, 4), 0.3, 0.85)
colour = load('*_Color.jpg') ** 2.2                                                  # sRGB photograph to linear
delta = colour * 1.6 * rust[..., None] - 0.45 * grime[..., None]                      # additive, linear: rust lifts toward the photograph's colour, grime pulls toward black
save(0.5 + 0.5 * np.clip(delta, -1, 1), 'mech_rust_c.data.png')
n = load('*_NormalGL.jpg')
flat = np.array([0.5, 0.5, 1.0], np.float32)
save(flat + (n - flat) * rust[..., None], 'mech_rust_n.normal.png')
r = load('*_Roughness.jpg', 'L')
save((0.5 + 0.5 * np.clip(0.3 * grime + (0.25 + 0.5 * r) * rust, 0, 1))[..., None].repeat(3, -1), 'mech_rust_r.data.png')
print('wrote mech_rust_c.data.png, mech_rust_n.normal.png, mech_rust_r.data.png to', os.path.abspath(OUT))
