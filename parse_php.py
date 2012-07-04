"""
Relies on https://raw.github.com/indygreg/clang/python_features/bindings/
python/clang/cindex.py
"""

import sys
import logging

from Queue import Queue

import clang.cindex as clang

from interparser.ccargparse import load_project_data

USAGE = "%s compiler_wrapper_output"
ZEND_FUNC = "zend_parse_parameters"

class FunctionProcessingError(Exception):
    pass

def get_child(node, idx):
    """
    Return child number 'idx' of the AST cursor 'node'

    @type node: clang.cindex.Cursor
    @param node: The node to process

    @type idx: Integer
    @param idx: The index of the child to return

    @rtype: clang.cinde.Cursor
    """

    return list(node.get_children())[idx]

def extract_fmt_str(func_call_nodes):
    """
    Extact the format string from a call to ZEND_FUNC

    @type func_call_nodes: List of clang.cindex.Cursor
    @param func_call_nodes: A list of the AST nodes for the function call

    @rtype: String
    @return: The format string parameter to the call
    """

    # The format string is the child of an UNEXPOSED_EXPR
    tmp = get_child(func_call_nodes[2], 0)
    tk_container = get_child(tmp, 0)

    if tk_container.kind != clang.CursorKind.STRING_LITERAL:
        msg = "Incorrect argument type: %s" % tk_container.kind
        log.error(msg)
        raise FunctionProcessingError(msg)

    tokens = list(tk_container.get_tokens())
    # Strip the quotation marks as we get the string literal
    fmt_str = tokens[0].spelling[1:-1]

    return fmt_str

def process_function(func_cursor):
    """
    Search the function indicated by 'func_cursor' for the first call to
    zend_parse_parameters. If such a call is found then we return the
    format string used.

    @type func_cursor: clang.cindex.Cursor
    @param func_cursor: A cursor object for the function to prcoess

    @rtype: String
    @return: The format string argument to the first call to
        zend_parse_parameters within the given function
    """

    log = logging.getLogger("process_function")

    to_process = Queue()
    fmt_strs = set()
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
                fmt_strs.add(extract_fmt_str(unexposed_exprs))
                break

        for c in n.get_children():
            to_process.put(c)

    if len(fmt_strs) > 1:
        loc = func_cursor.location
        msg = ("The function %s in %s (%d:%d) contains calls to " + \
               "%s with different format strings") % \
            (func_cursor.spelling, ZEND_FUNC, loc.file.name, loc.line,
             loc.column)
        log.error(msg)
        raise FunctionProcessingError(msg)
    elif len(fmt_strs) > 0:
        return fmt_strs.pop()
    else:
        return None

def process_all_functions(tu, file_filter=None):
    """
    @type tu: clang.cindex.TranslationUnit
    @param tu: The top level translation unit for a file

    @type file_filter: String
    @param file_filter: When processing the children of a given
        translation unit we may encounter nodes that are from
        included files. This parameter specifies a file name to
        which we will restrict our processing. If it is None then
        we will process all children of the translation unit.
    """

    log = logging.getLogger("process_all_functions")

    for c in tu.cursor.get_children():
        if c.kind == clang.CursorKind.FUNCTION_DECL:
            f = c.location.file
            if file_filter and f.name != file_filter:
                continue
            log.debug("Processing function %s in %s (%d:%d)" % \
                (c.spelling, f.name, c.location.line, c.location.column))

            # Check if the function contains a call to zend_parse_parameters
            fmt_str = process_function(c)
            if fmt_str is None:
                log.debug("%s does not call %s" % (c.spelling, ZEND_FUNC))
                continue
            else:
                log.info("%s calls %s with the format string %s" % \
                         (c.spelling, ZEND_FUNC, fmt_str))

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
    logging.basicConfig(level=logging.INFO)
    sys.exit(main(sys.argv))
