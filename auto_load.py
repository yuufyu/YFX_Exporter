import importlib
import inspect
import pkgutil
import typing
from pathlib import Path

import bpy

__all__ = (
    "init",
    "register",
    "unregister",
)

blender_version = bpy.app.version

modules = None
ordered_classes = None


def init() -> None:
    global modules  # noqa: PLW0603
    global ordered_classes  # noqa: PLW0603

    modules = get_all_submodules(Path(__file__).parent)
    ordered_classes = get_ordered_classes_to_register(modules)


def register() -> None:
    for cls in ordered_classes:
        bpy.utils.register_class(cls)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "register"):
            module.register()


def unregister() -> None:
    for cls in reversed(ordered_classes):
        bpy.utils.unregister_class(cls)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "unregister"):
            module.unregister()


# Import modules
#################################################


def get_all_submodules(directory):  # noqa: ANN202, ANN001
    return list(iter_submodules(directory, directory.name))


def iter_submodules(path, package_name):  # noqa: ANN202, ANN001
    for name in sorted(iter_submodule_names(path)):
        yield importlib.import_module("." + name, package_name)


def iter_submodule_names(path, root=""):  # noqa: ANN202, ANN001
    for _, module_name, is_package in pkgutil.iter_modules([str(path)]):
        if is_package:
            sub_path = path / module_name
            sub_root = root + module_name + "."
            yield from iter_submodule_names(sub_path, sub_root)
        else:
            yield root + module_name


# Find classes to register
#################################################


def get_ordered_classes_to_register(modules):  # noqa: ANN202, ANN001
    return toposort(get_register_deps_dict(modules))


def get_register_deps_dict(modules):  # noqa: ANN202, ANN001
    my_classes = set(iter_my_classes(modules))
    my_classes_by_idname = {
        cls.bl_idname: cls for cls in my_classes if hasattr(cls, "bl_idname")
    }

    deps_dict = {}
    for cls in my_classes:
        deps_dict[cls] = set(
            iter_my_register_deps(cls, my_classes, my_classes_by_idname),
        )
    return deps_dict


def iter_my_register_deps(  # noqa: ANN202
    cls,  # noqa: ANN001
    my_classes,  # noqa: ANN001
    my_classes_by_idname,  # noqa: ANN001
):
    yield from iter_my_deps_from_annotations(cls, my_classes)
    yield from iter_my_deps_from_parent_id(cls, my_classes_by_idname)


def iter_my_deps_from_annotations(cls, my_classes):  # noqa: ANN202, ANN001
    for value in typing.get_type_hints(cls, {}, {}).values():
        dependency = get_dependency_from_annotation(value)
        if dependency is not None and dependency in my_classes:
            yield dependency


def get_dependency_from_annotation(value):  # noqa: ANN202, ANN001
    if blender_version >= (2, 93):
        if isinstance(value, bpy.props._PropertyDeferred):  # noqa: SLF001
            return value.keywords.get("type")
    elif (
        isinstance(value, tuple)
        and len(value) == 2  # noqa: PLR2004
        and value[0] in (bpy.props.PointerProperty, bpy.props.CollectionProperty)
    ):
        return value[1]["type"]

    return None


def iter_my_deps_from_parent_id(cls, my_classes_by_idname):  # noqa: ANN001, ANN202
    if bpy.types.Panel in cls.__bases__:
        parent_idname = getattr(cls, "bl_parent_id", None)
        if parent_idname is not None:
            parent_cls = my_classes_by_idname.get(parent_idname)
            if parent_cls is not None:
                yield parent_cls


def iter_my_classes(modules):  # noqa: ANN202, ANN001
    base_types = get_register_base_types()
    for cls in get_classes_in_modules(modules):
        if any(base in base_types for base in cls.__bases__) and not getattr(
            cls,
            "is_registered",
            False,
        ):
            yield cls


def get_classes_in_modules(modules):  # noqa: ANN202, ANN001
    classes = set()
    for module in modules:
        for cls in iter_classes_in_module(module):
            classes.add(cls)
    return classes


def iter_classes_in_module(module):  # noqa: ANN202, ANN001
    for value in module.__dict__.values():
        if inspect.isclass(value):
            yield value


def get_register_base_types() -> set:
    return {
        getattr(bpy.types, name)
        for name in [
            "Panel",
            "Operator",
            "PropertyGroup",
            "AddonPreferences",
            "Header",
            "Menu",
            "Node",
            "NodeSocket",
            "NodeTree",
            "UIList",
            "RenderEngine",
            "Gizmo",
            "GizmoGroup",
        ]
    }


# Find order to register to solve dependencies
#################################################


def toposort(deps_dict: dict) -> list:
    sorted_list = []
    sorted_values = set()
    while len(deps_dict) > 0:
        unsorted = []
        for value, deps in deps_dict.items():
            if len(deps) == 0:
                sorted_list.append(value)
                sorted_values.add(value)
            else:
                unsorted.append(value)
        deps_dict = {value: deps_dict[value] - sorted_values for value in unsorted}
    return sorted_list
