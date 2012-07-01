import sys

import clang.cindex as clang

USAGE = "%s file.c"

def process_all_functions(tu, file_filter=None):
    for c in tu.cursor.get_children():
        if c.kind == clang.CursorKind.FUNCTION_DECL:
            f = c.location.file
            if file_filter and f.name != file_filter:
                continue
            print "Processing function %s in %s (%d:%d)" % \
                (c.spelling, f.name, c.location.line, c.location.column)
    
def main(argv):
    if len(argv) != 2:
        print USAGE % argv[0]
        return -1
        
    index = clang.Index.create()
    tu = index.parse(argv[1], args=["-D HAVE_EXIF"])
    print "Processing %s (%s)" % (argv[1], tu.spelling)
    
    process_all_functions(tu, argv[1])
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
