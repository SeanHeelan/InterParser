import sys
import logging

import clang.cindex as clang

from interparser.ccargparse import load_project_data

USAGE = "%s compiler_wrapper_output"

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
