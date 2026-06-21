===============================================================================
SEMANTIC UNIT  --  ParsedModule -> DeclaredModule -> SemanticModule
===============================================================================

OPERATION:

      ParsedModule (ast)
            |
            | declare         no peek. publish export_db.
            |
      DeclaredModule (ast + export_db)
            |
            | elaborate       peeks other modules' export_db.
            |
      SemanticModule (mutated ast + symbol table)

Two transitions. One module's ast in, one module's SemanticModule out.
References are KNOWN, not implemented. link (the next unit) implements them.

                    SemanticModule
                          |
                          |  is-a
                          |
                   DeclaredModule


DeclaredModule:
    export_db      # name / scope / kind database

A DeclaredModule carries references not yet given an access recipe. Its
export_db announces the kinds it declares.

SemanticModule(DeclaredModule):
    decorated_ast  # ast with '=> name' nodes replaced (topology preserved)
    symbol_table   # references as Access (each with recipe), ModuleRefs

A SemanticModule reads the export_db of related (imported) DeclaredModules.
For each reference, elaborate writes a recipe: the known way to reach it. The
recipe defines the access; it does not implement it.

-------------------------------------------------------------------------------
SEAM
-------------------------------------------------------------------------------

  parser  --------->  [ SEMANTIC UNIT ]  ---------------------->  link
             ast                              SemanticModule

SemanticModule is the disk boundary. It serialises out, loads back in. A
pre-built module on disk is consulted for its export_db during another
module's elaborate. A library acts as a set of SemanticModules.

-------------------------------------------------------------------------------
declare  --  ast -> export_db
-------------------------------------------------------------------------------

Walk the ast. Collect every declared name with its kind and scope. Emit the
export_db: the module's public half.

  export_db   name -> (kind, scope).  Export names only.
              References are not touched.

Declaration-first ordering: every module declares before any module elaborates.
The export_db is what another module peeks during its own elaborate. The peeked
module may be a bare DeclaredModule or a fully elaborated SemanticModule; both
present the same export_db.

-------------------------------------------------------------------------------
elaborate  --  ast + foreign export_dbs -> mutated ast + symbol table
-------------------------------------------------------------------------------

Walk the ast once. Read this module's ast and the export_dbs of the modules it
imports. Mutate the ast and build the SYMBOL TABLE.

  AST MUTATION  Where an AST node requires a kind held in a DeclaredModule's
                export_db, the node is replaced/mounted in place. The kind
                found in the export_db selects the replacement. The new node
                derives from the parser's node and grafts its branches
                unchanged. Other node identities and the topology stay intact.

  SYMBOL TABLE  declared names + scopes.
                Each reference -> an Access:  (name, ModuleRef).
                Each import    -> a ModuleRef: which module, which mount.
                ModuleRef shared by many Access.
                Each Access carries its RECIPE: how the name is reached
                (local scope, or through the ModuleRef's mount, by descent).
