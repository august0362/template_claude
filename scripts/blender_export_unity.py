"""
blender_export_unity.py
Normalize pivot -> freeze transforms -> export Y-Up FBX for Unity (URP).
Requires: Blender 3.6+ (tested on 4.x). Does not save the .blend.
"""
import argparse
import os
import re
import sys

import bpy
from mathutils import Matrix, Vector

EPS = 1e-6
MAX_MATERIALS = 3
EXPORTABLE = {"MESH", "ARMATURE", "EMPTY"}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser(description="Blender -> Unity FBX exporter")
    p.add_argument("--out", default="//Export", help="Output folder (supports //relative to the .blend)")
    p.add_argument("--pivot", choices=("BASE_CENTER", "BOUNDS_CENTER", "WORLD_ORIGIN"),
                   default="BASE_CENTER", help="How to place the pivot of rigid meshes")
    p.add_argument("--selected-only", action="store_true", help="Only process the selected objects")
    p.add_argument("--tri-budget", type=int, default=30000, help="Error when the triangle count exceeds this")
    p.add_argument("--combine", default="", help="File name to merge every asset into ONE FBX")
    p.add_argument("--no-bake-space", action="store_true", help="Disable bake_space_transform")
    p.add_argument("--dry-run", action="store_true", help="Validate only: no modification, no export")
    return p.parse_args(argv)


def ensure_object_mode():
    active = bpy.context.view_layer.objects.active
    if active is not None and active.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def sanitize(name):
    return re.sub(r"[^A-Za-z0-9_\-]", "_", name)


def collect_hierarchies(selected_only):
    """Return list[(root, members)]; every tree has at least one mesh."""
    source = bpy.context.selected_objects if selected_only else bpy.context.scene.objects
    roots = {}
    for obj in source:
        if obj.type not in EXPORTABLE or not obj.visible_get():
            continue
        root = obj
        while root.parent is not None:
            root = root.parent
        roots.setdefault(root.name, root)

    result = []
    for root in roots.values():
        members = [root] + [c for c in root.children_recursive if c.type in EXPORTABLE]
        if any(m.type == "MESH" for m in members):
            result.append((root, members))
    return result


def triangle_count(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = ev.to_mesh()
    try:
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)
    finally:
        ev.to_mesh_clear()


def local_pivot(obj, mode):
    corners = [Vector(c) for c in obj.bound_box]
    xs, ys, zs = zip(*corners)
    lo = Vector((min(xs), min(ys), min(zs)))
    hi = Vector((max(xs), max(ys), max(zs)))
    if mode == "BASE_CENTER":                       # Blender is Z-up: the base = min Z
        return Vector(((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, lo.z))
    if mode == "BOUNDS_CENTER":
        return (lo + hi) * 0.5
    return obj.matrix_world.inverted() @ Vector((0.0, 0.0, 0.0))   # WORLD_ORIGIN


def make_single_user(obj, log):
    if obj.type == "MESH" and obj.data.users > 1:
        obj.data = obj.data.copy()
        log.append(f"  - {obj.name}: split shared mesh data into its own copy")


def normalize_rigid(obj, mode):
    """Move the pivot to (0,0,0) then bake rotation/scale into the mesh. Only for objects without a parent."""
    pivot = local_pivot(obj, mode)
    obj.data.transform(Matrix.Translation(-pivot), shape_keys=True)   # local pivot -> local origin
    obj.location = (0.0, 0.0, 0.0)                                    # local origin -> world origin

    baked = obj.matrix_basis.copy()                                    # now only rotation + scale remain
    obj.data.transform(baked, shape_keys=True)
    obj.matrix_basis = Matrix.Identity(4)
    obj.data.update()


def normalize_rig(root, members):
    """Tree with an Armature: move the tree root to (0,0,0) then apply rotation/scale across the whole tree."""
    root.location = (0.0, 0.0, 0.0)
    select_only([root] + [m for m in members if m is not root])
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True, properties=True)


def verify_frozen(obj, check_translation):
    bpy.context.view_layer.update()
    m = obj.matrix_world
    rot_scale_ok = all(abs(m[r][c] - (1.0 if r == c else 0.0)) < 1e-5 for r in range(3) for c in range(3))
    trans_ok = (not check_translation) or m.translation.length < 1e-5
    return rot_scale_ok and trans_ok


def export_fbx(objs, filepath, has_rig, bake_space):
    select_only(objs)
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        object_types={"MESH", "ARMATURE", "EMPTY"},
        axis_forward="-Z",                 # this axis pair + bake => Unity receives rotation (0,0,0), scale (1,1,1)
        axis_up="Y",
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        use_space_transform=True,
        bake_space_transform=bake_space and not has_rig,   # baking the axes is unsafe with animation
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        use_tspace=True,
        add_leaf_bones=False,
        use_armature_deform_only=True,
        bake_anim=has_rig,
        embed_textures=False,
        path_mode="AUTO",
    )


def main():
    args = parse_args()
    errors, warnings, log = [], [], []
    scene = bpy.context.scene

    if abs(scene.unit_settings.scale_length - 1.0) > EPS:
        errors.append(f"Unit Scale = {scene.unit_settings.scale_length}, must be 1.0 (1 unit = 1 m).")

    ensure_object_mode()
    units = collect_hierarchies(args.selected_only)
    if not units:
        errors.append("No visible mesh found to export.")

    out_dir = bpy.path.abspath(args.out)
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)

    exported_sets = []   # (file name, list of objects)

    for root, members in units:
        meshes = [m for m in members if m.type == "MESH"]
        has_rig = any(m.type == "ARMATURE" for m in members)
        hierarchical = has_rig or len(members) > 1     # only a single standalone mesh can use the data API

        negative = [m.name for m in members if min(m.scale) < 0.0]
        if negative:
            errors.append(f"{root.name}: negative scale on {negative} — fix in Blender (Apply + Recalculate Normals).")
            continue

        for m in meshes:
            tris = triangle_count(m)
            slots = len([s for s in m.material_slots if s.material])
            if tris > args.tri_budget:
                errors.append(f"{m.name}: {tris} tris > budget {args.tri_budget}.")
            if slots > MAX_MATERIALS:
                warnings.append(f"{m.name}: {slots} materials > {MAX_MATERIALS} (use an atlas).")
            if not m.data.uv_layers:
                warnings.append(f"{m.name}: no UV map.")

        if args.dry_run:
            continue

        for m in meshes:
            make_single_user(m, log)

        if hierarchical:
            normalize_rig(root, members)
            if not verify_frozen(root, check_translation=True):
                errors.append(f"{root.name}: freezing the tree failed (check parent-inverse/constraints).")
                continue
            warnings.append(f"{root.name}: multi-object tree — pivot = origin of the root; "
                            "animation must be re-keyed if scale ≠ 1.")
        else:
            normalize_rigid(root, args.pivot)
            if not verify_frozen(root, check_translation=True):
                errors.append(f"{root.name}: freeze failed.")
        exported_sets.append((sanitize(root.name), members, has_rig))

    if errors:
        report(errors, warnings, log)
        return 1
    if args.dry_run:
        report(errors, warnings, ["dry-run: nothing modified, nothing exported."])
        return 0

    bake = not args.no_bake_space
    if args.combine:
        all_objs = [o for _, members, _ in exported_sets for o in members]
        rig_any = any(r for _, _, r in exported_sets)
        path = os.path.join(out_dir, sanitize(args.combine) + ".fbx")
        export_fbx(all_objs, path, rig_any, bake)
        log.append(f"  → {path}")
    else:
        for name, members, has_rig in exported_sets:
            path = os.path.join(out_dir, name + ".fbx")
            export_fbx(members, path, has_rig, bake)
            log.append(f"  → {path}")

    report(errors, warnings, log)
    return 0


def report(errors, warnings, log):
    for line in log:
        print("[export]", line)
    for w in warnings:
        print("[warn]  ", w)
    for e in errors:
        print("[ERROR] ", e)
    print(f"[export] {len(errors)} errors, {len(warnings)} warnings.")


if __name__ == "__main__":
    code = main()
    if bpy.app.background:
        sys.exit(code)
