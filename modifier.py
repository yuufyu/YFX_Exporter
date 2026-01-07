import bpy


def copy_object(obj: bpy.types.Object) -> bpy.types.Object:
    copy_obj = obj.copy()
    copy_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(copy_obj)
    return copy_obj


def remove_object(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(state=True)
    bpy.ops.object.delete(use_global=False, confirm=False)


def transfer_shapekey(obj: bpy.types.Object, blendshape: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    blendshape.select_set(state=True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join_shapes()


def reset_shapekey_value(obj: bpy.types.Object) -> None:
    for shapekey in obj.data.shape_keys.key_blocks:
        shapekey.value = 0


def apply_shapekey(obj: bpy.types.Object, index: int) -> None:
    shapekeys = obj.data.shape_keys.key_blocks
    if 0 <= index < len(shapekeys):
        shapekeys[index].value = 1
        obj.shape_key_add(name="temp_apply_shape_key", from_mix=True)
        for s in shapekeys[:]:
            obj.shape_key_remove(s)


def apply_all_modifiers(obj: bpy.types.Object) -> None:
    for m in obj.modifiers:
        if m.show_viewport:
            if m.type != "ARMATURE":
                bpy.context.view_layer.objects.active = obj
                try:
                    bpy.ops.object.modifier_apply(modifier=m.name)
                except RuntimeError:
                    obj.modifiers.remove(m)
        else:
            obj.modifiers.remove(m)


def apply_modifiers_with_shapekeys(obj: bpy.types.Object) -> None:
    reset_shapekey_value(obj)

    # Weldモディファイアの情報を収集
    weld_jobs = []
    for m in obj.modifiers:
        if m.type == "WELD" and m.show_viewport:
            weld_jobs.append(
                {
                    "dist": m.merge_threshold,
                    "vgroup": m.vertex_group,
                },
            )
            m.show_viewport = False

    # Temp object that will contain all collapsed shapekeys
    temp_obj = copy_object(obj)

    apply_shapekey(obj, 0)
    apply_all_modifiers(obj)

    shapekeys_blocks = temp_obj.data.shape_keys.key_blocks
    basis_name = shapekeys_blocks[0].name

    for i in range(1, len(shapekeys_blocks)):
        blendshape_obj = copy_object(temp_obj)

        apply_shapekey(blendshape_obj, i)
        apply_all_modifiers(blendshape_obj)

        # Transfer shapekey to the original object
        transfer_shapekey(obj, blendshape_obj)

        # Rename shapekey
        obj.data.shape_keys.key_blocks[i].name = shapekeys_blocks[i].name

        # Delete the blendshape donor
        remove_object(blendshape_obj)

    # Keep Basis name
    obj.data.shape_keys.key_blocks[0].name = basis_name

    # Delete temp object
    remove_object(temp_obj)

    if weld_jobs:
        execute_manual_weld(obj, weld_jobs)


def execute_manual_weld(obj: bpy.types.Object, weld_jobs: list) -> None:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")

    for job in weld_jobs:
        bpy.ops.mesh.select_all(action="DESELECT")

        if job["vgroup"] and job["vgroup"] in obj.vertex_groups:
            # 頂点グループが指定されている場合、その頂点のみを選択
            bpy.ops.object.vertex_group_set_active(group=job["vgroup"])
            bpy.ops.object.vertex_group_select()
        else:
            # 指定がなければ全選択
            bpy.ops.mesh.select_all(action="SELECT")

        # 距離でマージを実行
        bpy.ops.mesh.remove_doubles(threshold=job["dist"])

    bpy.ops.object.mode_set(mode="OBJECT")


def main_apply_modifiers(obj: bpy.types.Object) -> None:
    """
    Main function to apply modifiers to the target object.

    Args:
        obj (bpy.types.Object): The target object.
    """
    if sum(m.type != "ARMATURE" for m in obj.modifiers) == 0:
        return
    shapekeys = obj.data.shape_keys
    if shapekeys is not None and len(shapekeys.key_blocks) > 0:
        apply_modifiers_with_shapekeys(obj)
    else:
        apply_all_modifiers(obj)
