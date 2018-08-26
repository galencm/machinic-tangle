# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

import pathlib
import os
import shutil
import argparse
import fnmatch
import uuid
import subprocess
from lxml import etree

# code generation approaches derived from earlier machinic
# approaches, see ma and the concept of projectional systems

def scaffold_thing(thing_name, thing_type, model_type):
    # create an initial directory to hold whatever is generated
    cwd = os.path.join(os.getcwd(), "{}_{}".format(thing_type, thing_name))
    if not os.path.isdir(cwd):
        os.mkdir(cwd)

    model_file = "model_{}.xml".format(thing_type)
    # update model xml with thing name
    model_xml = etree.parse(str(pathlib.PurePath(module_path(), model_file)))
    for peripheral in model_xml.xpath('//peripheral'):
        peripheral.set("name", thing_name)
        for output in peripheral.xpath('.//output'):
            # prefer publish nodes?
            output.set("channel", "/{}".format(thing_name))
            # value setting is a default for testing button
            # will have to take into account things such as 
            # sensors that might send varying values
            output.set("value", "1".format(thing_name))

    model_xml.write(str(pathlib.PurePath(cwd, model_file)), pretty_print=True)
    # use pattern to match various prefixes: iot, gui, cli, ...
    template_pattern = "*_{}_{}.gsl".format(model_type, thing_type)
    template_file = None
    for file in pathlib.Path(module_path()).iterdir():
        if fnmatch.fnmatch(file, template_pattern):
            template_file = pathlib.Path(file).name
            print("found template: {}".format(template_file))
            break

    if template_file:
        shutil.copy(pathlib.PurePath(module_path(), template_file), cwd)
        # run gsl to generate code / create directories
        subprocess.call(["gsl","-script:{}".format(template_file), model_file], cwd=cwd)
        subprocess.call(["chmod", "+x", "regenerate.sh"], cwd=cwd)
        subprocess.call(["./regenerate.sh"], cwd=cwd)
    else:
        print("no template file found for: {}".format(template_pattern))

def module_path():
    return pathlib.PurePath(pathlib.Path(__file__).parents[0])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("thing_type", help="type of thing")
    parser.add_argument("--model-type", default="homie", help="model to use")
    parser.add_argument("--name", default=None, help="thing name (default is a uuid)")

    args = parser.parse_args()

    if not args.name:
        args.name = str(uuid.uuid4())

    args = vars(args)
    scaffold_thing(args["name"], args["thing_type"], args["model_type"])
