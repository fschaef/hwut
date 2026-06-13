"""Parser package. Importing it has NO side effects: grammar registration and
compilation happen lazily in rule_parser.compiled_grammar(), so this package can
be imported without forming the grammar -> Luau Role -> parser.core import cycle.
"""