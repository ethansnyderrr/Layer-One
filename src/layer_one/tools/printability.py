"""Swimlane step: "Check size, STL, and printer fit"

Uses trimesh to confirm the mesh is a valid solid, and draws a preview image.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: the homelab LXC has no display
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from layer_one.constraints import PRINTERS
from layer_one.tools.cost import fits


def check(stl_path: Path) -> tuple[trimesh.Trimesh, dict]:
    mesh = trimesh.load(stl_path, force="mesh")
    extents = [round(float(x), 1) for x in mesh.extents]
    facts = {
        "watertight": bool(mesh.is_watertight),
        "faces_point_consistently": bool(mesh.is_winding_consistent),
        "separate_pieces": int(mesh.body_count),
        "size_mm_print_orientation": extents,
        "volume_cm3": round(mesh.volume / 1000, 2),
        "fits_printers": [name for name, p in PRINTERS.items() if fits(extents, p["build_mm"])],
    }
    return mesh, facts


def render_preview(mesh: trimesh.Trimesh, png_path: Path) -> None:
    # matplotlib draws faces back to front by their center, so long thin triangles
    # overlap wrongly. Splitting them into smaller ones fixes most of that.
    vertices, faces = trimesh.remesh.subdivide_to_size(
        mesh.vertices, mesh.faces, max_edge=max(mesh.extents) / 30, max_iter=8
    )
    view = trimesh.Trimesh(vertices, faces, process=False)

    light = np.array([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    shade = np.clip(view.face_normals @ light, 0.0, 1.0)
    base = np.array([0.62, 0.11, 0.20])  # crimson
    rgb = np.outer(0.45 + 0.55 * shade, base)
    colors = np.column_stack([rgb, np.ones(len(rgb))])

    fig = plt.figure(figsize=(6, 6), dpi=150)
    ax = fig.add_subplot(projection="3d")
    ax.add_collection3d(Poly3DCollection(view.triangles, facecolors=colors, linewidths=0))
    lo, hi = mesh.bounds
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(np.maximum(mesh.extents, 1e-6))
    ax.view_init(elev=25, azim=-60)
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)"); ax.set_zlabel("Z (mm)")
    ax.set_title("Shown in print orientation", fontsize=9)
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)
