"""Every texture the worn look ships is the game's own cooked DDS (BC7 for data maps, BC5 for normals), named *.color / *.normal / *.data, and no PNG is left beside it:
a PNG the game cooks at runtime and then reloads strips the maps from a material switched in at spawn (the tyre overlays' finding). Fails until the cook run has been copied back.

    python tools/test_wear_textures.py
"""
import os, struct, sys

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mod", "art")
DXGI = {"data": 98, "normal": 83, "color": 99}      # BC7 (linear), BC5, BC7 sRGB


def main():
    bad = []
    names = set()
    for root, _, files in os.walk(ART):
        for f in files:
            stem, ext = os.path.splitext(f)
            if ext.lower() == ".png":
                bad.append("%s is a PNG: ship the game's cooked DDS" % f)
            elif ext.lower() == ".dds":
                kind = stem.rsplit(".", 1)[-1]
                if kind not in DXGI:
                    bad.append("%s is not named *.color / *.normal / *.data" % f)
                    continue
                with open(os.path.join(root, f), "rb") as fh:
                    h = fh.read(148)
                if h[:4] != b"DDS " or h[84:88] != b"DX10" or struct.unpack("<I", h[128:132])[0] != DXGI[kind]:
                    bad.append("%s is not a DX10 DDS of format %d" % (f, DXGI[kind]))
                names.add(stem)
    for need in ("disc_rust_c.data", "disc_rust_n.normal", "disc_rust_r.data"):
        if need not in names:
            bad.append("%s.dds is missing" % need)
    if bad:
        print("wear textures FAIL:")
        for b in bad:
            print("  " + b)
        sys.exit(1)
    print("wear textures ok: %d cooked DDS, no PNG" % len(names))


if __name__ == "__main__":
    main()
