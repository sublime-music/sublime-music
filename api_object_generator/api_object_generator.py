#! /usr/bin/env python3
# TODO use dataclasses
"""
Autogenerates Python classes for Subsonic API objects.

This program constructs a dependency graph of all of the entities defined by a
Subsonic REST API XSD file. It then uses that graph to generate code which
represents those API objects in Python.
"""

import re
import sys
from collections import defaultdict
from typing import DefaultDict, Dict, List, Set, Tuple

from graphviz import Digraph
from lxml import etree

# Global variables.
tag_type_re = re.compile(r'\{.*\}(.*)')
element_type_re = re.compile(r'.*:(.*)')
primitive_translation_map = {
    'string': 'str',
    'double': 'float',
    'boolean': 'bool',
    'long': 'int',
    'dateTime': 'datetime',
}


def render_digraph(graph: DefaultDict[str, Set[str]], filename: str):
    """
    Render a graph of the form {'node_name': iterable(node_name)} to
    ``filename``.
    """
    g = Digraph('G', filename=f'/tmp/{filename}', format='png')
    for type_, deps in graph.items():
        g.node(type_)

        for dep in deps:
            g.edge(type_, dep)

    g.render()


def primitive_translate(type_str: str) -> str:
    # Translate the primitive values, but default to the actual value.
    return primitive_translation_map.get(type_str, type_str)


def extract_type(type_str: str) -> str:
    match = element_type_re.match(type_str)
    if not match:
        raise Exception(f'Could not extract type from string "{type_str}"')
    return primitive_translate(match.group(1))


def extract_tag_type(tag_type_str: str) -> str:
    match = tag_type_re.match(tag_type_str)
    if not match:
        raise Exception(
            f'Could not extract tag type from string "{tag_type_str}"')
    return match.group(1)


def get_dependencies(
        xs_el: etree._Element,
        is_response_obj=False,
) -> Tuple[Set[str], Dict[str, str]]:
    """
    Return the types which ``xs_el`` depends on as well as the type of the
    object for embedding in other objects.
    """
    # If the node is a comment, the tag will be callable for some reason.
    # Ignore it.
    if hasattr(xs_el.tag, '__call__'):
        return set(), {}

    tag_type = extract_tag_type(xs_el.tag)
    name = xs_el.attrib.get('name')

    depends_on: Set[str] = set()
    type_fields: Dict[str, str] = {}

    if tag_type == 'element':
        # <element>s depend on their corresponding ``type``.
        # There is only one field: name -> type.
        type_ = extract_type(xs_el.attrib['type'])
        depends_on.add(type_)
        if is_response_obj:
            type_ = f'Optional[{type_}] = None'
        type_fields[name] = type_

    elif tag_type == 'simpleType':
        # <simpleType>s do not depend on any other type (that's why they are
        # simple lol).
        # The fields are the ``key = "key"`` pairs for the Enum if the
        # restriction type is ``enumeration``.

        restriction = xs_el.getchildren()[0]
        restriction_type = extract_type(restriction.attrib['base'])
        if restriction_type == 'str':
            restriction_children = restriction.getchildren()
            if extract_tag_type(restriction_children[0].tag) == 'enumeration':
                type_fields['__inherits__'] = 'Enum'
                for rc in restriction_children:
                    rc_type = primitive_translate(rc.attrib['value'])
                    type_fields[rc_type] = rc_type
            else:
                type_fields['__inherits__'] = 'str'
        else:
            type_fields['__inherits__'] = restriction_type

    elif tag_type == 'complexType':
        # <complexType>s depend on all of the types that their children have.
        for el in xs_el.getchildren():
            deps, fields = get_dependencies(
                el,
                is_response_obj=name == 'Response',
            )

            # Genres has this.
            fields['value'] = 'Optional[str] = None'
            depends_on |= deps
            type_fields.update(fields)

    elif tag_type == 'choice':
        # <choice>s depend on all of their choices (children) types.
        for choice in xs_el.getchildren():
            deps, fields = get_dependencies(choice, is_response_obj)
            depends_on |= deps
            type_fields.update(fields)

    elif tag_type == 'attribute':
        # <attribute>s depend on their corresponding ``type``.
        depends_on.add(extract_type(xs_el.attrib['type']))
        is_optional = is_response_obj or xs_el.attrib['use'] == 'optional'
        format_str = 'Optional[{}] = None' if is_optional else '{}'
        type_fields[name] = format_str.format(
            extract_type(xs_el.attrib['type']))

    elif tag_type == 'sequence':
        # <sequence>s depend on their children's types.
        for el in xs_el.getchildren():
            deps, fields = get_dependencies(el)
            depends_on |= deps

            if len(fields) < 1:
                # This is a comment.
                continue

            name, type_ = list(fields.items())[0]
            type_fields[name] = f'List[{type_}] = field(default_factory=list)'

    elif tag_type == 'complexContent':
        # <complexContent>s depend on the extension's types.
        extension = xs_el.getchildren()[0]
        deps, fields = get_dependencies(extension)
        depends_on |= deps
        type_fields.update(fields)

    elif tag_type == 'extension':
        # <extension>s depend on their children's types as well as the base
        # type.
        for el in xs_el.getchildren():
            deps, fields = get_dependencies(el)
            depends_on |= deps
            type_fields.update(fields)

        base = xs_el.attrib.get('base')
        if base:
            base_type = extract_type(base)
            depends_on.add(base_type)
            type_fields['__inherits__'] = base_type

    else:
        raise Exception(f'Unknown tag type {tag_type}.')

    depends_on -= {'bool', 'int', 'str', 'float', 'datetime'}
    return depends_on, type_fields


# Check arguments.
# =============================================================================
if len(sys.argv) < 3:
    print(f'Usage: {sys.argv[0]} <schema_file> <output_file>.')  # noqa: T001
    sys.exit(1)

schema_file, output_file = sys.argv[1:]

# Determine who depends on what and determine what fields are on each object.
# =============================================================================
with open(schema_file) as f:
    tree = etree.parse(f)

dependency_graph: DefaultDict[str, Set[str]] = defaultdict(set)
type_fields: DefaultDict[str, Dict[str, str]] = defaultdict(dict)

for xs_el in tree.getroot().getchildren():
    # We don't care about the top-level xs_el. We just care about the actual
    # types defined by the spec.
    if hasattr(xs_el.tag, '__call__'):
        continue

    name = xs_el.attrib['name']
    dependency_graph[name], type_fields[name] = get_dependencies(xs_el)

# Determine order to put declarations using a topological sort.
# =============================================================================

# DEBUG
render_digraph(dependency_graph, 'dependency_graph')

# DFS from the subsonic-response node while keeping track of the end time to
# determine the order in which to output the API objects to the file. (The
# order is the sort of the end time. This is slightly different than
# traditional topological sort because I think that I built my digraph the
# wrong direction, but it gives the same result, regardless.)

end_times: List[Tuple[str, int]] = []
seen: Set[str] = set()
i = 0


def dfs(g: DefaultDict[str, Set[str]], el: str):
    global i
    if el in seen:
        return
    seen.add(el)

    i += 1
    for child in sorted(g[el]):
        dfs(g, child)

    i += 1
    end_times.append((el, i))


dfs(dependency_graph, 'subsonic-response')

output_order = [x[0] for x in sorted(end_times, key=lambda x: x[1])]
output_order.remove('subsonic-response')

# Create the code according to the spec that was generated earlier.
# =============================================================================


def generate_class_for_type(type_name: str) -> str:
    fields = type_fields[type_name]

    code = ['', '']
    inherits_from = ['APIObject']

    inherits = fields.get('__inherits__', '')
    is_enum = 'Enum' in inherits

    if inherits:
        if inherits in primitive_translation_map.values() or is_enum:
            inherits_from.append(inherits)
        else:
            # Add the fields, we can't directly inherit due to the Diamond
            # Problem.
            fields.update(type_fields[inherits])

    format_str = '    ' + ("{} = '{}'" if is_enum else '{}: {}')

    if not is_enum:
        code.append('@dataclass(frozen=True)')

    code.append(f"class {type_name}({', '.join(inherits_from)}):")
    has_properties = False
    sorted_fields = sorted(
        fields.items(),
        key=lambda f: f[1].startswith('Optional[') or f[1].startswith('List['),
    )
    for key, value in sorted_fields:
        if key.startswith('__'):
            continue

        # Uppercase the key if an Enum.
        key = key.upper() if is_enum else key

        code.append(format_str.format(key, value))
        has_properties = True

    indent_str = '    {}'
    if not has_properties:
        code.append(indent_str.format('pass'))

    return '\n'.join(code)


with open(output_file, 'w+') as outfile:
    outfile.writelines(
        '\n'.join(
            [
                '"""',
                'WARNING: AUTOGENERATED FILE',
                'This file was generated by the api_object_generator.py',
                'script. Do not modify this file directly, rather modify the',
                'script or run it on a new API version.',
                '"""',
                '',
                'from dataclasses import dataclass, field',
                'from datetime import datetime',
                'from enum import Enum',
                'from typing import List, Optional',
                '',
                'from sublime.server.api_object import APIObject',
                *map(generate_class_for_type, output_order),
            ]) + '\n')
