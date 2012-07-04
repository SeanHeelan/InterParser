#!/usr/bin/python

"""Drop-in replacement for clang. Logs the arguments passed to the compiler to
the file xxx_compiler_args.out. Set the CC and CXX to point at this script.

"""

__author__= "Sean Heelan"
__email__ = "sean.heelan@gmail.com"

import sys
import subprocess

O_FILE = "xxx_compiler_args.out"
CC = "clang"

with open(O_FILE, "ab") as fd:
    fd.write(" ".join(sys.argv[1:]) + "\n")
    l = [CC]
    l.extend(sys.argv[1:])
    r = subprocess.Popen(l)

sys.exit(r.wait())

