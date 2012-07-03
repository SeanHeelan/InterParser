import sys
import os
import logging

import clang.cindex as clang

USAGE = "%s compiler_wrapper_output"

class CompileArgsError(Exception):
    pass

def process_data_line(line):
    """
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

def update_results(res, info):
    """
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

def load_project_data(data_file):
    """
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
        [update_results(ret, process_data_line(line)) for line in fd]

    return ret

def process_all_functions(tu, file_filter=None):
    log = logging.getLogger("process_all_functions")

    for c in tu.cursor.get_children():
        if c.kind == clang.CursorKind.FUNCTION_DECL:
            f = c.location.file
            if file_filter and f.name != file_filter:
                continue
            log.debug("Processing function %s in %s (%d:%d)" % \
                (c.spelling, f.name, c.location.line, c.location.column))

def main(argv):
    log = logging.getLogger("main")

    if len(argv) < 2:
        log.error(USAGE % argv[0])
        return -1

    log.info("Loading compiler args from %s" % argv[1])
    comp_args = load_project_data(argv[1])
    log.info("Found compiler args for %d source files" % len(comp_args))

    if len(argv) == 3:
        src_file = sys.argv[2]
        args = comp_args[src_file]

        log.info("Processing %s" % src_file)
        log.debug("Compiler args: %s" % " ".join(list(args)))

        index = clang.Index.create()
        tu = index.parse(src_file, args)
        process_all_functions(tu, src_file)
        return
    else:
        log.info("Processing all source files ...")

        for src_file, args in comp_args.items():
            log.info("Processing %s" % src_file)
            log.debug("Compiler args: %s" % " ".join(list(args)))

            index = clang.Index.create()
            tu = index.parse(src_file, args)
            process_all_functions(tu, src_file)
        return

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    sys.exit(main(sys.argv))
