import bpy
import bpy.types


def get_child_objects(collection: bpy.types.Collection) -> list:
    collections = [
        obj for obj in collection.objects if obj.visible_get() and obj.type == "MESH"
    ]
    for c in collection.children:
        children = get_child_objects(c)
        collections.extend(children)

    return collections


def merge_objects(context: bpy.types.Context, collection: bpy.types.Collection) -> None:
    merge_targets = get_child_objects(collection)

    if len(merge_targets) == 1:
        merge_targets[0].name = collection.name
        context.view_layer.objects.active = merge_targets[0]
    elif len(merge_targets) > 1:
        context.view_layer.objects.active = merge_targets[0]
        bpy.ops.object.select_all(action="DESELECT")

        for obj in merge_targets:
            # Normalize Basis name
            shapekeys = obj.data.shape_keys
            if shapekeys is not None and len(shapekeys.key_blocks) > 0:
                shapekeys.key_blocks[0].name = "Basis"

            obj.select_set(state=True)
        bpy.ops.object.join()
        context.view_layer.objects.active.name = collection.name
