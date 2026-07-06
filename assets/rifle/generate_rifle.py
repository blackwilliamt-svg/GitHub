#!/usr/bin/env python3
"""Procedural AR-15-style rifle generator for Unreal Engine.

Builds a modern semi-auto rifle out of parametric primitives and exports:
  * SM_Rifle.glb  -- glTF binary, imports directly into UE5 with PBR materials
  * SM_Rifle.obj  -- OBJ + MTL fallback for UE4 / other DCC tools

Conventions:
  * Units are meters (glTF standard). UE's glTF importer converts to cm.
  * Modeled Z-up with the muzzle pointing +X (UE's "forward"). trimesh
    handles the Y-up conversion required by the glTF spec on export.
  * The bore (barrel axis) sits at Z = 0; the origin is placed at the
    pistol grip so the mesh attaches naturally to a hand socket.

Usage:
    python3 generate_rifle.py [output_dir]
"""

import sys

import numpy as np
import trimesh
from trimesh.creation import box, cylinder, cone
from trimesh.visual.material import PBRMaterial

SECTIONS = 32  # radial segments for round parts


# ---------------------------------------------------------------- helpers

def _translate(mesh, x=0.0, y=0.0, z=0.0):
    mesh.apply_translation([x, y, z])
    return mesh


def _rot(mesh, deg, axis, point=None):
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(
            np.radians(deg), axis, point=point if point is not None else [0, 0, 0]
        )
    )
    return mesh


def bx(sx, sy, sz, cx=0.0, cy=0.0, cz=0.0):
    """Axis-aligned box of extents (sx, sy, sz) centered at (cx, cy, cz)."""
    return _translate(box(extents=[sx, sy, sz]), cx, cy, cz)


def cyl_x(radius, x0, x1, cy=0.0, cz=0.0, sections=SECTIONS):
    """Cylinder along +X spanning x0..x1."""
    m = cylinder(radius=radius, height=x1 - x0, sections=sections)
    _rot(m, 90, [0, 1, 0])
    return _translate(m, (x0 + x1) / 2.0, cy, cz)


def cyl_y(radius, y0, y1, cx=0.0, cz=0.0, sections=SECTIONS):
    """Cylinder along +Y spanning y0..y1."""
    m = cylinder(radius=radius, height=y1 - y0, sections=sections)
    _rot(m, 90, [1, 0, 0])
    return _translate(m, cx, (y0 + y1) / 2.0, cz)


def cyl_z(radius, z0, z1, cx=0.0, cy=0.0, sections=SECTIONS):
    """Cylinder along +Z spanning z0..z1."""
    m = cylinder(radius=radius, height=z1 - z0, sections=sections)
    return _translate(m, cx, cy, (z0 + z1) / 2.0)


def octo_x(radius, x0, x1, cz=0.0):
    """Octagonal prism along +X (flat top), used for the handguard."""
    m = cylinder(radius=radius, height=x1 - x0, sections=8)
    _rot(m, 22.5, [0, 0, 1])  # flat facet on top before reorienting
    _rot(m, 90, [0, 1, 0])
    return _translate(m, (x0 + x1) / 2.0, 0, cz)


# ---------------------------------------------------------------- parts
# Bore axis at z = 0, receiver rear face at x = 0, muzzle points +X.

def build_receiver_parts():
    """Upper/lower receiver, rails, controls -- anodized aluminum group."""
    parts = []

    # Upper receiver around the bore.
    parts.append(bx(0.24, 0.040, 0.046, cx=0.14, cz=0.003))
    # Lower receiver.
    parts.append(bx(0.20, 0.036, 0.052, cx=0.14, cz=-0.044))
    # Magazine well collar.
    parts.append(bx(0.075, 0.040, 0.030, cx=0.175, cz=-0.078))

    # Flat-top picatinny rail: base strips + ridges over receiver and handguard.
    parts.append(bx(0.24, 0.030, 0.006, cx=0.14, cz=0.029))
    parts.append(bx(0.285, 0.030, 0.010, cx=0.4025, cz=0.026))  # handguard riser
    for i in range(21):
        x = 0.035 + i * 0.025
        parts.append(bx(0.006, 0.032, 0.005, cx=x, cz=0.0345))

    # Ejection port (raised plate, right side) + brass deflector.
    parts.append(bx(0.075, 0.004, 0.024, cx=0.16, cy=-0.021, cz=0.004))
    parts.append(bx(0.014, 0.008, 0.024, cx=0.208, cy=-0.021, cz=0.004))

    # Charging handle: shaft + T latch at the rear.
    parts.append(bx(0.045, 0.014, 0.008, cx=0.024, cz=0.022))
    parts.append(bx(0.012, 0.062, 0.010, cx=0.006, cz=0.022))

    # Trigger guard and trigger blade.
    parts.append(bx(0.062, 0.014, 0.006, cx=0.118, cz=-0.093))   # bottom
    parts.append(bx(0.006, 0.014, 0.024, cx=0.090, cz=-0.081))   # front post
    parts.append(bx(0.006, 0.014, 0.024, cx=0.146, cz=-0.081))   # rear post
    trigger = bx(0.006, 0.010, 0.026, cx=0.118, cz=-0.082)
    parts.append(_rot(trigger, -12, [0, 1, 0], point=[0.118, 0, -0.070]))

    # Controls: safety lever (left), mag release (right), bolt release (left).
    parts.append(cyl_y(0.006, 0.018, 0.024, cx=0.10, cz=-0.030, sections=16))
    parts.append(bx(0.026, 0.004, 0.009, cx=0.088, cy=0.022, cz=-0.030))
    parts.append(cyl_y(0.005, -0.024, -0.018, cx=0.155, cz=-0.032, sections=16))
    parts.append(bx(0.018, 0.004, 0.030, cx=0.13, cy=0.019, cz=-0.010))

    # Forward assist (right rear of upper).
    parts.append(cyl_y(0.007, -0.028, -0.018, cx=0.215, cz=0.010, sections=16))

    # Gas block under the front sight.
    parts.append(bx(0.030, 0.024, 0.030, cx=0.575, cz=0.008))

    # Sights: folding-style rear (on rail) and front post tower.
    parts.append(bx(0.030, 0.030, 0.014, cx=0.055, cz=0.044))    # rear base
    parts.append(bx(0.006, 0.030, 0.016, cx=0.062, cz=0.059))    # rear aperture wall
    parts.append(bx(0.024, 0.024, 0.010, cx=0.575, cz=0.032))    # front base
    return parts


def build_polymer_parts():
    """Stock, grip, magazine -- matte polymer group."""
    parts = []

    # Collapsible stock body riding the buffer tube.
    parts.append(bx(0.150, 0.044, 0.060, cx=-0.195, cz=-0.016))
    parts.append(bx(0.130, 0.036, 0.018, cx=-0.185, cz=0.020))    # cheek riser
    parts.append(bx(0.022, 0.050, 0.120, cx=-0.281, cz=-0.038))   # butt pad
    # Sloped underside connecting butt pad to tube.
    slope = bx(0.13, 0.040, 0.016, cx=-0.20, cz=-0.055)
    parts.append(_rot(slope, -14, [0, 1, 0], point=[-0.27, 0, -0.09]))

    # Pistol grip, raked back ~17 degrees.
    grip = bx(0.030, 0.034, 0.105, cx=0.062, cz=-0.115)
    parts.append(_rot(grip, -17, [0, 1, 0], point=[0.062, 0, -0.070]))

    # 30-round curved magazine: two angled segments.
    seg1 = bx(0.070, 0.026, 0.075, cx=0.175, cz=-0.125)
    parts.append(_rot(seg1, 8, [0, 1, 0], point=[0.175, 0, -0.093]))
    seg2 = bx(0.070, 0.026, 0.075, cx=0.190, cz=-0.185)
    parts.append(_rot(seg2, 22, [0, 1, 0], point=[0.183, 0, -0.155]))
    base = bx(0.080, 0.030, 0.014, cx=0.205, cz=-0.222)
    parts.append(_rot(base, 22, [0, 1, 0], point=[0.205, 0, -0.222]))
    return parts


def build_metal_round_parts():
    """Barrel, muzzle, handguard, buffer tube -- smooth gunmetal group."""
    parts = []

    # Buffer tube from receiver into the stock.
    parts.append(cyl_x(0.0155, -0.27, 0.02, cz=-0.004))

    # Free-float octagonal handguard.
    parts.append(octo_x(0.0235, 0.26, 0.545))

    # Barrel: chamber taper then main profile.
    parts.append(cyl_x(0.014, 0.26, 0.32))
    parts.append(cyl_x(0.0095, 0.32, 0.70))

    # A2-style flash hider: body, tip ring, crown cone.
    parts.append(cyl_x(0.0115, 0.70, 0.755))
    parts.append(cyl_x(0.0125, 0.748, 0.755))
    tip = cone(radius=0.0115, height=0.012, sections=SECTIONS)
    _rot(tip, 90, [0, 1, 0])
    parts.append(_translate(tip, 0.755, 0, 0))

    # Front sight post.
    parts.append(cyl_z(0.0025, 0.036, 0.060, cx=0.575, sections=12))
    parts.append(cyl_z(0.0050, 0.056, 0.060, cx=0.575, sections=12))
    return parts


# ---------------------------------------------------------------- assembly

def _merge(parts, flat_shaded):
    mesh = trimesh.util.concatenate(parts)
    if flat_shaded:
        mesh.unmerge_vertices()  # unique verts per face -> crisp hard edges
    return mesh


def build_scene():
    groups = {
        "Receiver": (build_receiver_parts(), True),
        "Furniture": (build_polymer_parts(), True),
        "BarrelAssembly": (build_metal_round_parts(), False),
    }
    materials = {
        "Receiver": PBRMaterial(
            name="M_Rifle_Receiver",
            baseColorFactor=[0.055, 0.055, 0.060, 1.0],
            metallicFactor=1.0,
            roughnessFactor=0.55,
        ),
        "Furniture": PBRMaterial(
            name="M_Rifle_Polymer",
            baseColorFactor=[0.045, 0.045, 0.045, 1.0],
            metallicFactor=0.0,
            roughnessFactor=0.85,
        ),
        "BarrelAssembly": PBRMaterial(
            name="M_Rifle_Gunmetal",
            baseColorFactor=[0.14, 0.145, 0.155, 1.0],
            metallicFactor=1.0,
            roughnessFactor=0.35,
        ),
    }

    # Shift so the origin lands at the top of the pistol grip (hand socket).
    grip_origin = np.array([0.062, 0.0, -0.070])

    scene = trimesh.Scene()
    total_tris = 0
    for name, (parts, flat) in groups.items():
        mesh = _merge(parts, flat_shaded=flat)
        mesh.apply_translation(-grip_origin)
        mesh.visual = trimesh.visual.TextureVisuals(material=materials[name])
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        total_tris += len(mesh.faces)

    ext = scene.bounds[1] - scene.bounds[0]
    print(f"Rifle: {ext[0]:.3f} m long, {ext[2]:.3f} m tall, "
          f"{ext[1]*1000:.0f} mm wide, {total_tris} triangles")
    return scene


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    scene = build_scene()

    glb_path = f"{out_dir}/SM_Rifle.glb"
    scene.export(glb_path)
    print(f"wrote {glb_path}")

    obj_path = f"{out_dir}/SM_Rifle.obj"
    scene.export(obj_path)
    print(f"wrote {obj_path}")


if __name__ == "__main__":
    main()
