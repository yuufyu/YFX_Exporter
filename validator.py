from collections.abc import Generator, Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import groupby

import bpy
import bpy_types
from bpy.app.translations import pgettext_tip as tip_


class ErrorCategory(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ErrorInfo:
    code: int
    category: ErrorCategory
    message: str


def all_equal(iterable: Iterable[bpy.types.AnyType]) -> bool:
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def get_child_objects(
    collection: bpy.types.Collection,
) -> Generator[bpy.types.Object, None, None]:
    for obj in collection.objects:
        if obj.visible_get() and obj.type == "MESH":
            yield obj

    for c in collection.children:
        yield from get_child_objects(c)


def check_fbx_path(path: str) -> bool:
    """
    Check the validity of the provided FBX file path.

    Parameters:
    - path (str): The file path of the FBX file.

    Returns:
    - bool: If True is returned, it indicates a potential error due to an invalid path.
    """
    min_path_length = 5
    return len(path) < min_path_length  # <>.fbx


def check_multiple_collections(obj: bpy.types.Object) -> bool:
    """
    Check multiple collections.

    Parameters:
    - obj (bpy.types.Object): Object

    Returns:
    - bool: If True is returned, it indicates a potential error due to
            object in multiple collections.
    """
    return len(obj.users_collection) > 1


# nest
def get_nest_collections(
    collection_settings: dict,  # readonly
    parent_collection: bpy.types.Collection,
    in_merge_collection: bool,
) -> list:
    nest_collection_names = []
    name = parent_collection.name
    is_merge_collection = name in collection_settings

    if is_merge_collection and in_merge_collection:
        nest_collection_names.append(name)

    for child in parent_collection.children:
        nested = get_nest_collections(
            collection_settings,
            child,
            in_merge_collection=is_merge_collection or in_merge_collection,
        )
        if len(nested) > 0:
            nest_collection_names.extend(nested)

    return nest_collection_names


def check_nest_collections(
    collection_settings: bpy.types.AnyType,
    collection: bpy.types.Collection,
) -> list:
    if len(collection_settings) <= 1:
        return []

    collection_settings_dict = {c.collection_ptr.name: c for c in collection_settings}
    return get_nest_collections(
        collection_settings_dict,
        collection,
        in_merge_collection=False,
    )


def check_vertex_count_based_on_shape_with_shapekeys(obj: bpy.types.Object) -> bool:
    # Check if there are more than 1 shape keys
    if obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 1:
        # Check if a Bevel modifier with limit_method='ANGLE' is present
        for modifier in obj.modifiers:
            if modifier.type == "BEVEL" and modifier.limit_method == "ANGLE":
                return True

    return False


def check_armature_modifier_order(obj: bpy.types.Object) -> bool:
    # Function to check if Armature modifier is not at the bottom
    return any(modifier.type == "ARMATURE" for modifier in obj.modifiers[:-1])


# Function to check if the referenced Armature is hidden
def check_hidden_armature(obj: bpy.types.Object) -> bool:
    # Find the Armature modifier
    armature = obj.find_armature()
    if armature:
        return not (armature.visible_get())

    return False


def check_inconsistent_armature(collection: bpy.types.Collection) -> bool:
    return not (all_equal(obj.find_armature() for obj in get_child_objects(collection)))


def check_geometry_node(obj: bpy.types.Object) -> bool:
    return any(modifier.type == "NODES" for modifier in obj.modifiers)


def validate(context: bpy_types.Context) -> list:
    error_list = []

    scn = context.scene
    # export_settings = scn.yfx_exporter_settings.export_settings
    # collection_settings = export_settings.collections

    # Check file path error
    # if check_fbx_path(export_settings.export_path):
    #     err = ErrorInfo(
    #         code=2,
    #         category=ErrorCategory.ERROR,
    #         message="Invalid FBX output path",
    #     )
    #     error_list.append(err)

    # Check nestd collection
    # nested_collections = check_nest_collections(collection_settings, scn.collection)
    # if len(nested_collections) > 0:
    #     nested_collections_str = ",".join(nested_collections)

    #     err = ErrorInfo(
    #         code=17,
    #         category=ErrorCategory.WARNING,
    #         message=tip_(
    #             "Child collection '%s' settings are ignored as the parent collection is set as the merge target",
    #         )
    #         % nested_collections_str,
    #     )
    #     error_list.append(err)

    # # Check Collections
    # for c in collection_settings:
    #     collection = c.collection_ptr
    #     if collection and check_inconsistent_armature(collection):
    #         err = ErrorInfo(
    #             code=7,
    #             category=ErrorCategory.WARNING,
    #             message=tip_(
    #                 "Armature settings for objects in '%s' are not consistent. Some meshes may not follow bones after export",
    #             )
    #             % collection.name,
    #         )
    #         error_list.append(err)

    # Check visible meshes
    for obj in scn.objects:
        if obj.visible_get() and obj.type == "MESH":
            if check_multiple_collections(obj):
                err = ErrorInfo(
                    code=1,
                    category=ErrorCategory.ERROR,
                    message=tip_(
                        "'%s' belongs to multiple collections. The object's appearance may change after export",
                    )
                    % obj.name,
                )
                error_list.append(err)

            if check_vertex_count_based_on_shape_with_shapekeys(obj):
                err = ErrorInfo(
                    code=3,
                    category=ErrorCategory.ERROR,
                    message=tip_(
                        "'%s' has a shapekey with a modifier changing vertex count based on shape",
                    )
                    % obj.name,
                )
                error_list.append(err)

            if check_armature_modifier_order(obj):
                err = ErrorInfo(
                    code=4,
                    category=ErrorCategory.WARNING,
                    message=tip_(
                        "Armature modifier in '%s' should be set at the bottom",
                    )
                    % obj.name,
                )
                error_list.append(err)

            if check_hidden_armature(obj):
                err = ErrorInfo(
                    code=8,
                    category=ErrorCategory.WARNING,
                    message=tip_(
                        "Armature '%s' referenced by modifiers will not be exported as it's hidden",
                    )
                    % obj.find_armature().name,
                )
                error_list.append(err)

            if check_geometry_node(obj):
                err = ErrorInfo(
                    code=6,
                    category=ErrorCategory.WARNING,
                    message=tip_("'%s''s GeometryNode may not be exportable")
                    % obj.name,
                )
                error_list.append(err)

    return error_list
