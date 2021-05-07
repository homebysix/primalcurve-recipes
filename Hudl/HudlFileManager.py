#!/usr/local/autopkg/python
#
# Copyright 2021 Glynn Lane (primalcurve)
#
# Based on Versioner Copyright 2010 Per Olofsson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Some code borrowed from pyasar:
# https://github.com/Photonios/pyasar
"""See docstring for AsarVersioner class"""

import glob
import json
import pathlib
import plistlib
import re
import shutil
import struct

from autopkglib import ProcessorError
from autopkglib.Unarchiver import Unarchiver

__all__ = ["AsarVersioner"]

UNKNOWN_VERSION = "UNKNOWN_VERSION"


class HudlFileManager(Unarchiver):
    # we dynamically set the docstring from the description (DRY), so:
    description = (
        """Makes sure downloaded file becomes a DMG if it is not one already."""
    )
    input_variables = {
        "pathname": {
            "required": True,
            "description": (
                "Path to downloaded file. File type is determined after the "
                "downloaded file is parsed and renamed."
            ),
        },
        "purge_destination": {
            "required": False,
            "description": (
                "Whether the contents of the destination directory "
                "will be removed before unpacking."
            ),
        },
        "destination_path": {
            "required": False,
            "description": (
                "Path to directory in which to extract archives."
            ),
        },
    }
    output_variables = {
        "dmg_path": {"description": "DMG to feed into AppDmgVersioner."}
    }

    __doc__ = description

    def main(self):
        """Return a path do a DMG  for file at pathname
        """
        # Handle some defaults for archive_path and destination_path
        pathname = self.env.get("archive_path", self.env.get("pathname"))
        if not pathname:
            raise ProcessorError(
                "Expected a 'pathname' input variable but none is set!"
            )

        # Convert to pathlib.Path for further processing
        pathname = pathlib.Path(self.env["pathname"])
        if not pathname.exists():
            raise ProcessorError(
                f"File from previous processor (pathname: {pathname}) does "
                f"not exist!"
            )

        destination_path = pathlib.Path(self.env.get(
            "destination_path",
            pathlib.Path(self.env["RECIPE_CACHE_DIR"], self.env["NAME"]),
        ))
        # Make the destination path
        destination_path.mkdir(parents=True, exist_ok=True)
        if self.env.get("purge_destination"):
            for file_path in destination_path.glob("*"):
                try:
                    if file_path.is_dir() and not file_path.is_symlink():
                        shutil.rmtree(path)
                    else:
                        file_path.unlink()
                except OSError as err:
                    raise ProcessorError(
                        f"Can't remove {file_path}: {err.strerror}"
                    )

        try:
            new_pathname = pathname.joinpath(
                pathname.parent, pathname.name.split("?")[0]
            )
            # Rename file to new_pathname:
            pathname.rename(new_pathname)
            # Handle dmgs
            if new_pathname.suffix == ".dmg":
                self.env["dmg_path"] = str(new_pathname)
            # Handle other formats
            else:
                file_fmt = self.get_archive_format(str(new_pathname))
                if not file_fmt:
                    raise ProcessorError(
                        "Can't guess archive format for filename "
                        f"'{new_pathname.name}'"
                    )
                self.output(
                    f"Guessed archive format '{file_fmt}' from filename "
                    f"'{new_pathname.name}'"
                )
                if file_fmt not in list(Unarchiver.EXTNS.keys()):
                    err_msg = ", ".join(list(Unarchiver.EXTNS.keys()))
                    raise ProcessorError(
                        f"'{file_fmt}' is not valid for the 'archive_format' "
                        f"variable. Must be one of {err_msg}."
                    )
                # Extract archived file
                self._extract(
                    file_fmt, str(new_pathname), str(destination_path)
                )
                self.output(
                    f"Unarchived '{new_pathname}' to '{destination_path}'"
                )
                # Find DMG at destination_path
                recipe_name = self.env["NAME"]
                file_regex = rf"{recipe_name}.*\.dmg"
                for file_path in destination_path.glob("*.dmg"):
                    if re.match(file_regex, file_path):
                        self.env["dmg_path"] = str(file_path)
                        break

            # Make sure we've found a DMG
            if not self.env.get("dmg_path"):
                raise ProcessorError(
                    "Unable to locate a DMG after processing!"
                )

            self.output(
                f"Found DMG {self.env['dmg_path']} in file {pathname}"
            )
        except ProcessorError:
            raise
        except Exception as ex:
            raise ProcessorError(ex)


if __name__ == "__main__":
    PROCESSOR = AsarVersioner()
    PROCESSOR.execute_shell()