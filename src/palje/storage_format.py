# Palje - Document MSSQL databases to Confluence wiki
#
# Copyright 2021 ALM Partners Oy
# SPDX-License-Identifier: Apache-2.0

"""Module for formatting content into Confluence storage format."""
from html import escape
from xml.etree import ElementTree as ET

ET.register_namespace("xmlns:ac", "ac")


def objects_list():
    """Create title 'Objects', following children macro."""
    h1 = ET.Element('h1')
    h1.text = 'Objects'
    p = ET.Element('p')
    p.append(children_macro())
    return ET.tostring(h1, encoding='unicode') + \
        ET.tostring(p, encoding='unicode')


def children_macro():
    macro = ET.Element('ac:structured-macro', attrib={
        "ac:macro-id": "3f6a7cbe-2142-47ac-a9ef-a5226c237a51",
        "ac:name": "children",
        "ac:schema-version": "2"
    })
    parameter1 = ET.Element('ac:parameter', attrib={"ac:name": "all"})
    parameter1.text = "true"
    parameter2 = ET.Element('ac:parameter', attrib={"ac:name": "excerptType"})
    parameter2.text = "simple"
    macro.append(parameter1)
    macro.append(parameter2)
    return macro


def description_header(description):
    """Create title 'Description', following description and line break."""
    h1 = ET.Element('h1')
    h1.text = 'Description'
    p1 = ET.Element('p')
    macro = description_macro(description)
    p1.append(macro)
    return ET.tostring(h1, encoding='unicode') + \
        ET.tostring(p1, encoding='unicode')


def description_macro(description):
    """This will let the description show in the children macro."""
    macro = ET.Element('ac:structured-macro', attrib={
        "ac:macro-id": "3f6a7cbe-2142-47ac-a9ef-a5226c237a52",
        "ac:name": "excerpt",
        "ac:schema-version": "2"
    })
    body = ET.Element('ac:rich-text-body')
    body.text = escape(description)
    macro.append(body)
    return macro


def html_table(rows):
    """Create HTML table with header from list of dicts."""
    tbody = ET.Element('tbody')
    # headers
    tr = ET.Element('tr')
    for header in rows[0].keys():
        th = ET.Element('th')
        th.text = escape(header)
        tr.append(th)
    tbody.append(tr)
    # rows
    for row in rows:
        tr = ET.Element('tr')
        for cell in row:
            td = ET.Element('td')
            value = row[cell]
            if isinstance(value, list):    # value is list of dicts
                for dictionary in value:
                    p = ET.Element('p')
                    p.text = ' '.join([val for val in dictionary.values()])
                    td.append(p)
            else:
                td.text = escape(value)    # value is string or number
            tr.append(td)
        tbody.append(tr)
    table = ET.Element('table')
    table.append(tbody)
    return table


def column_table(columns):
    """Create title 'Columns', following table of column information."""
    h1 = ET.Element('h1')
    h1.text = 'Columns'
    table = html_table(columns)
    return ET.tostring(h1, encoding='unicode') + \
        ET.tostring(table, encoding='unicode')


def index_table(indexes):
    """Create title 'Indexes', following table of index information.
    Return empty string if no indexes.
    """
    if not indexes:
        return ''
    h1 = ET.Element('h1')
    h1.text = 'Indexes'
    table = html_table(indexes)
    return ET.tostring(h1, encoding='unicode') + \
        ET.tostring(table, encoding='unicode')


def parameter_table(parameters):
    """Create title 'Parameters', following table of parameter information.
    Return empty string if no parameters.
    """
    if not parameters:
        return ''
    h1 = ET.Element('h1')
    h1.text = 'Parameters'
    table = html_table(parameters)
    return ET.tostring(h1, encoding='unicode') + \
        ET.tostring(table, encoding='unicode')


def dependencies_table(dependencies):
    """Create title 'Dependencies', following table of object dependencies.
    Return empty string if no dependencies.
    """
    if not dependencies:
        return ''
    h1 = ET.Element('h1')
    h1.text = 'Dependencies'
    table = html_table(dependencies)
    return ET.tostring(h1, encoding='unicode') + \
        ET.tostring(table, encoding='unicode')
