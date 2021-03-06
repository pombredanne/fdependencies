#!/usr/bin/env python

from __future__ import print_function
import argparse
import os
import re
import sys

# This file is released under terms of BSD license`
# See LICENSE.txt for more information

"""
generate_dep.py

Generate list of all dependencies for a starting fortran file.
"""

# information
__author__ = 'Valentin Clement'
__copyright__ = 'Copyright 2017, C2SM/MeteoSwiss'
__license__ = 'GPL'
__version__ = '0.1'
__date__ = 'Fri May 12 15:54:44 2017'
__email__ = 'valentin.clement@env.ethz.ch'


def add_fortran_file_to_parse(fortran_file, src_directory):
    if fortran_file not in processed_module_files:
        print(fortran_file.replace(src_directory, ''))
        processed_module_files.append(fortran_file)


# Gather all use information from the file
def gather_dependencies(fortran_input):
    input_file = open(os.path.join(fortran_input), 'r')
    modules = []
    try:
        for line in input_file:
            if use_p.match(line):
                modules.append(use_p.match(line).group(2).lower().rstrip())
        return list(set(modules))
    finally:
        input_file.close()


# Try to find the file containing the specified module
def find_module_file(module_name, module_map):
    if module_name in module_map:
        return module_map[module_name.lower()]
    return None


# Recursive call to process all dependencies
def find_all_dependencies(mods, module_map, src_directory, excluded):
    for mod in mods:
        mod_file = find_module_file(mod, module_map)
        if mod_file is not None and mod_file.replace(src_directory, '') not in excluded:
            if mod not in processed_modules:
                usages = gather_dependencies(mod_file)
                if mod in usages:
                    print('Warning: Module ' + mod + ' use itself!', file=sys.stderr)
                    usages.remove(mod)
                    # Remove module that are part of this file as well
                    for key_module_name in usages:
                        if key_module_name in module_map and module_map[key_module_name] == mod_file:
                            usages.remove(key_module_name)
                if len(usages) > 0:
                    find_all_dependencies(usages, module_map, src_directory, excluded)
                # Add module name as processed
                processed_modules.append(mod)

                add_fortran_file_to_parse(mod_file, src_directory)

                # Add file as processed
                for module_name in module_map:
                    if module_map[module_name] == mod_file and module_name != mod:
                        processed_modules.append(module_name)
        else:
            if mod in intrinsic_modules:
                intrinsic_usage[mod] = intrinsic_usage[mod] + 1
            else:
                print('Warning: no file found for module ' + mod.rstrip(), file=sys.stderr)


# Gather all fortran files in the source directory. For the moment only .f90 files
def find_all_fortran_files(is_recursive, src_directory):
    fortran_files = []
    if is_recursive:
        for root, dirs, files in os.walk(src_directory):
            for input_file in files:
                if input_file.endswith('.f90'):
                    fortran_files.append(root + '/' + input_file)
    else:
        for input_file in os.listdir(src_directory):
            if input_file.endswith(".f90"):
                fortran_files.append(os.path.join(src_directory, input_file))
    return fortran_files


# Map module name with their corresponding files
def find_all_modules(fortran_files):
    mapping = dict()
    mod_generic_regex = '^ *MODULE * ([a-zA-Z0-9_]+)'
    mod_generic_p = re.compile(mod_generic_regex, re.IGNORECASE)
    for f90 in fortran_files:
        fortran_file = open(f90, 'r')
        for line in fortran_file:
            if mod_generic_p.match(line):
                module_name = mod_generic_p.match(line).group(1).rstrip()
                if module_name.lower() != 'procedure':
                    mapping[module_name] = f90
    return mapping


# Arguments of the program
parser = argparse.ArgumentParser(description='FORTRAN dependency scanner.')
parser.add_argument('source', action='store', help='Directory containing the FORTRAN source files')
parser.add_argument('start', action='store', help='Start file for the scanning')
parser.add_argument('--recursive', dest='recursive', action='store_true', help='Recurse to child folders')
parser.add_argument('--exclude', dest='exclude_list', action='store',
                    help='List of file to be excluded seperated by a colon :')
parser.set_defaults(recursive=False)
parser.set_defaults(exclude_list='')
args = parser.parse_args()

# List of FORTRAN intrinsic modules
intrinsic_modules = ['iso_c_binding', 'iso_fortran_env', 'openacc', 'omp_lib', 'omp_lib_kinds', 'ieee_arithmetic']
fortran_ext = ['f90', 'F90', '.for', '.f', '.F', '.f95', '.f03']
intrinsic_usage = dict()
for intrinsic_module in intrinsic_modules:
    intrinsic_usage[intrinsic_module] = 0

# all excluded files
excluded_files = args.exclude_list.split(':')

# Regex to catch the module names in use statements
use_regex = '^ *USE *(, *INTRINSIC *::)? *([^,|^ |^!]*)'
use_p = re.compile(use_regex, re.IGNORECASE)

# Format the entry point
start_file = os.path.join(args.source, args.start)

# Find all the FORTRAN file in the search path
input_files = find_all_fortran_files(args.recursive, args.source)

# Process all module files once to extract their module
module_to_file = find_all_modules(input_files)

# Keep list of processed modules to avoid processing them more than once
processed_modules = []
processed_module_files = []
for excluded_fortran_file in excluded_files:
    processed_module_files.append(os.path.join(args.source, excluded_fortran_file))

# Start the dependency search from the given entry point (file containing the PROGRAM subroutine)
start_modules = gather_dependencies(start_file)
find_all_dependencies(start_modules, module_to_file, args.source, excluded_files)

# Print the entry point as the last file in the dependency list
add_fortran_file_to_parse(start_file, args.source)

# Check module that have not been processed to have all .xmod
for possible_module_name in module_to_file:
    module_file = module_to_file[possible_module_name].replace(args.source, '')
    if possible_module_name not in processed_modules and module_file not in excluded_files:
        start_modules = gather_dependencies(module_to_file[possible_module_name])
        if len(start_modules) > 0:
            find_all_dependencies(start_modules, module_to_file, args.source, excluded_files)
        else:
            add_fortran_file_to_parse(module_to_file[possible_module_name], args.source)
        processed_modules.append(module_to_file)
        for module_name in module_to_file:
            if module_to_file[module_name] == module_file and module_name != possible_module_name:
                processed_modules.append(module_name)
        add_fortran_file_to_parse(module_to_file[possible_module_name], args.source)


# Process rest of files that are not excluded
for input_file in input_files:
    if input_file not in processed_module_files and input_file.replace(args.source, '') not in excluded_files:
        add_fortran_file_to_parse(input_file, args.source)

# Print intrinsic module usage
for intrinsic_module in intrinsic_modules:
    if intrinsic_usage[intrinsic_module] > 0:
        print('Info: intrinsic module ' + intrinsic_module + ' used ' + str(intrinsic_usage[intrinsic_module])
              + ' times', file=sys.stderr)
