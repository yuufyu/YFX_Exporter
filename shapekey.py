import graphlib

import bpy


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


def sort_blend_settings(blend_settings):
    """
    依存関係に基づいて blend_settings をトポロジカルソートする。
    """
    # 依存関係を保持する辞書 { 作成するキー: {必要なキーのセット} }
    # graphlib は「依存されるもの」を先に返すため、
    # 「このキーを作るには、これらのソースが必要」という定義にする
    dependencies = {}
    settings_map = {}

    for info in blend_settings:
        name = info["name"]
        settings_map[name] = info
        sources = {src["name"] for src in info.get("sources", [])}
        dependencies[name] = sources

    ts = graphlib.TopologicalSorter(dependencies)

    try:
        # ソート実行
        sorted_names = list(ts.static_order())

        # blend_settings に含まれていない（既存の）キーも含まれるため、
        # 今回の設定に含まれるものだけを抽出して並び替える
        return [settings_map[name] for name in sorted_names if name in settings_map]

    except graphlib.CycleError:
        # AがBを必要とし、BがAを必要とするような循環参照がある場合
        raise ValueError("シェイプキーの合成設定に循環参照が見つかりました。")


def create_deform_shape_key(target_obj, name, deform_info):
    """頂点グループとベクトルに基づいて新しいシェイプキーを生成する"""
    vg_name = deform_info.get("target_group")
    vector = deform_info.get("vector", [0.0, 0.0, 0.0])

    if vg_name not in target_obj.vertex_groups:
        print(f"警告: 頂点グループ {vg_name} が見つかりません。")
        return

    # ミックス用の新規シェイプキーを追加
    new_key = target_obj.shape_key_add(name=name, from_mix=False)
    vg_index = target_obj.vertex_groups[vg_name].index

    # 各頂点に対して移動を計算
    # target_obj はすでにモディファイア適用済みの想定
    for i, vert in enumerate(target_obj.data.vertices):
        weight = 0.0
        try:
            # 頂点から該当グループのウェイトを取得
            for g in vert.groups:
                if g.group == vg_index:
                    weight = g.weight
                    break
        except:
            pass

        if weight > 0:
            # 相対座標をオフセット (vector は [x, y, z])
            offset = [v * weight for v in vector]
            # シェイプキーのデータ(data[i].co)は絶対座標
            new_key.data[i].co[0] += offset[0]
            new_key.data[i].co[1] += offset[1]
            new_key.data[i].co[2] += offset[2]


def process_shape_key_blending(obj, blend_settings):
    """JSONの設定に基づきシェイプキーを合成する"""
    if not obj.data.shape_keys:
        return

    sorted_settings = sort_blend_settings(blend_settings)

    # 1. すべての既存シェイプキーの値を一度 0 にリセット
    for key in obj.data.shape_keys.key_blocks:
        key.value = 0.0

    # 2. 合成設定を一つずつループ
    for blend_info in sorted_settings:
        new_name = blend_info["name"]
        sources = blend_info.get("sources", [])
        deform = blend_info.get("deform", None)

        if sources:
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

            # --- 3. 新しいシェイプキーを作成、または既存のキーを更新 ---
            existing_key_idx = obj.data.shape_keys.key_blocks.find(new_name)

            if existing_key_idx == -1:
                # 新規作成の場合：現在のミックス状態から新規キーを作成
                _ = obj.shape_key_add(name=new_name, from_mix=True)
            else:
                # 既存更新の場合：現在のミックス状態から一時的なキーを作成
                target_key = obj.data.shape_keys.key_blocks[existing_key_idx]
                target_key.value = 1.0

                temp_key = obj.shape_key_add(
                    name="__YFX_temp_blend_result__",
                    from_mix=True,
                )

                # 座標データをコピーして一時キーを削除
                # 各頂点の相対座標(data[].co)をコピー
                # ※頂点数が一致していることが前提
                for i in range(len(temp_key.data)):
                    target_key.data[i].co = temp_key.data[i].co

                # 一時的なキーを削除
                obj.shape_key_remove(temp_key)

                target_key.value = 0.0

            # 4. 次の合成のためにリセット
            for src in sources:
                kb = obj.data.shape_keys.key_blocks.get(src["name"])
                if kb:
                    kb.value = 0.0
                    kb.vertex_group = ""

        if deform:
            create_deform_shape_key(obj, new_name, deform)

    # 一時的な頂点グループ（左右判定用）を削除
    # cleanup_temp_vertex_groups(obj)


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
