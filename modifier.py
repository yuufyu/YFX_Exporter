import bpy


def copy_object(obj : bpy.types.Object) -> bpy.types.Object:
    copy_obj = obj.copy()
    copy_obj.data = obj.data.copy()
    bpy.context.collection.objects.link(copy_obj)
    return copy_obj


def remove_object(obj : bpy.types.Object) -> None:
    mesh_data = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh_data)


def transfer_shapekey(obj: bpy.types.Object, blendshape: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    blendshape.select_set(state=True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join_shapes()


def apply_single_shapekey(obj: bpy.types.Object, index: int) -> None:
    shapekeys = obj.data.shape_keys.key_blocks
    if 0 <= index < len(shapekeys):
        for i in reversed(range(len(shapekeys))):
            if i != index:
                obj.shape_key_remove(shapekeys[i])
        obj.shape_key_remove(shapekeys[0])


def apply_all_modifiers(obj: bpy.types.Object) -> None:
    for m in obj.modifiers:
        if m.show_viewport:
            if m.type != "ARMATURE":
                bpy.context.view_layer.objects.active = obj
                try:
                    bpy.ops.object.modifier_apply(modifier=m.name)
                except RuntimeError as e:
                    print(f"Error applying {m.name} to {obj.name}: {e}")
                    obj.modifiers.remove(m)
        else:
            obj.modifiers.remove(m)


def apply_modifiers_with_shapekeys(obj: bpy.types.Object) -> None:
    # Temp object that will contain all collapsed shapekeys
    temp_obj = copy_object(obj)

    apply_single_shapekey(obj, 0)
    apply_all_modifiers(obj)

    shapekeys_data = temp_obj.data.shape_keys
    shapekeys_blocks = shapekeys_data.key_blocks

    for i in range(1, len(shapekeys_blocks)):
        blendshape_obj = copy_object(temp_obj)

        apply_single_shapekey(blendshape_obj, i)
        apply_all_modifiers(blendshape_obj)

        # Transfer shapekey to the original object
        transfer_shapekey(obj, blendshape_obj)

        # Rename shapekey
        obj.data.shape_keys.key_blocks[i].name = shapekeys_blocks[i].name

        # Delete the blendshape donor
        remove_object(blendshape_obj)

    # Delete temp object
    remove_object(temp_obj)


def main_apply_modifiers(obj: bpy.types.Object) -> None:
    """
    Main function to apply modifiers to the target object.

    Args:
        obj (bpy.types.Object): The target object.
    """
    if len(obj.modifiers) < 1:
        return
    shapekeys = obj.data.shape_keys
    if shapekeys is not None and len(shapekeys.key_blocks) > 0:
        apply_modifiers_with_shapekeys(obj)
    else:
        apply_all_modifiers(obj)