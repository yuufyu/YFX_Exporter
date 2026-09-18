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


def _get_or_create_shape_key(obj, name):
    """ShapeKey を取得し、存在しなければ Basis から新規作成する。"""
    shape_keys = obj.data.shape_keys
    if shape_keys is None:
        # 通常ここには来ないが、単独利用時の安全策。
        obj.shape_key_add(name="Basis", from_mix=False)
        shape_keys = obj.data.shape_keys

    key = shape_keys.key_blocks.get(name)
    if key is None:
        key = obj.shape_key_add(name=name, from_mix=False)
    return key


def _normalize_side(raw_side):
    """JSON の side 指定を LEFT / RIGHT / BOTH に正規化する。"""
    value = str(raw_side or "BOTH").upper()
    if value.startswith("L"):
        return "LEFT"
    if value.startswith("R"):
        return "RIGHT"
    return "BOTH"


def _side_factor(x, side, eps=0.0000001):
    """従来の TEMP_LEFT/TEMP_RIGHT と同じ頂点ウェイトを返す。"""
    if side == "LEFT":
        if x > eps:
            return 1.0
        if -eps <= x <= eps:
            return 0.5
        return 0.0

    if side == "RIGHT":
        if x < -eps:
            return 1.0
        if -eps <= x <= eps:
            return 0.5
        return 0.0

    return 1.0


def _vertex_group_weights(obj, group_name):
    """
    Vertex Group のウェイトを頂点順の list として取得する。

    ShapeKey.vertex_group が空、またはグループが存在しない場合は、
    Blender の通常の無制限 ShapeKey と同様に全頂点 1.0 とする。
    """
    count = len(obj.data.vertices)
    if not group_name:
        return [1.0] * count

    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return [1.0] * count

    group_index = vg.index
    weights = [0.0] * count

    for vertex in obj.data.vertices:
        for group_element in vertex.groups:
            if group_element.group == group_index:
                weights[vertex.index] = group_element.weight
                break

    return weights


def _source_mask_weights(obj, source_key, side):
    """
    source 1個分の頂点マスクを返す。

    LEFT/RIGHT:
        旧実装が一時 VertexGroup を source_key.vertex_group に上書きしていた
        挙動を直接再現する。そのため source_key 本来の vertex_group は使わない。

    BOTH:
        source_key に元から vertex_group がある場合はそのウェイトを尊重する。
        旧 from_mix 実装で BOTH を指定したときの挙動に対応する。
    """
    if side in {"LEFT", "RIGHT"}:
        return [_side_factor(v.co.x, side) for v in obj.data.vertices]

    return _vertex_group_weights(obj, source_key.vertex_group)


def _validate_relative_shape_keys(obj):
    """直接合成が対象とする Relative ShapeKey かを検証する。"""
    shape_keys = obj.data.shape_keys
    if shape_keys is None:
        return False

    if not shape_keys.use_relative:
        raise ValueError(
            f"{obj.name}: YFX の sources 合成は Relative ShapeKey のみ対応しています。"
        )

    return True


def _compose_shape_key_direct(obj, new_name, sources):
    """
    from_mix を使わずに sources を直接合成する。

    Relative ShapeKey の実効変形量は
        source.data - source.relative_key.data
    なので、それを source weight と頂点マスクで加算する。

    target 自身に custom relative_key が設定されている場合でも、
    target の「実効 delta」が sources の合計になるよう、target.relative_key を
    合成の基準座標として使用する。
    """
    _validate_relative_shape_keys(obj)

    key_blocks = obj.data.shape_keys.key_blocks
    vertex_count = len(obj.data.vertices)

    # 先に source を解決・検証する。target 更新中に source を壊さないため、
    # delta と mask は target への書き込み前にすべて snapshot する。
    prepared_sources = []
    for src in sources:
        src_name = src["name"]
        source_key = key_blocks.get(src_name)
        if source_key is None:
            print(
                f"警告: {src_name} が存在しないため、{new_name} の作成をスキップします。"
            )
            return False

        relative_key = source_key.relative_key
        if relative_key is None:
            raise ValueError(
                f"{obj.name}: ShapeKey '{src_name}' の relative_key を取得できません。"
            )

        if len(source_key.data) != vertex_count or len(relative_key.data) != vertex_count:
            raise ValueError(
                f"{obj.name}: ShapeKey '{src_name}' の頂点数が Mesh と一致しません。"
            )

        weight = float(src.get("weight", 1.0))
        side = _normalize_side(src.get("side", "BOTH"))
        mask = _source_mask_weights(obj, source_key, side)

        # mathutils.Vector の参照を保持せず copy() しておく。
        # 後段で target が source/relative_key と関係していても安全にする。
        deltas = [
            source_key.data[i].co.copy() - relative_key.data[i].co.copy()
            for i in range(vertex_count)
        ]
        prepared_sources.append((weight, mask, deltas))

    target_key = _get_or_create_shape_key(obj, new_name)
    target_relative = target_key.relative_key
    if target_relative is None:
        target_relative = obj.data.shape_keys.reference_key

    if len(target_key.data) != vertex_count or len(target_relative.data) != vertex_count:
        raise ValueError(
            f"{obj.name}: ShapeKey '{new_name}' の頂点数が Mesh と一致しません。"
        )

    # target_relative 自身が後で書き換わるケースに備えて基準座標も snapshot。
    base_coords = [target_relative.data[i].co.copy() for i in range(vertex_count)]

    for i in range(vertex_count):
        result = base_coords[i].copy()
        for weight, mask, deltas in prepared_sources:
            factor = weight * mask[i]
            if factor != 0.0:
                result += deltas[i] * factor
        target_key.data[i].co = result

    # 合成結果そのものには Vertex Group 制限を持たせない。
    # 旧実装の New Shape from Mix で焼き込んだ結果と同じ考え方。
    target_key.vertex_group = ""
    target_key.value = 0.0
    return True


def create_deform_shape_key(target_obj, name, deform_info):
    """頂点グループとベクトルに基づいて ShapeKey を直接生成・更新する。"""
    _validate_relative_shape_keys(target_obj)

    vg_name = deform_info.get("target_group")
    vector = deform_info.get("vector", [0.0, 0.0, 0.0])

    vg = target_obj.vertex_groups.get(vg_name) if vg_name else None
    if vg is None:
        print(f"警告: 頂点グループ {vg_name} が見つかりません。")
        return False

    if len(vector) != 3:
        raise ValueError(
            f"{target_obj.name}: deform.vector は3要素で指定してください: {vector}"
        )

    target_key = _get_or_create_shape_key(target_obj, name)
    relative_key = target_key.relative_key
    if relative_key is None:
        relative_key = target_obj.data.shape_keys.reference_key

    vertex_count = len(target_obj.data.vertices)
    if len(relative_key.data) != vertex_count:
        raise ValueError(
            f"{target_obj.name}: ShapeKey '{name}' の頂点数が Mesh と一致しません。"
        )

    weights = _vertex_group_weights(target_obj, vg_name)
    offset_vector = tuple(float(v) for v in vector)

    # 既存キー更新でも差分が累積しないよう、毎回 relative_key から作り直す。
    for i in range(vertex_count):
        co = relative_key.data[i].co.copy()
        weight = weights[i]
        if weight != 0.0:
            co.x += offset_vector[0] * weight
            co.y += offset_vector[1] * weight
            co.z += offset_vector[2] * weight
        target_key.data[i].co = co

    target_key.vertex_group = ""
    target_key.value = 0.0
    return True


def process_shape_key_blending(obj, blend_settings):
    """
    JSON の設定に基づき ShapeKey を合成する。

    Blender の evaluated mix / depsgraph / shape_key_add(from_mix=True) には依存せず、
    Relative ShapeKey の座標差分を直接計算する。
    """
    if not obj.data.shape_keys:
        return

    _validate_relative_shape_keys(obj)
    sorted_settings = sort_blend_settings(blend_settings)

    # 旧実装と同じく export 時の ShapeKey 値は 0 に揃える。
    # ただし、この値は合成計算には一切使用しない。
    for key in obj.data.shape_keys.key_blocks:
        key.value = 0.0

    for blend_info in sorted_settings:
        new_name = blend_info["name"]
        sources = blend_info.get("sources", [])
        deform = blend_info.get("deform")

        if sources:
            _compose_shape_key_direct(obj, new_name, sources)

        if deform:
            create_deform_shape_key(obj, new_name, deform)

    # FBX 出力直前も全 value を 0 に保証する。
    # direct compose なので、ここで depsgraph update は不要。
    for key in obj.data.shape_keys.key_blocks:
        key.value = 0.0


def create_temp_side_vertex_group(obj, side, eps=0.0000001):
    """
    後方互換用。

    direct compose では使用しないが、外部コードがこの関数を import している
    可能性を考慮して残している。
    """
    vg_name = f"TEMP_{side}"
    if vg_name in obj.vertex_groups:
        return vg_name

    vg = obj.vertex_groups.new(name=vg_name)
    for v in obj.data.vertices:
        factor = _side_factor(v.co.x, side, eps)
        if factor != 0.0:
            vg.add([v.index], factor, "REPLACE")

    return vg_name


def cleanup_temp_vertex_groups(obj):
    """旧方式で作成された一時的な頂点グループを削除する。"""
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
