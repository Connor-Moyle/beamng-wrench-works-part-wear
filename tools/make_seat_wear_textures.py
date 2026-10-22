"""Detail textures of the worn interior look: faded, creased upholstery on the cabin and seat materials. All drawn (periodic noise, no photograph, nothing to credit).

    python tools/make_seat_wear_textures.py [out folder]

Writes to mod/art/slrr_partwear/ three 512 x 512 detail maps that tile (the stage materials lay them over the interior's own maps at detailScale 5):
  seat_wear_c.data.png   colour detail: 0.5 = no change; above it the cloth or leather is faded in patches, a little below it dark creases and grime in the folds
  seat_wear_n.normal.png normal detail: creases (long soft wrinkles) and a fine cracked-grain
  seat_wear_r.data.png   roughness detail: the worn patches are smoother and shinier (polished by use), the folds rougher
PNG here; the game cooks them to DDS on first use and the DDS replace the PNGs (tools/test_wear_textures.py).
"""
import numpy as np
from make_disc_rust_textures import periodic_noise, smooth, save, N

rng = np.random.default_rng(91)
fade = smooth(periodic_noise(rng, 3, 4), 0.4, 0.7)                  # big patches where the sitting wears the cover
ridge = 1.0 - np.abs(2.0 * periodic_noise(rng, 6, 3) - 1.0)         # 1 along the lines of a noise field: wrinkles
crease = smooth(ridge, 0.82, 0.97)
grain = periodic_noise(rng, 48, 2)
delta = 0.45 * fade - 0.35 * crease * (0.5 + 0.5 * periodic_noise(rng, 5, 3))
save(0.5 + 0.5 * np.clip(delta, -1, 1)[..., None].repeat(3, -1), 'seat_wear_c.data.png')
gy, gx = np.gradient(0.8 * crease + 0.2 * grain)
nrm = np.stack([0.5 - 4 * gx, 0.5 - 4 * gy, np.ones_like(gx)], -1)
save(np.clip(nrm, 0, 1), 'seat_wear_n.normal.png')
save((0.5 + 0.5 * np.clip(-0.6 * fade + 0.5 * crease, -1, 1))[..., None].repeat(3, -1), 'seat_wear_r.data.png')
print('wrote seat_wear_c.data.png, seat_wear_n.normal.png, seat_wear_r.data.png')
