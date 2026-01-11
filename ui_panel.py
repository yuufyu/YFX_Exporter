import bpy
import bpy_types


def show_popup_message(
    context: bpy_types.Context,
    message: str = "",
    title: str = "Message Box",
    icon: str = "INFO",
) -> None:
    def draw(self: bpy.types.Panel, context: bpy_types.Context) -> None:
        self.layout.label(text=message)

    context.window_manager.popup_menu(draw, title=title, icon=icon)


class View3dSidePanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "YFX"


class YFX_EXPORTER_MT_collection_list_context(bpy.types.Menu):
    bl_label = "Collection list context menu"

    def draw(self, context: bpy_types.Context) -> None:
        layout = self.layout
        layout.separator()
        layout.operator("yfx_exporter.clear_list", icon="X")


class YFX_EXPORTER_UL_colllection(bpy.types.UIList):
    def draw_item(
        self,
        context: bpy_types.Context,
        layout: bpy.types.UILayout,
        data: bpy.types.AnyType,
        item: bpy.types.AnyType,
        icon: int,
        active_data: bpy.types.AnyType,
        active_propname: str,
        index: int,
    ) -> None:
        if item.collection_ptr:
            row = layout.row()
            row.prop(
                item.collection_ptr,
                "name",
                text="",
                translate=False,
                emboss=False,
                icon="OUTLINER_COLLECTION",
            )

    def invoke(self, context: bpy_types.Context, event: bpy.types.Event) -> None:
        pass


class YFX_EXPORTER_PT_export_panel(View3dSidePanel, bpy.types.Panel):
    bl_label = "YFX Exporter"
    bl_idname = "YFX_EXPORTER_PT_export_panel"

    def draw(self, context: bpy_types.Context) -> None:
        layout = self.layout
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings
        settings_file = scn.yfx_exporter_settings.export_settings_file

        row = layout.row()
        col = row.column(align=True)
        row = col.row(align=True)
        row.scale_y = 1.5
        row.operator("yfx_exporter.export_fbx", icon="CUBE")

        row = layout.row(align=True)

        row.prop(settings_file, "settings_file")

        row = layout.row(align=True)
        if settings.export_path == "":
            row.alert = True

        row.prop(settings, "export_path", text="")

        row = row.row(align=True)
        row.operator(
            "yfx_exporter.select_file",
            text="",
            icon="FILE_FOLDER",
        ).filepath = settings.export_path

        row = layout.row(align=True)
        row.operator("yfx_exporter.check_model", icon="ERROR")


class YFX_EXPORTER_PT_fbx_export_settings_main_panel(View3dSidePanel, bpy.types.Panel):
    bl_label = "FBX settings"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"
    bl_parent_id = "YFX_EXPORTER_PT_export_panel"
    bl_options = {"DEFAULT_CLOSED"}  # noqa: RUF012

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        layout = self.layout

        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        row = layout.row(align=True)
        row.prop(fbx_export_settings, "path_mode")
        sub = row.row(align=True)
        sub.enabled = fbx_export_settings.path_mode == "COPY"
        sub.prop(
            fbx_export_settings,
            "embed_textures",
            text="",
            icon="PACKAGE" if fbx_export_settings.embed_textures else "UGLYPACKAGE",
        )


class YFX_EXPORTER_PT_fbx_export_settings_include_panel(
    View3dSidePanel,
    bpy.types.Panel,
):
    bl_label = "Include"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_include_panel"
    bl_parent_id = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.column().prop(fbx_export_settings, "object_types")
        layout.prop(fbx_export_settings, "use_custom_props")


class YFX_EXPORTER_PT_fbx_export_settings_transform_panel(
    View3dSidePanel,
    bpy.types.Panel,
):
    bl_label = "Transform"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_transform_panel"
    bl_parent_id = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.prop(fbx_export_settings, "global_scale")
        layout.prop(fbx_export_settings, "apply_scale_options")

        layout.prop(fbx_export_settings, "axis_forward")
        layout.prop(fbx_export_settings, "axis_up")

        layout.prop(fbx_export_settings, "apply_unit_scale")
        layout.prop(fbx_export_settings, "use_space_transform")
        row = layout.row()
        row.prop(fbx_export_settings, "bake_space_transform")
        row.label(text="", icon="ERROR")


class YFX_EXPORTER_PT_fbx_export_settings_geometry_panel(
    View3dSidePanel,
    bpy.types.Panel,
):
    bl_label = "Geometry"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_geometry_panel"
    bl_parent_id = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.prop(fbx_export_settings, "mesh_smooth_type")
        layout.prop(fbx_export_settings, "use_subsurf")
        layout.prop(fbx_export_settings, "use_mesh_modifiers")
        layout.prop(fbx_export_settings, "use_mesh_edges")
        layout.prop(fbx_export_settings, "use_triangles")
        sub = layout.row()
        # ~ sub.enabled = operator.mesh_smooth_type in {'OFF'}
        sub.prop(fbx_export_settings, "use_tspace")
        layout.prop(fbx_export_settings, "colors_type")
        layout.prop(fbx_export_settings, "prioritize_active_color")


class YFX_EXPORTER_PT_fbx_export_settings_armature_panel(
    View3dSidePanel,
    bpy.types.Panel,
):
    bl_label = "Armature"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_armature_panel"
    bl_parent_id = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.prop(fbx_export_settings, "primary_bone_axis")
        layout.prop(fbx_export_settings, "secondary_bone_axis")
        layout.prop(fbx_export_settings, "armature_nodetype")
        layout.prop(fbx_export_settings, "use_armature_deform_only")
        layout.prop(fbx_export_settings, "add_leaf_bones")


class YFX_EXPORTER_PT_fbx_export_settings_bake_animation_panel(
    View3dSidePanel,
    bpy.types.Panel,
):
    bl_label = "Bake Animation"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_bake_animation_panel"
    bl_parent_id = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"

    def draw_header(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        self.layout.prop(fbx_export_settings, "bake_anim", text="")

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        fbx_export_settings = settings.export_settings.fbx_export_settings

        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        layout.enabled = fbx_export_settings.bake_anim
        layout.prop(fbx_export_settings, "bake_anim_use_all_bones")
        layout.prop(fbx_export_settings, "bake_anim_use_nla_strips")
        layout.prop(fbx_export_settings, "bake_anim_use_all_actions")
        layout.prop(fbx_export_settings, "bake_anim_force_startend_keying")
        layout.prop(fbx_export_settings, "bake_anim_step")
        layout.prop(fbx_export_settings, "bake_anim_simplify_factor")


class YFX_EXPORTER_PT_fbx_export_settings_custom(
    View3dSidePanel,
    bpy.types.Panel,
):
    bl_label = "Custom"
    bl_idname = "YFX_EXPORTER_PT_fbx_export_settings_custom"
    bl_parent_id = "YFX_EXPORTER_PT_fbx_export_settings_main_panel"

    def draw(self, context: bpy_types.Context) -> None:
        scn = context.scene
        settings = scn.yfx_exporter_settings
        export_settings = settings.export_settings
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False  # No animation.

        row = layout.row()
        row.prop(export_settings, "use_main_process_export")
        row.label(text="", icon="ERROR")


class YFX_EXPORTER_PT_collection_panel(View3dSidePanel, bpy.types.Panel):
    bl_label = "Merge Collections"
    bl_idname = "YFX_EXPORTER_PT_collection_panel"
    bl_parent_id = "YFX_EXPORTER_PT_export_panel"

    def draw(self, context: bpy_types.Context) -> None:
        layout = self.layout
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings

        row = layout.row()
        col = row.column(align=True)
        row = col.row(align=True)
        row.operator_menu_enum(
            "yfx_exporter.add_collection",
            "user_collections",
            icon="ADD",
        )

        row = layout.row()
        row.template_list(
            "YFX_EXPORTER_UL_colllection",
            "yfx_exporter_collection_list_panel",
            settings,
            "collections",
            settings,
            "collection_index",
            rows=5,
        )

        col = row.column(align=True)
        col.operator("yfx_exporter.list_action", icon="X", text="").action = "REMOVE"
        col.operator(
            "yfx_exporter.update_collection_list",
            icon="FILE_REFRESH",
            text="",
        )
        col.separator()
        col.operator("yfx_exporter.list_action", icon="TRIA_UP", text="").action = "UP"
        col.operator(
            "yfx_exporter.list_action",
            icon="TRIA_DOWN",
            text="",
        ).action = "DOWN"


class YFX_EXPORTER_PT_collection_setting_panel(View3dSidePanel, bpy.types.Panel):
    bl_label = "Collection Settings"
    bl_idname = "YFX_EXPORTER_PT_collection_setting_panel"
    bl_parent_id = "YFX_EXPORTER_PT_collection_panel"

    def draw(self, context: bpy_types.Context) -> None:
        layout = self.layout
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings

        idx = settings.collection_index
        try:
            item = settings.collections[idx]
        except IndexError:
            pass
        else:
            row = layout.row(align=True)
            col = row.column(align=True)

            col.prop(
                item.transform_settings,
                "apply_all_transform",
            )

            col.separator()

            col.prop(
                item.vertex_group_settings,
                "delete_vertex_group",
            )


class YFX_EXPORTER_UL_shapekey(bpy.types.UIList):
    def draw_item(
        self,
        context: bpy_types.Context,
        layout: bpy.types.UILayout,
        data: bpy.types.AnyType,
        item: bpy.types.AnyType,
        icon: int,
        active_data: bpy.types.AnyType,
        active_propname: str,
        index: int,
    ) -> None:
        if item.name:
            row = layout.row()
            row.label(text=item.name, translate=False, icon="SHAPEKEY_DATA")

    def invoke(self, context: bpy_types.Context, event: bpy.types.Event) -> None:
        pass


class YFX_EXPORTER_PT_shapekey_settings_panel(View3dSidePanel, bpy.types.Panel):
    bl_label = "Shapekey Settings"
    bl_idname = "YFX_EXPORTER_PT_shapekey_settings_panel"
    bl_parent_id = "YFX_EXPORTER_PT_collection_setting_panel"

    def draw(self, context: bpy_types.Context) -> None:
        layout = self.layout
        scn = context.scene
        settings = scn.yfx_exporter_settings.export_settings
        len_collections = len(settings.collections)

        row = layout.row(align=True)
        col = row.column(align=True)
        row = col.row(align=True)
        row.operator(
            "yfx_exporter.update_shapekey_list",
            icon="FILE_REFRESH",
        )

        if len_collections > 0 and 0 <= settings.collection_index < len_collections:
            shapekey_settings_path = f"scene.yfx_exporter_settings.export_settings\
.collections[{settings.collection_index}].shapekey_settings"
            list_path = shapekey_settings_path + ".shapekeys"
            active_index_path = shapekey_settings_path + ".shapekey_index"

            collection_setting = settings.collections[settings.collection_index]
            shapekey_settings = collection_setting.shapekey_settings

            row = layout.row()
            row.template_list(
                "YFX_EXPORTER_UL_shapekey",
                "yfx_exporter_shapekey_list_panel",
                shapekey_settings,
                "shapekeys",
                shapekey_settings,
                "shapekey_index",
                rows=5,
            )

            col = row.column(align=True)

            props = col.operator(
                "uilist.entry_move",
                icon="TRIA_UP",
                text="",
            )
            props.direction = "UP"
            props.list_path = list_path
            props.active_index_path = active_index_path

            props = col.operator(
                "uilist.entry_move",
                icon="TRIA_DOWN",
                text="",
            )
            props.direction = "DOWN"
            props.list_path = list_path
            props.active_index_path = active_index_path

            len_shapekeys = len(shapekey_settings.shapekeys)
            if (
                len_shapekeys > 0
                and 0 <= shapekey_settings.shapekey_index < len_shapekeys
            ):
                shapekey_setting = shapekey_settings.shapekeys[
                    shapekey_settings.shapekey_index
                ]

                row = layout.row(align=True)
                col = row.column(align=True)

                col.prop(
                    shapekey_setting,
                    "separate_shapekey",
                )
                if shapekey_setting.separate_shapekey:
                    col.use_property_split = True
                    col.use_property_decorate = False  # No animation.
                    col.prop(
                        shapekey_setting,
                        "separate_shapekey_left",
                    )
                    col.prop(
                        shapekey_setting,
                        "separate_shapekey_right",
                    )
                    col.prop(
                        shapekey_setting,
                        "delete_shapekey",
                    )
