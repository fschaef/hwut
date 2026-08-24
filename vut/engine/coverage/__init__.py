"""Coverage component. Importing it has NO side effects: the reader
registry is filled by the reader modules themselves, which are imported
where a tool is elected -- so this package can be imported without
pulling in any language's tooling.
"""
