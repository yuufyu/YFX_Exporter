import bpy

from .merge import get_child_objects


def insert_shapekey(obj: bpy.types.Object, name: str, index: int) -> bpy.types.ShapeKey:
    key_blocks_len = len(obj.data.shape_keys.key_blocks)
    if key_blocks_len <= 1:
        return None

    shapekey = obj.shape_key_add(name=name, from_mix=False)

    stash_active_index = obj.active_shape_key_index
    obj.active_shape_key_index = key_blocks_len

    for _ in range(key_blocks_len - index - 1):
        bpy.ops.object.shape_key_move(type="UP")
    obj.active_shape_key_index = stash_active_index

    return shapekey


def separate_shapekey(
    obj: bpy.types.Object,
    source: str,
    left: str,
    right: str,
    eps: float = 0.0000001,
) -> None:
    key_blocks = obj.data.shape_keys.key_blocks

    source_shapekey_idx = key_blocks.find(source)
    if source_shapekey_idx < 0:
        return
    source_shapekey = key_blocks[source_shapekey_idx]
    right_shapekey = (
        insert_shapekey(obj, right, source_shapekey_idx) if right else None
    )  # No error check
    left_shapekey = (
        insert_shapekey(obj, left, source_shapekey_idx) if left else None
    )  # No error check
    basis_shapekey = key_blocks[0]

    for i in range(len(source_shapekey.data)):
        co = source_shapekey.data[i].co

        if co.x > eps:
            if left_shapekey:
                left_shapekey.data[i].co = co
        elif co.x < -eps:
            if right_shapekey:
                right_shapekey.data[i].co = co
        else:
            basis_co = basis_shapekey.data[i].co
            center_co = basis_co + ((co - basis_co) / 2)
            if left_shapekey:
                left_shapekey.data[i].co = center_co

            if right_shapekey:
                right_shapekey.data[i].co = center_co


def separate_shapekey_lr(
    obj: bpy.types.Object,
    shapekey_settings: bpy.types.AnyType,
) -> None:
    shapekeys = obj.data.shape_keys
    if shapekeys is None or len(shapekeys.key_blocks) <= 1:
        return

    key_blocks = shapekeys.key_blocks
    for shapekey_setting in shapekey_settings.shapekeys:
        if shapekey_setting.separate_shapekey:
            idx = key_blocks.find(shapekey_setting.name)
            left = shapekey_setting.separate_shapekey_left
            right = shapekey_setting.separate_shapekey_right
            if idx > 0:
                if left or right:
                    separate_shapekey(obj, shapekey_setting.name, left, right)

                if shapekey_setting.delete_shapekey:
                    obj.shape_key_remove(key_blocks[idx])


def remove_unlisted_shapekeys(obj: bpy.types.Object, shapekey_settings: list) -> None:
    """
    sort_shapekey 実行後、指定リストに含まれない（末尾に送られなかった）
    シェイプキーをすべて削除する。
    """
    shapekeys = obj.data.shape_keys
    if shapekeys is None:
        return

    key_blocks = shapekeys.key_blocks
    total_keys = len(key_blocks)

    # 常に保持すべき 'Basis' を除いた、設定ファイルにある有効なキーの数をカウント
    # (findで存在確認できたものだけをカウントするのがより安全です)
    valid_setting_count = 0
    for s in shapekey_settings:
        if s["name"] in key_blocks:
            valid_setting_count += 1

    # 削除すべき数 = (現在の全数) - (設定にある数) - (Basisキー 1つ)
    # Basis は通常 index 0 に固定されているため、これを飛ばして削除します。
    num_to_remove = total_keys - valid_setting_count - 1

    if num_to_remove <= 0:
        return

    # print(f"{num_to_remove} 個の未定義シェイプキーを削除します。")

    # index 1 (Basisの次) から順番に削除
    # 削除するたびにインデックスが詰まるため、常に index 1 を消し続ければOKです
    for _ in range(num_to_remove):
        obj.shape_key_remove(key_blocks[1])


def process_shape_key_blending(obj, blend_settings):
    """JSONの設定に基づきシェイプキーを合成する"""
    if not obj.data.shape_keys:
        return

    # 1. すべての既存シェイプキーの値を一度 0 にリセット
    for key in obj.data.shape_keys.key_blocks:
        key.value = 0.0

    # 2. 合成設定を一つずつループ
    for blend_info in blend_settings:
        new_name = blend_info["name"]
        sources = blend_info.get("sources", [])

        if not sources:
            continue

        # --- 追加: ソースの存在チェック ---
        # 1つでも存在しないキーがあれば、この新規シェイプキー作成をスキップ
        missing_source = False
        for src in sources:
            if src["name"] not in obj.data.shape_keys.key_blocks:
                print(
                    f"警告: {src['name']} が存在しないため、{new_name} の作成をスキップします。",
                )
                missing_source = True
                break
        if missing_source:
            continue
        # ------------------------------

        # 各ソース（合成元）の値を設定
        for src in sources:
            src_name = src["name"]
            weight = src.get("weight", 1.0)
            raw_side = str(src.get("side", "BOTH")).upper()

            # サイドの判定をファジーに (Lから始まればLEFT, RならRIGHT)
            if raw_side.startswith("L"):
                determined_side = "LEFT"
            elif raw_side.startswith("R"):
                determined_side = "RIGHT"
            else:
                determined_side = "BOTH"

            key_block = obj.data.shape_keys.key_blocks.get(src_name)

            # 重みを設定
            key_block.value = weight

            # 左右分離の処理
            if determined_side in ["LEFT", "RIGHT"]:
                temp_vg_name = create_temp_side_vertex_group(obj, determined_side)
                key_block.vertex_group = temp_vg_name

        # 3. 新しいシェイプキーを作成
        # すでに同名のキーがある場合は上書きせずスキップ（または必要に応じて削除して作り直し）
        if obj.data.shape_keys.key_blocks.find(new_name) == -1:
            obj.shape_key_add(name=new_name, from_mix=True)
            print(f"作成完了: {new_name}")
        else:
            print(f"スキップ: {new_name} は既に存在します。")

        # 4. 次の合成のためにリセット
        for src in sources:
            kb = obj.data.shape_keys.key_blocks.get(src["name"])
            if kb:
                kb.value = 0.0
                kb.vertex_group = ""

    # 一時的な頂点グループ（左右判定用）を削除
    cleanup_temp_vertex_groups(obj)


def create_temp_side_vertex_group(obj, side, eps=0.0000001):
    """原点からの座標に基づき、左右どちらかのみに影響する一時的な頂点グループを作成"""
    vg_name = f"TEMP_{side}"
    if vg_name in obj.vertex_groups:
        return vg_name

    vg = obj.vertex_groups.new(name=vg_name)

    # 全頂点をループして、座標に応じてウェイトを割り当て
    # LEFT: X > 0, RIGHT: X < 0 (Blenderの標準的な左右)
    for v in obj.data.vertices:
        if (side == "LEFT" and v.co.x > eps) or (side == "RIGHT" and v.co.x < -eps):
            vg.add([v.index], 1.0, "REPLACE")
        elif (side == "LEFT" or side == "RIGHT") and -eps <= v.co.x <= eps:
            vg.add([v.index], 0.5, "REPLACE")

    return vg_name


def cleanup_temp_vertex_groups(obj):
    """一時的な頂点グループを削除"""
    for side in ["LEFT", "RIGHT"]:
        vg = obj.vertex_groups.get(f"TEMP_{side}")
        if vg:
            obj.vertex_groups.remove(vg)


def sort_shapekey(obj: bpy.types.Object, shapekey_settings: bpy.types.AnyType) -> None:
    shapekeys = obj.data.shape_keys
    if shapekeys is None or len(shapekeys.key_blocks) <= 1:
        return

    stash_active_index = obj.active_shape_key_index
    key_blocks = shapekeys.key_blocks
    for s in shapekey_settings:
        idx = key_blocks.find(s["name"])
        if idx < 0:
            continue
        obj.active_shape_key_index = idx
        bpy.ops.object.shape_key_move(type="BOTTOM")

    obj.active_shape_key_index = stash_active_index


def get_collection_shapekeys(collection: bpy.types.Collection) -> list:
    objects = get_child_objects(collection)
    total_shapekeys = []
    for obj in objects:
        shapekeys = obj.data.shape_keys
        if shapekeys is not None and len(shapekeys.key_blocks) > 1:
            shapekey_names = [key.name for key in shapekeys.key_blocks]
            total_shapekeys.extend(shapekey_names[1:])

    return list(dict.fromkeys(total_shapekeys))


def update_collection_shepekey_settings(collection_setting: bpy.types.AnyType) -> None:
    shapekey_settings = collection_setting.shapekey_settings
    shapekeys = shapekey_settings.shapekeys

    # Add new shapekeys
    shapekey_names = get_collection_shapekeys(collection_setting.collection_ptr)
    for name in shapekey_names:
        if shapekeys.find(name) < 0:
            shapekey_item = shapekeys.add()
            shapekey_item.name = name

    # Remove deleted shapekeys
    remove_idx = [
        i for i, shapekey in enumerate(shapekeys) if shapekey.name not in shapekey_names
    ]
    for i in reversed(remove_idx):
        shapekeys.remove(i)


def update_active_collection_shapekeys(context: bpy.types.Context) -> None:
    if context and context.scene.yfx_exporter_settings:
        export_settings = context.scene.yfx_exporter_settings.export_settings
        collection_settings = export_settings.collections
        collection_index = export_settings.collection_index
        len_collections = len(collection_settings)

        if len_collections > 0 and 0 <= collection_index < len_collections:
            collection_setting = collection_settings[collection_index]
            update_collection_shepekey_settings(collection_setting)


def update_all_collection_shapekeys(context: bpy.types.Context) -> None:
    if context and context.scene.yfx_exporter_settings:
        export_settings = context.scene.yfx_exporter_settings.export_settings
        collection_settings = export_settings.collections
        len_collections = len(collection_settings)

        for i in range(len_collections):
            collection_setting = collection_settings[i]
            update_collection_shepekey_settings(collection_setting)
