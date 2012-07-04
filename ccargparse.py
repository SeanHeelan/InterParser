"""This is a container module for functions related to parsing the output of
the compiler wrapper. The load_project_data function provides the interface.

"""

__author__= "Sean Heelan"
__email__ = "sean.heelan@gmail.com"

import os
import logging

class CompileArgsError(Exception):
    pass

def load_project_data(data_file):
    """Load the output of the compiler wrapper and put it in a dictionary mapping
    source file paths to the arguments passed to the compiler when processing
    that file.

    @type data_file: String
    @param data_file: The output of our compiler wrapper. Each line contains
        the arguments passed to a single instantiation of the compiler.

    @rtype: Dictionary
    @returns: A mapping from path-to-source-file to a list of strings where
        each element is an argument that was passed to the compiler during
        the compilation of the associated file.

    """

    try:
        fd = open(data_file)
    except Exception, e:
        log = logging.getLogger("load_project_data")
        log.exception("Could not open %s")
        log.exception("%s" % str(e))
        raise

    ret = {}
    with fd:
        [__update_results(ret, __process_data_line(line)) for line in fd]

    return ret

def __process_data_line(line):
    """Parse the arguments provided to one invocation of the compiler

    @type line: String
    @param line: A single line from the file logged by the compiler wrapper

    @rtype: List of Tuple of (String, Set of Strings)
    @return: A list in which each element is a tuple containing a source file
        name and the corresponding set of compiler options

    """

    log = logging.getLogger("process_data_line")
    line = line.split(" ")
    skip_next = False
    source_files = set()
    args = set()

    for arg in line:
        # On a -o arg we want to skip the filename that comes next
        if skip_next:
            skip_next = False
            continue

        if arg.endswith(".c") or arg.endswith(".cpp"):
            path = os.path.abspath(arg)
            if not os.path.exists(path):
                log.error("Found a reference to %s but it does not exist" % \
                          path)
                continue
            source_files.add(arg)
            continue
        elif arg == "-c" or arg == "-emit-ast" or arg == "-fsyntax-only":
            # These would just be ignored by clang_parseTranslationUnit anyway
            continue
        elif arg == "-o":
            skip_next = True
            continue
        else:
            args.add(arg)
            continue

    ret = []
    for f_name in source_files:
        ret.append((f_name, args))

    return ret

def __update_results(res, info):
    """Update the res dictionary with the source file to compiler argument
    mappings in 'info'

    @type res: Dict
    @param res: The result dictionary to update

    @type info: List of Tuple of (String, Set of Strings)
    @param info: The new data to insert

    @rtype: None

    """

    log = logging.getLogger("update_results")
    for source_file, args in info:
        if source_file in res:
            prev_args = set(res[source_file])
            if prev_args == set(args):
                continue
            else:
                log = logging.getLogger("update_results")
                log.error("%s was found before with different args")
                log.error("%s != %s" % (str(prev_args), str(args)))
                raise CompileArgsError()

        log.debug("Compile args found for %s" % source_file)
        res[source_file] = args
