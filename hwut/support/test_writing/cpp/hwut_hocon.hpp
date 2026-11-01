// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: PARSE THE HOCON SUBSET OF THE SPECIFICATION LANGUAGE INTO THE
//          ANNOTATED TREE -- the port of 'python/hwut_hocon.py', a thin face
//          over '../c/hwut_hocon.c': every key, every value and every block
//          carries its file-relative position.
//
//     std::vector<hwut::hocon::SourceLine> lines = { { "a = 1", 1, 0 }, { "b = \"x\"", 2, 0 } };
//     auto [document, faults] = hwut::hocon::parse(lines, "f.hocon");
//     document.get("a")->node.as_int();             -- 1
//     for(const auto& f : faults) std::puts(f.to_string().c_str());
//
// THE SUBSET, word for word Python's ('../python/README-hwut_hocon.txt'):
// nested objects, lists, numbers in every radix, booleans, the spellings of
// nothing, '#' and '//' comments, double-quoted and triple-quoted strings;
// 'include', '${...}' and '+=' refused by name. The parser accumulates
// faults and recovers at the next line; it never throws for a text.
//
// A Node is a VIEW into the parsed tree; every Node and Entry of one parse
// shares the tree's ownership, so each may outlive the document it came from.
// _____________________________________________________________________________
#ifndef HWUT_HOCON_HPP
#define HWUT_HOCON_HPP

#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/types.h>
namespace hwut { namespace c {       // the C core, out of the global namespace
extern "C" {
#include "../c/hwut_hocon.h"
}
} }

namespace hwut {
namespace hocon {

struct Position {
    int line   = 0;
    int column = 0;
    std::string to_string() const;                   // 'line:column'
};

enum class E_ParseFault { SYNTAX, REFUSED };

struct ParseFault {
    E_ParseFault kind;
    std::string  file;
    Position     position;
    std::string  message;
    std::string to_string() const;                   // 'file:line:column: KIND: message'
};

struct SourceLine {
    std::string text;                                // the line, without its newline
    int         line;
    int         column_offset = 0;                   // what was removed before 'text'
};

struct Entry;

class Node {
public:
    enum Kind { SCALAR, LIST, OBJECT };

    Kind        kind() const;
    Position    position() const;
    // a scalar
    std::string type_name() const;                   // 'str', 'int', 'float', 'bool', 'NoneType'
    std::string value_repr() const;                  // as Python's '%r' prints the value
    bool        is_null() const;
    bool        as_bool() const;
    long long   as_int() const;
    double      as_float() const;
    std::string as_str() const;
    // a list
    std::vector<Node>        item_list() const;
    // an object
    std::vector<Entry>       entry_list() const;
    std::optional<Entry>     get(const std::string& key) const;
    std::vector<std::string> keys() const;

    const c::HoconNode* c() const { return node_; }

private:
    friend std::pair<Node, std::vector<ParseFault>> parse(const std::vector<SourceLine>&, const std::string&);
    Node(std::shared_ptr<c::HoconNode> root, const c::HoconNode* node) : root_(std::move(root)), node_(node) {}
    std::shared_ptr<c::HoconNode> root_;
    const c::HoconNode*           node_;
};

struct Entry {
    std::string key;
    Position    key_position;
    Node        node;
};

std::pair<Node, std::vector<ParseFault>> parse(const std::vector<SourceLine>& line_list, const std::string& file);
std::string                              cleandoc(const std::string& text);

} // namespace hocon
} // namespace hwut

#endif
