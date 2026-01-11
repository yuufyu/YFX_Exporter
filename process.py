import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy

from yfx_exporter.exporter import ExportError, export


def run_export_process(context: bpy.types.Context) -> None:
    scn = context.scene
    # settings = scn.yfx_exporter_settings
    settings = load_export_settings(context)

    export_path = settings["export_path"]
    if not os.path.isabs(export_path):
        raise ExportError("The path must be absolute.")

    export(context, settings)


def start_foreground_export(context: bpy.types.Context) -> None:
    run_export_process(context)


def start_background_export(context: bpy.types.Context) -> None:
    """Function to start background export"""
    export_settings = context.scene.yfx_exporter_settings.export_settings
    abs_export_path = bpy.path.abspath(export_settings.export_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = str(Path(temp_dir) / "___yfx_exporter_temp___.blend")
        bpy.ops.wm.save_as_mainfile(filepath=temp_file, copy=True, check_existing=False)

        exec_script_path = __file__
        exec_script_dir = Path(exec_script_path).parent

        blender_args = [
            bpy.app.binary_path,
            "--factory-startup",
            "--addons",
            __package__.split(".")[0],
            "--background",
            temp_file,
            "--python",
            exec_script_path,
            "--",
            "--output",
            abs_export_path,
        ]
        with subprocess.Popen(
            blender_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="UTF-8",
            cwd=str(exec_script_dir),
        ) as proc:
            print(proc.stdout.read())

            # Check and raise ExportError if there is an error in stderr
            msg_stderr = proc.stderr.read()
            if msg_stderr:
                raise ExportError(msg_stderr)


def load_export_settings(context: bpy.types.Context) -> dict:
    scn = context.scene
    settings_file = scn.yfx_exporter_settings.export_settings_file
    if settings_file is None:
        raise ExportError("Not founded json file")

    json_string = settings_file.settings_file.as_string()

    try:
        settings = json.loads(json_string)
        return settings
    except json.JSONDecodeError as e:
        raise ExportError(str(e))


if __name__ == "__main__":
    """Entry point when the script is executed directly in sub process"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str)

    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    output = args.output

    context = bpy.context
    # settings = context.scene.yfx_exporter_settings
    # export_settings = settings.export_settings
    # export_settings.export_path = output
    run_export_process(context)
