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
import os.path
import plistlib
import struct

from autopkglib import ProcessorError
from autopkglib.Versioner import Versioner

__all__ = ["AsarVersioner"]

UNKNOWN_VERSION = "UNKNOWN_VERSION"


class AsarVersioner(Versioner):
    # we dynamically set the docstring from the description (DRY), so:
    description = (
        """Returns version information from an asar file"""
    )
    input_variables = {
        "input_asar_path": {
            "required": True,
            "description": (
                "Relative path within the app bundle containing the app "
                "version (i.e. 'Contents/Resources/app.asar') Can point to "
                "a path inside a .dmg which will be mounted."
            ),
        },
        "package_json": {
            "required": True,
            "description": (
                "Name of the file embedded within the asar file containing "
                "the version (i.e. 'package.json')"
            ),
        },
        "version_key": {
            "required": False,
            "default": "version",
            "description": (
                "The key containing the version string in %package_json%. "
                "If not present, defaults to 'version'"
            ),
        },
        "skip_single_root_dir": {
            "required": False,
            "default": False,
            "description": (
                "If this flag is set, `input_asar_path` points inside "
                "a zip file, and there is a single directory inside the "
                "zip file at the root of the archive, then interpret the "
                "path in the archive as being relative to that directory. "
                "Example:"
                """
          input_asar_path=/tmp/some/archive.zip/path/to/app.asar
          archive.zip
            archive-abcdef/
              path/to/app.asar\n"""
                "        Will use `archive-abcdef/path/to/app.asar` "
                "as the final path. If there is more than one file or "
                "directory at the root, the Processor will fail."
            ),
        }
    }
    output_variables = {
        "version": {"description": "Version of the app."}
    }

    __doc__ = description

    def _asar_opener(self, path):
        """Open the asar file and read its contents.
        Args:
            filename (str):
                Path to the *.asar file to open for reading.
        Returns (str):
            Version extracted from asar file
        """
        try:
            asar_file = open(path, 'rb')
        except Exception as error:
            raise ProcessorError(f"Can't read {path}: {error}")

        # uses google's pickle format, which prefixes each field
        # with its total length, the first field is a 32-bit unsigned
        # integer, thus 4 bytes, we know that, so we skip it
        asar_file.seek(4)

        header_size = struct.unpack('I', asar_file.read(4))
        if len(header_size) <= 0:
            raise ProcessorError(
                f"Can't determine header size of {path}: {error}"
            )

        # substract 8 bytes from the header size, again because google's
        # pickle format uses some padding here
        header_size = header_size[0] - 8

        # read the actual header, which is a json string, again skip 8
        # bytes because of pickle padding
        asar_file.seek(asar_file.tell() + 8)
        header = asar_file.read(header_size).decode('utf-8')

        json_header = json.loads(header)
        base_offset = asar_file.tell()
        return asar_file, json_header, base_offset

    def _extract_package_json(self, asar_file, json_header, base_offset):
        """Find package.json inside of asar and return it as a dict
        Args:
            None
        Returns (dict):
            Dictionary extracted from embedded package.json
        """
        # Get information about the embedded package.json file
        try:
            package_json = json_header["files"][self.env["package_json"]]
        except Exception as error:
            raise ProcessorError(f"Can't find package JSON: {error}")
        # Get the actual offset for the start of the file
        # (have to add the base offset)
        absolute_offset = int(package_json.get("offset")) + base_offset
        # Seek the open file to the offset
        asar_file.seek(absolute_offset)
        # Read up to the end of the file and return as a dict.
        return json.loads(asar_file.read(package_json.get("size")))

    def get_asar_info(self, asar_path):
        """Get version string from asar file inside a bundle.
        Args:
            asar_path (str):
                Path to the *.asar file to open for reading.
        Returns (str):
            Version extracted from asar file
        """
        # Open the asar file and get some information about its embedded
        # contents.
        asar_file, json_header, base_offset = self._asar_opener(asar_path)
        try:
            return self._extract_package_json(
                asar_file, json_header, base_offset
            )
        except Exception as error:
            raise ProcessorError(f"Can't extract package info: {error}")
        finally:
            # Close the asar file
            asar_file.close()

    def main(self):
        """Return a version for file at input_asar_path
        """
        input_asar_path: str = self.env["input_asar_path"]
        skip_single_root_dir: bool = self.env["skip_single_root_dir"]
        version_key: str = self.env["version_key"]

        try:
            asar_dict = self._read_auto_detect(
                input_asar_path, skip_single_root_dir, self.get_asar_info
            )
            if asar_dict is None:
                raise ProcessorError(
                    f"File '{input_asar_path}' was not found."
                )
            self.env["version"] = asar_dict.get(version_key, UNKNOWN_VERSION)
            self.output(
                f"Found version {self.env['version']} "
                f"in file {input_asar_path}"
            )
        except ProcessorError:
            raise
        except Exception as ex:
            raise ProcessorError(ex)


if __name__ == "__main__":
    PROCESSOR = AsarVersioner()
    PROCESSOR.execute_shell()
