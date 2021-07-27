#!/usr/local/autopkg/python
#
# Copyright 2021 Glynn Lane (primalcurve)
#
# Based on Unarchiver Copyright 2010 Per Olofsson
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
"""See docstring for PackageInfoReader class"""

import pathlib
import xml.etree.ElementTree as ET

from autopkglib import Processor, ProcessorError

__all__ = ["PackageInfoReader"]

UNKNOWN_VERSION = "UNKNOWN_VERSION"


class PackageInfoReader(Processor):
    # we dynamically set the docstring from the description (DRY), so:
    description = (
        """Tries to get requested info from a PackageInfo file"""
    )
    input_variables = {
        "pkg_info_path": {
            "required": True,
            "description": (
                "Path to PackageInfo file."
            ),
        },
        "target_key": {
            "required": True,
            "description": (
                "Which key to search the PackageInfo file for"
            ),
        },
    }
    output_variables = {
        "target_value": {"description": "Results from the key search."}
    }

    __doc__ = description

    def recursive_element_search(self, xml_element, target_key):
        """Searches through all elements of an XML node looking for a key."""
        for child_element in xml_element:
            target_value = xml_element.get(target_key)
            # If we've found what we're looking for, return it.
            if target_value:
                return target_value
            # Check the tag for the key
            if child_element.tag == target_key:
                target_value = child_element.text.strip()
                if target_value:
                    return target_value
            # Otherwise, continue recursion
            return self.recursive_element_search(child_element, target_key)


    def main(self):
        """Return a path do a DMG  for file at pkg_info_path
        """
        # Handle some defaults for archive_path and destination_path
        pkg_info_path = self.env.get("pkg_info_path")
        if not pkg_info_path:
            raise ProcessorError(
                "Expected a 'pkg_info_path' input variable but none is set!"
            )

        target_key = self.env.get("target_key")
        if not target_key:
            raise ProcessorError(
                "Expected a 'target_key' input variable but none is set!"
            )

        # Convert to pathlib.Path for further processing
        pkg_info_path = pathlib.Path(self.env["pkg_info_path"])
        if not pkg_info_path.exists():
            raise ProcessorError(
                f"File from previous processor (pkg_info_path: "
                f"{pkg_info_path}) does not exist!"
            )

        try:
            # Open file and read its contents
            with open(pkg_info_path, "rb") as fp:
                package_info = ET.fromstring(fp.read())

            # Attempt to find the target key in the `pkg-info` root object
            target_value = package_info.get(target_key)
            if target_value:
                self.env["target_value"] = target_value
            if package_info.tag == target_key:
                target_valuechild_element.text.strip()
                if target_value:
                    self.env["target_value"] = target_value
            # If it cannot be found at the root level, recursively check all
            # children
            else:
                target_value = self.recursive_element_search(
                    package_info, target_key
                )

            # Make sure we've found a value
            if not target_value:
                raise ProcessorError(
                    f"Unable to locate a matching value for {target_key}!"
                )

            self.output(
                f"Found value {self.env['target_value']} "
                f"in file {pkg_info_path}"
            )
        except ProcessorError:
            raise
        except Exception as ex:
            raise ProcessorError(ex)


if __name__ == "__main__":
    PROCESSOR = PackageInfoReader()
    PROCESSOR.execute_shell()
