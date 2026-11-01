// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// PURPOSE: The HOCON subset parser -- see 'hwut_hocon.hpp'.
// _____________________________________________________________________________
#include "hwut_hocon.hpp"

#include <cstdlib>
#include <cstring>
#include <stdexcept>

using namespace hwut::c;

namespace hwut {
namespace hocon {

namespace {

Position of(c::HoconPosition p) { return Position{ p.line, p.column }; }

void
scalar_required(const c::HoconNode* node, c::HoconValueKind kind, const char* what)
/* RETURN: nothing where 'node' is a scalar of 'kind'; throws
 *         std::invalid_argument naming 'what' was asked of it else.       */
{
    if( node->kind != HOCON_SCALAR || node->value_kind != kind )
        throw std::invalid_argument(std::string("hocon: not a scalar of the kind '") + what + "'");
}

} // namespace

std::string
Position::to_string() const
/* RETURN: 'line:column'.                                                   */
{ return std::to_string(line) + ":" + std::to_string(column); }

std::string
ParseFault::to_string() const
/* RETURN: 'file:line:column: KIND: message'.                               */
{ return file + ":" + position.to_string() + ": " + (kind == E_ParseFault::SYNTAX ? "SYNTAX" : "REFUSED") + ": " + message; }

Node::Kind
Node::kind() const
/* RETURN: SCALAR, LIST or OBJECT -- what the node is.                      */
{ return node_->kind == HOCON_OBJECT ? OBJECT : node_->kind == HOCON_LIST ? LIST : SCALAR; }

Position
Node::position() const
/* RETURN: where the node begins in its file.                               */
{ return of(node_->position); }

std::string
Node::type_name() const
/* RETURN: the name Python's 'type(value).__name__' gives a scalar's value:
 *         'str', 'int', 'float', 'bool', 'NoneType'.                       */
{ return HoconNode_type_name(node_); }

std::string
Node::value_repr() const
/* RETURN: the scalar's value as Python's '%r' prints it.                   */
{
    size_t      n = 64 + (node_->value_kind == HOCON_STR ? 4 * std::strlen(node_->value.s) : 0);
    std::string buffer(n, '\0');
    return HoconNode_value_repr(node_, &buffer[0], n);
}

bool Node::is_null() const
/* RETURN: true where the node is a scalar whose value is nothing (None).   */
{ return node_->kind == HOCON_SCALAR && node_->value_kind == HOCON_NULL; }

bool Node::as_bool() const
/* RETURN: the boolean value; std::invalid_argument where it is none.       */
{ scalar_required(node_, HOCON_BOOL, "bool"); return node_->value.b != 0; }

long long Node::as_int() const
/* RETURN: the integer value; std::invalid_argument where it is none.       */
{ scalar_required(node_, HOCON_INT, "int"); return node_->value.i; }

double Node::as_float() const
/* RETURN: the float value; std::invalid_argument where it is none.         */
{ scalar_required(node_, HOCON_FLOAT, "float"); return node_->value.f; }

std::string Node::as_str() const
/* RETURN: the string value; std::invalid_argument where it is none.        */
{ scalar_required(node_, HOCON_STR, "str"); return node_->value.s; }

std::vector<Node>
Node::item_list() const
/* RETURN: the items of a list, in order; empty for any other node.         */
{
    std::vector<Node> result;
    if( node_->kind == HOCON_LIST )
        for(size_t i = 0; i < node_->item_n; ++i) result.push_back(Node(root_, node_->item[i]));
    return result;
}

std::vector<Entry>
Node::entry_list() const
/* RETURN: the entries of an object, in written order; empty for any other
 *         node.                                                            */
{
    std::vector<Entry> result;
    if( node_->kind == HOCON_OBJECT )
        for(size_t i = 0; i < node_->entry_n; ++i)
            result.push_back(Entry{ node_->entry[i].key, of(node_->entry[i].key_position),
                                    Node(root_, node_->entry[i].node) });
    return result;
}

std::optional<Entry>
Node::get(const std::string& key) const
/* RETURN: the entry named 'key' of an object; nullopt, no such entry (or
 *         the node is no object).                                         */
{
    if( node_->kind != HOCON_OBJECT ) return std::nullopt;
    const c::HoconEntry* e = HoconNode_get(const_cast<c::HoconNode*>(node_), key.c_str());
    if( ! e ) return std::nullopt;
    return Entry{ e->key, of(e->key_position), Node(root_, e->node) };
}

std::vector<std::string>
Node::keys() const
/* RETURN: the keys of an object in written order; empty for another node. */
{
    std::vector<std::string> result;
    for(const Entry& e : entry_list()) result.push_back(e.key);
    return result;
}

std::pair<Node, std::vector<ParseFault>>
parse(const std::vector<SourceLine>& line_list, const std::string& file)
/* RETURN: [0] the document, an OBJECT -- every entry of the outermost
 *             level; possibly empty;
 *         [1] every fault found, in the order found; empty on a clean
 *             parse. 'file' names the file in the faults.                 */
{
    std::vector<c::HoconSourceLine> c_line;
    c::HoconFaultList               c_fault;
    for(const auto& l : line_list) c_line.push_back({ l.text.c_str(), l.line, l.column_offset });
    HoconFaultList_init(&c_fault);
    std::shared_ptr<c::HoconNode> root(Hocon_parse(c_line.data(), c_line.size(), file.c_str(), &c_fault),
                                      HoconNode_free);
    std::vector<ParseFault> fault_list;
    for(size_t i = 0; i < c_fault.n; ++i) {
        const c::HoconFault& f = c_fault.fault[i];
        fault_list.push_back(ParseFault{ f.kind == HOCON_SYNTAX ? E_ParseFault::SYNTAX : E_ParseFault::REFUSED,
                                         file, of(f.position), f.message });
    }
    HoconFaultList_free(&c_fault);
    const c::HoconNode* top = root.get();
    return { Node(std::move(root), top), std::move(fault_list) };
}

std::string
cleandoc(const std::string& text)
/* RETURN: 'text' laid out as Python 3.13's 'inspect.cleandoc': tabs
 *         expanded, the indentation common to the lines after the first
 *         removed, the first line's leading blanks removed, empty lines at
 *         both ends dropped.                                               */
{
    char*       c_text = Hocon_cleandoc(text.c_str());
    std::string result(c_text);
    std::free(c_text);
    return result;
}

} // namespace hocon
} // namespace hwut
