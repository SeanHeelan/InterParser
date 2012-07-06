InterParser
===========

A collection of scripts based on libclang for extracting API information from interpreters

Relies on :
https://raw.github.com/indygreg/clang/python_features/bindings/python/clang/cindex.py
https://raw.github.com/indygreg/clang/python_features/bindings/python/clang/enumerations.py

However, the above cindex.py contains a bug when get_tokens is called on an AST
node that refers to an empty string literal. For now, you should use the copy
of the above files, with this bug fixed, provided in the libclang_bindings
folder

