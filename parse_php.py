"""Process all files that are part of a PHP build and extract the format
string parameter passed to any calls to zend_parse_parameters. The results
are output in a file mapping the names of such functions to the format string.

Relies on :
https://raw.github.com/indygreg/clang/python_features/bindings/python/
clang/cindex.py
https://raw.github.com/indygreg/clang/python_features/bindings/python/
clang/enumerations.py

However, the above cindex.py contains a bug when get_tokens is called on an
AST node that refers to an empty string literal. For now, you should use the
copy of the above files, with this bug fixed, provided in the
libclang_bindings folder

"""

__author__= "Sean Heelan"
__email__ = "sean.heelan@gmail.com"

import sys
import logging
import argparse

from Queue import Queue

import clang.cindex as clang

from interparser.ccargparse import load_project_data

ZEND_FUNC = "zend_parse_parameters"
DESC = "Format string extractor for %s" % ZEND_FUNC

# Counter for the number of calls to ZEND_FUNC detected that use a
# variable rather than a string literal as their argument
VAR_ARG_COUNT = 0

class FunctionProcessingError(Exception):
    pass

class VariableArgumentError(Exception):
    pass

def get_child(node, idx):
    """Return child number 'idx' of the AST cursor 'node'

    @type node: clang.cindex.Cursor
    @param node: The node to process

    @type idx: Integer
    @param idx: The index of the child to return

    @rtype: clang.cinde.Cursor

    """

    return list(node.get_children())[idx]

def extract_fmt_str(func_call_nodes):
    """Extact the format string from a call to ZEND_FUNC

    @type func_call_nodes: List of clang.cindex.Cursor
    @param func_call_nodes: A list of the AST nodes for the function call

    @rtype: String
    @return: The format string parameter to the call

    """

    # The format string is the child of an UNEXPOSED_EXPR introduced due to
    # an rvalue-to-lvalue conversion
    unex_expr = get_child(func_call_nodes[2], 0)
    tkn_container = get_child(unex_expr, 0)

    if tkn_container.kind != clang.CursorKind.STRING_LITERAL:
        raise VariableArgumentError()

    tokens = list(tkn_container.get_tokens())
    if tokens[0] is None:
        return ""

    # Strip the quotation marks as we get the string literal
    fmt_str = tokens[0].spelling[1:-1]

    return fmt_str

def process_function(func_cursor):
    """Search the function indicated by 'func_cursor' for the all calls to
    zend_parse_parameters. Return all format strings used by such invocations.

    @type func_cursor: clang.cindex.Cursor
    @param func_cursor: A cursor object for the function to prcoess

    @rtype: List of Strings
    @return: A list of all unique format strings used as arguments to
        ZEND_FUNC within the specified function

    """

    log = logging.getLogger("process_function")

    fmt_strs = set()
    to_process = Queue()
    to_process.put(func_cursor)

    while not to_process.empty():
        n = to_process.get()

        if n.kind == clang.CursorKind.CALL_EXPR:
            # The first child will be the function name, the rest will
            # represent the arguments to the function. Each child will
            # be of the kind UNEXPOSED_EXPR due to the function-to-pointer
            # decay on the function and rvalue-to-lvalue conversion on
            # the arguments. Each will have a single child of kind
            # DECL_REF_EXPR from which we can retrieve details such as
            # the variable name.
            unexposed_exprs = list(n.get_children())
            func_name_node = get_child(unexposed_exprs[0], 0)
            if func_name_node.displayname == ZEND_FUNC:
                try:
                    fmt_str = extract_fmt_str(unexposed_exprs)
                except VariableArgumentError:
                    # A negligible number of calls to ZEND_FUNC pass the
                    # format string using a variable.
                    global VAR_ARG_COUNT
                    VAR_ARG_COUNT += 1
                else:
                    # Some calls to ZEND_FUNC have an empty format string
                    if len(fmt_str):
                        fmt_strs.add(fmt_str)
                # Regardless of our success/failure at retrieving the
                # format string arg we 1) Don't explore the children
                # of the CALL node and 2) Do explore the rest of the
                # function in case there are multiple calls to ZEND_FUNC
                # with different arguments (e.g. the levenshtein function).
                continue

        for c in n.get_children():
            to_process.put(c)

    if len(fmt_strs):
        return list(fmt_strs)
    else:
        return None

def process_all_functions(tu, file_filter=None, globals_only=False):
    """Iterate over the translation unit tu, searching for functions that call
    ZEND_FUNC. When a call is found the format string used is extracted. A
    map of each calling function to the format strings used in all calls to
    ZEND_FUNC is returned.

    @type tu: clang.cindex.TranslationUnit
    @param tu: The top level translation unit for a file

    @type file_filter: String
    @param file_filter: When processing the children of a given
        translation unit we may encounter nodes that are from
        included files. This parameter specifies a file name to
        which we will restrict our processing. If it is None then
        we will process all children of the translation unit.

    @rtype: Dict

    """

    log = logging.getLogger("process_all_functions")
    res = {}

    for c in tu.cursor.get_children():
        if c.kind == clang.CursorKind.FUNCTION_DECL:
            f = c.location.file
            if file_filter and f.name != file_filter:
                continue

            if globals_only and not c.spelling.startswith("zif_"):
                # Exclude functions that are not defined using the
                # PHP_FUNCTION macro
                continue

            log.debug("Processing function %s in %s (%d:%d)" % \
                (c.spelling, f.name, c.location.line, c.location.column))

            # Check if the function contains a call to zend_parse_parameters
            fmt_strs = process_function(c)
            if fmt_strs is None:
                log.debug("%s does not call %s" % (c.spelling, ZEND_FUNC))
                continue
            else:
                tmp = ", ".join(fmt_strs)
                log.debug("%s calls %s with the format string(s) %s" % \
                         (c.spelling, ZEND_FUNC, tmp))
                res[c.spelling] = fmt_strs
    return res

def write_output(src_file, data, out_file):
    """Log the function/format string mappings extracted from 'src_file'

    @type src_file: String
    @param src_file: The C/C++ source file from which the data was extracted

    @type data: Dict
    @param data: A mapping of function names to format strings used within
        those functions as parameters to ZEND_FUNC

    @type out_file: String
    @param out_file: The log file to which the data will be appended

    @rtype: None

    """

    with open(out_file, "ab") as fd:
        fd.write("# %s\n" % src_file)
        for func_name, fmt_strs in data.items():
            fd.write("%s %s\n" % (func_name, " ".join(fmt_strs)))

def main(cc_file, output_file, single_file=None, globals_only=False):
    log = logging.getLogger("main")

    log.info("Loading compiler args from %s" % cc_file)
    comp_args = load_project_data(cc_file)
    log.info("Found compiler args for %d source files" % len(comp_args))

    file_count = func_count = 0

    if single_file:
        if single_file not in comp_args:
            log.error("The file %s is not in the compiler arg log" % \
                      single_file)
            return -1

        args = comp_args[single_file]

        log.info("Processing %s" % single_file)
        log.debug("Compiler args: %s" % " ".join(list(args)))

        index = clang.Index.create()
        tu = index.parse(single_file, args)
        tu_data = process_all_functions(tu, single_file, globals_only)
        log.info("Found %d functions in %s that call %s" % \
                 (len(tu_data), single_file, ZEND_FUNC))
        if len(tu_data):
            file_count += 1
            func_count += len(tu_data)
            write_output(single_file, tu_data, output_file)
    else:
        log.info("Processing all source files ...")

        for src_file, args in comp_args.items():
            log.info("Processing %s" % src_file)
            log.debug("Compiler args: %s" % " ".join(list(args)))

            index = clang.Index.create()
            tu = index.parse(src_file, args)
            tu_data = process_all_functions(tu, src_file, globals_only)
            log.info("Found %d functions in %s that call %s" % \
                     (len(tu_data), src_file, ZEND_FUNC))
            if len(tu_data):
                file_count += 1
                func_count += len(tu_data)
                write_output(src_file, tu_data, output_file)

    log.info("API info for %d functions in %d files written to %s" % \
             (func_count, file_count, output_file))
    log.info("%d calls to %s with variable parameters" % \
             (VAR_ARG_COUNT, ZEND_FUNC))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description=DESC)
    parser.add_argument("-c", dest="cc_log", required=True,
                      help="The file created by the compiler wrapper")
    parser.add_argument("-o", dest="output_file", required=True,
                      help="The name of the output file")
    parser.add_argument("-s", dest="single_file", default=None,
                      help="Specify a single source file to process")
    parser.add_argument("--globals_only", dest="globals_only",
                        action="store_true", default=False,
                        help="If specified then we exclude class methods " + \
                        "from the results")
    args = parser.parse_args()

    cc_log = args.cc_log
    output_file = args.output_file
    single_file = args.single_file
    globals_only = args.globals_only

    sys.exit(main(cc_log, output_file, single_file, globals_only))
