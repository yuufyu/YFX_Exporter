from enum import Enum
from typing import ClassVar

import bpy
import bpy_extras
import bpy_types

from .exporter import ExportError
from .process import start_background_export, start_foreground_export
from .shapekey import update_active_collection_shapekeys
from .utils import update_active_setting_items, update_all_setting_items
from .validator import validate


def list_actions_move(items: bpy.types.AnyType, index: int, action: str) -> tuple:
    idx = index

    try:
        item = items[idx]
    except IndexError:
        info = "Out of range"
    else:
        if item.collection_ptr is None:
            index -= 1
            items.remove(idx)
        elif action == "DOWN" and idx < len(items) - 1:
            items.move(idx, idx + 1)
            index += 1
            info = 'Item "%s" moved to position %d' % (
                item.collection_ptr.name,
                index + 1,
            )

        elif action == "UP" and idx >= 1:
            items.move(idx, idx - 1)
            index -= 1
            info = 'Item "%s" moved to position %d' % (
                item.collection_ptr.name,
                index + 1,
            )

        elif action == "REMOVE":
            info = 'Item "%s" removed from list' % (item.collection_ptr.name)
            index -= 1
            items.remove(idx)
        else:
            info = "Unknown action"

    return index, info


# Collection list Operators
#################################################
class YFX_EXPORTER_OT_update_collection_list(bpy.types.Operator):
    """Remove all invalid items"""

    bl_idname = "yfx_exporter.update_collection_list"
    bl_label = "Update Merge Collections"
    bl_description = "Update merge collection list"
    bl_options: ClassVar[set] = {"REGISTER"}

    def execute(self, context: bpy_types.Context) -> set:
        update_active_setting_items(self, context)
        return {"FINISHED"}


class YFX_EXPORTER_OT_list_actions(bpy.types.Operator):
    """Move items up and down, add and remove"""

    bl_idname = "yfx_exporter.list_action"
    bl_label = "List Actions"
    bl_description = "Move items up and down, add and remove"
    bl_options: ClassVar[set] = {"REGISTER"}

    action: bpy.props.EnumProperty(
        items=(
            ("UP", "Up", ""),
            ("DOWN", "Down", ""),
            ("REMOVE", "Remove", ""),
            ("ADD", "Add", ""),
        ),
    )

    def invoke(self, context: bpy_types.Context, event: bpy.types.Event) -> set:
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings

        index, info = list_actions_move(
            settings.collections,
            settings.collection_index,
            self.action,
        )

        self.report({"INFO"}, info)
        settings.collection_index = index

        return {"FINISHED"}


class YFX_EXPORTER_OT_clear_list(bpy.types.Operator):
    # Clear all items of the list
    bl_idname = "yfx_exporter.clear_list"
    bl_label = "Clear List"
    bl_description = "Clear all items of the list"
    bl_options: ClassVar[set] = {"INTERNAL"}

    @classmethod
    def poll(cls, context: bpy_types.Context) -> None:
        return bool(context.scene.yfx_exporter_settings.export_settings.collections)

    def invoke(self, context: bpy_types.Context, event: bpy.types.Event) -> Enum:
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context: bpy_types.Context) -> None:
        collections = context.scene.yfx_exporter_settings.export_settings.collections
        if bool(collections):
            collections.clear()
            self.report({"INFO"}, "All items removed")
        else:
            self.report({"INFO"}, "Nothing to remove")
        return {"FINISHED"}


class YFX_EXPORTER_OT_add_viewport_selection(bpy.types.Operator):
    """Add all items currently selected in the viewport"""

    bl_idname = "yfx_exporter.add_viewport_selection"
    bl_label = "Add Viewport Selection to List"
    bl_description = "Add all items currently selected in the viewport"
    bl_options: ClassVar[set] = {"REGISTER", "UNDO"}

    def execute(self, context: bpy_types.Context) -> set:
        scn = context.scene
        selected_objs = context.selected_objects
        if selected_objs:
            new_objs = []
            for i in selected_objs:
                item = scn.yfx_exporter_settings.export_settings.collections.add()
                item.name = i.name
                item.obj = i
                new_objs.append(item.name)
            info = ", ".join(map(str, new_objs))
            self.report({"INFO"}, 'Added: "%s"' % (info))
        else:
            self.report({"INFO"}, "Nothing selected in the Viewport")
        return {"FINISHED"}


class YFX_EXPORTER_OT_add_collection(bpy.types.Operator):
    bl_idname = "yfx_exporter.add_collection"
    bl_label = "Add Collection"

    def get_collection_list_callback(
        self: bpy.types.Operator,
        context: bpy_types.Context,
    ) -> list:
        scn = context.scene
        export_settings = scn.yfx_exporter_settings.export_settings
        custom_collections = [
            c.collection_ptr.name
            for c in export_settings.collections
            if c.collection_ptr
        ]

        # There is a known bug with using a callback,
        # Python must keep a reference to the strings returned by the callback
        # or Blender will misbehave or even crash.
        YFX_EXPORTER_OT_add_collection.collection_list_enum_items = [
            (
                c.name,
                c.name + " ",  # Append a space to prevent translation
                c.name,
                "OUTLINER_COLLECTION",
                idx,
            )
            for idx, c in enumerate(bpy.data.collections)
            if c.name not in custom_collections and bpy.context.scene.user_of_id(c)
        ]
        return YFX_EXPORTER_OT_add_collection.collection_list_enum_items

    user_collections: bpy.props.EnumProperty(items=get_collection_list_callback)

    def execute(self, context: bpy_types.Context) -> set:
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings
        act_coll = bpy.data.collections.get(self.user_collections)

        if act_coll is None:
            message = "Selected Collection is Not founded"
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

        if act_coll.name in [c.collection_ptr.name for c in settings.collections]:
            info = '"%s" already in the list' % (act_coll.name)
        else:
            item = settings.collections.add()
            item.collection_ptr = act_coll
            settings.collection_index = len(settings.collections) - 1
            info = "%s added to list" % (item.collection_ptr.name)

        self.report({"INFO"}, info)

        return {"FINISHED"}


# Shapekeys list Operators
#################################################
class YFX_EXPORTER_OT_update_shapekey_list(bpy.types.Operator):
    """Update Shapekey list"""

    bl_idname = "yfx_exporter.update_shapekey_list"
    bl_label = "Update Shapekey List"
    bl_description = "Update shapekey list in collection"
    bl_options: ClassVar[set] = {"REGISTER"}

    def execute(self, context: bpy_types.Context) -> set:
        update_active_collection_shapekeys(context)
        return {"FINISHED"}


# Export Operators
#################################################
class YFX_EXPORTER_OT_select_file(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    bl_idname = "yfx_exporter.select_file"
    bl_label = "Select file in browser"

    # ExportHelper mixin class uses this
    filename_ext = ".fbx"

    filter_glob: bpy.props.StringProperty(
        default="*.fbx",
        options={"HIDDEN"},
    )

    def execute(self, context: bpy_types.Context) -> set:
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings

        settings.export_path = self.filepath

        return {"FINISHED"}


class YFX_EXPORTER_OT_export_fbx(bpy.types.Operator):
    bl_idname = "yfx_exporter.export_fbx"
    bl_label = "Export FBX"
    bl_description = "Export FBX"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.mode == "OBJECT"

    def execute(self, context: bpy.types.Context) -> set:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        export_settings = settings.export_settings

        update_all_setting_items(context)

        exist_error = False
        # results = validate(context)
        # if len(results) > 0:
        #     for res in results:
        #         if res.category == ErrorCategory.ERROR:
        #             exist_error = True
        #         self.report({res.category.value}, res.message)

        if not exist_error:
            try:
                if export_settings.use_main_process_export:
                    start_foreground_export(context)
                else:
                    start_background_export(context)
            except ExportError as e:
                self.report({"ERROR"}, str(e))
            else:
                self.report({"INFO"}, "FBX exported successfully!")

        return {"FINISHED"}


class YFX_EXPORTER_OT_check_model(bpy.types.Operator):
    bl_idname = "yfx_exporter.check_model"
    bl_label = "Check Model"
    bl_description = "A validation check on the models in the scene,\
 ensuring their exportability"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.mode == "OBJECT"

    def execute(self, context: bpy.types.Context) -> set:
        results = validate(context)
        if len(results) > 0:
            for res in results:
                self.report({res.category.value}, res.message)
        else:
            self.report(
                {"INFO"},
                "[Validation Successful] \
All models in the scene have passed the exportability check successfully",
            )
        return {"FINISHED"}
