import bpy

from .exporter import ExportError
from .process import start_background_export, start_foreground_export
from .validator import validate


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

        check_results = []

        if export_settings.use_check_before_export:
            check_results = validate(context)

        if len(check_results) > 0:
            for res in check_results:
                self.report({res.category.value}, res.message)
            self.report({"ERROR"}, "[Validation Failed]")
        else:
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
