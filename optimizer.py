import bpy


def get_used_bones(context: bpy.types.Context) -> set[str]:
    """
    シーン上で表示されているメッシュオブジェクトのVertex Groupから
    ウェイト(weight > 0)として使われているボーン名のセットを返す。
    """
    used = set()

    for obj in context.scene.objects:
        # 非表示オブジェクトはスキップ
        if obj.hide_viewport or obj.hide_get():
            continue
        if obj.type != "MESH":
            continue

        mesh = obj.data
        vgroups = obj.vertex_groups

        # 各Vertex Groupについて、weight > 0 の頂点が1つでもあれば「使用中」
        for vg in vgroups:
            for v in mesh.vertices:
                for g in v.groups:
                    if g.group == vg.index and g.weight > 0.0:
                        used.add(vg.name)
                        break
                else:
                    continue
                break

    return used


def collect_bones_to_delete(
    armature_obj: bpy.types.Object,
    used_bone_names: set[str],
) -> list[str]:
    """
    削除対象のボーン名リストを返す。
    条件: 自身と子孫ボーンがすべて未使用。
    """
    to_delete = []

    def traverse(bone) -> bool:
        """
        Returns:
            True  … bone 自身と全子孫がすべて未使用（このbone以下は削除してよい）
            False … bone 自身または子孫に使用中ボーンが1つ以上ある
        """
        # まず全子を後順に処理し、子ごとの結果を収集する
        subtree_all_unused = True
        for child in bone.children:
            child_all_unused = traverse(child)
            if not child_all_unused:
                subtree_all_unused = False
            # child_all_unused が True のケースはchildのtraverse内で
            # すでにto_deleteへ追加済みなので、ここでは何もしない

        self_unused = bone.name not in used_bone_names

        if self_unused and subtree_all_unused:
            # 自身も子孫もすべて未使用 → 削除対象
            to_delete.append(bone.name)
            return True
        # 使用中ボーンが存在 → 削除しない
        return False

    for bone in armature_obj.data.bones:
        if bone.parent is None:  # ルートボーンのみ起点にする
            traverse(bone)

    return to_delete


def remove_unused_bones(context: bpy.types.Context) -> None:
    # ---- アーマチュアを取得 ----
    armature_obj = None
    for obj in context.scene.objects:
        if obj.hide_viewport or obj.hide_get():
            continue
        if obj.type == "MESH":
            found = obj.find_armature()
            if found:
                armature_obj = found
                break

    if not armature_obj:
        print("アーマチュアが見つかりません")
        return

    used_bones = get_used_bones(context)

    # 2. 削除対象の特定
    bones_to_remove = collect_bones_to_delete(armature_obj, used_bones)

    context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature_obj.data.edit_bones
    deleted_count = 0
    for name in bones_to_remove:
        eb = edit_bones.get(name)
        if eb:
            edit_bones.remove(eb)
            deleted_count += 1
    bpy.ops.object.mode_set(mode="OBJECT")
