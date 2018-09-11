# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import os
import pathlib
from textx.metamodel import metamodel_from_file


pathling_model_file = pathlib.Path(
    pathlib.PurePath(pathlib.Path(__file__).parents[0], "pathling.tx")
)
pathling_metamodel = metamodel_from_file(pathling_model_file)
passed = 0
failed = 0

with open("pathling_spec.txt", "r") as f:
    for line in f.read().split("\n"):
        if not line.startswith("#") and line:
            try:
                path = pathling_metamodel.model_from_str(line)
                print("PASSED:{}\n".format(line))
                passed += 1
            except Exception as ex:
                print("FAILED:\n{}\n{}\n".format(line, ex))
                failed += 1

print("passed: {}\nfailed: {}".format(passed, failed))
