from collections.abc import Generator

import bpy
import bpy.types

from .merge import merge_objects
from .modifier import main_apply_modifiers
from .optimizer import remove_unused_bones
from .shapekey import (
    process_shape_key_blending,
    remove_unlisted_shapekeys,
    sort_shapekey,
)


class ExportError(Exception):
    pass


def make_all_unlink() -> None:
    bpy.ops.object.duplicates_make_real(use_hierarchy=True)
    bpy.ops.object.make_local(type="ALL")
    bpy.ops.object.make_single_user(
        type="ALL",
        object=True,
        obdata=True,
        material=False,
        animation=False,
        obdata_animation=False,
    )


def apply_constraints(obj: bpy.types.Object) -> None:
    names = [constraint.name for constraint in obj.constraints]
    for name in names:
        bpy.ops.constraint.apply(constraint=name)


def apply_all_objects(context: bpy.types.Context) -> None:
    scn = context.scene

    bpy.ops.object.select_all(action="SELECT")
    make_all_unlink()

    for obj in scn.objects:
        if obj.visible_get() and obj.type in ("CURVE", "FONT", "SURFACE", "MESH"):
            context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(state=True)

            apply_constraints(obj)

            if obj.type in ("CURVE", "FONT", "SURFACE"):
                # Convert object to mesh
                bpy.ops.object.convert(target="MESH")

            main_apply_modifiers(obj)


def get_merge_collections(
    collection_settings: dict,  # readonly
    parent_collection: bpy.types.Collection,
) -> Generator[bpy.types.AnyType, None, None]:
    name = parent_collection.name
    if name in collection_settings:
        # Ignore nested collections
        yield collection_settings[name]
    else:
        for child in parent_collection.children:
            yield from get_merge_collections(collection_settings, child)


def delete_unused_vertex_group(obj: bpy.types.Object) -> None:
    if len(obj.vertex_groups) == 0:
        return

    max_weights = [0] * len(obj.vertex_groups)

    # Survey Zero Weights
    for vertex in obj.data.vertices:
        for vertex_group_element in vertex.groups:
            group_index = vertex_group_element.group
            weight = vertex_group_element.weight
            max_weights[group_index] = max(max_weights[group_index], weight)

    # Deform vertex groups
    deform_bone_names = []
    armature = obj.find_armature()
    if armature:
        deform_bone_names = [bone.name for bone in armature.data.bones]

    for index, weight in reversed(list(enumerate(max_weights))):
        vertex_group = obj.vertex_groups[index]
        if vertex_group.name not in deform_bone_names or weight == 0:
            obj.vertex_groups.remove(obj.vertex_groups[index])


def export(context: bpy.types.Context, settings: dict) -> None:
    """Preprocess and Export file"""

    exporter_settings = context.scene.yfx_exporter_settings
    export_settings = exporter_settings.export_settings

    export_path = settings["export_path"]

    # Convert object to mesh and Apply modifiers
    apply_all_objects(context)

    for col_info in settings["collections"]:
        col_name = col_info["name"]
        col = bpy.data.collections.get(col_name)
        if not col:
            continue

        merge_objects(context, col)
        obj = context.view_layer.objects.active

        # Post merge process
        bpy.ops.object.transform_apply(
            location=True,
            rotation=True,
            scale=True,
            properties=False,
        )

        if "shape_keys" in col_info:
            shape_keys = col_info["shape_keys"]

            # ここでシェイプキーの合成をする
            process_shape_key_blending(obj, shape_keys)
            sort_shapekey(obj, shape_keys)
            remove_unlisted_shapekeys(obj, shape_keys)

        delete_unused_vertex_group(obj)

    if "armature" in settings:
        armature_info = settings["armature"]
        delete_unused_bones = armature_info.get("delete_unused_bones", True)
        if delete_unused_bones:
            keep_bones = armature_info.get("keep_bones", [])
            remove_unused_bones(context, keep_bones)

    # Export to fbx
    fbx_export_settings = export_settings.fbx_export_settings
    keyargs_dict = {
        key: getattr(fbx_export_settings, key, None)
        for key in fbx_export_settings.__annotations__
    }
    bpy.ops.export_scene.fbx(
        filepath=export_path,
        **keyargs_dict,
    )
