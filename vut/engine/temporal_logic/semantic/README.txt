===============================================================================
SEMANTIC UNIT  --  ParsedModule -> DeclaredModule -> SemanticModule
===============================================================================

OPERATION:

      ParsedModule (ast)
            |
            | declare         no peek. publish declaration surface.
            |
      DeclaredModule (ast + declaration surface)
            |
            | elaborate       peeks other modules' declaration surfaces.
            |
      SemanticModule (mutated ast + symbol table)

Two transitions. One module's ast in, one module's SemanticModule out.
References are KNOWN, not implemented. link implements them.

                    SemanticModule
                          |
                          |  is-a
                          |
                   DeclaredModule


DeclaredModule:
    export_db      # name / scope / kind database

A declared module is a parsed module that still has references without any
hint of how to access them. It, however announces the types that it declares
to implement.

SemanticModule(DeclaredModule):
    decorated_ast  # ast with '=> name' nodes replaced (topology preserved)
    symbol_table   # references as Access (each with recipe), ModuleRefs

A SemanticModule is the next step, where in consideration of related (imported)
DeclaredModule-s, recipies are developed (access definitions) are specified
such that for each reference a way is known of how the reference can be
implemented (but actually is not yet implemented).

-------------------------------------------------------------------------------
SEAM
-------------------------------------------------------------------------------

  parser  --------->  [ SEMANTIC UNIT ]  ---------------------->  link
             ast                              SemanticModule

SemanticModule is the disk boundary. It serialises out, loads back in. A
pre-built module on disk is consulted for its declaration surface during
another module's elaborate. A library acts as a set of SemanticModules.

-------------------------------------------------------------------------------
declare  --  ast -> declaration surface
-------------------------------------------------------------------------------

Walk the ast. Collect every declared name with its kind and scope. Emit the
DECLARATION SURFACE: the module's public half.

  DECLARATION SURFACE   name -> (kind, scope).  Export names only.
                        References are not touched.

Declaration-first ordering: every module declares before any module elaborates.
The surface is what another module peeks during its own elaborate. The peeked
module may be a bare DeclaredModule or a fully elaborated SemanticModule; both
present the same surface.

-------------------------------------------------------------------------------
elaborate  --  ast + foreign surfaces -> mutated ast + symbol table
-------------------------------------------------------------------------------

Walk the ast once. Read this module's ast and the declaration surfaces of the
modules it imports. Mutate the ast and build the SYMBOL TABLE.

  AST MUTATION  Where concrete AST nodes require knowledge provided by a DeclaredModule,
                the according AST node is replaced/mounted in place without affacting 
                the remaining identities or topologies of the AST. That is, the
                new node must be derived from the original parser's AST node.

  SYMBOL TABLE  declared names + scopes.
                Each reference -> an Access:  (name, ModuleRef).
                Each import    -> a ModuleRef: which module, which mount.
                ModuleRef shared by many Access.
                Each Access carries its RECIPE: how the name is reached
                (local scope, or through the ModuleRef's mount, by descent).

