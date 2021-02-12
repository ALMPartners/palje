from xml.etree import ElementTree as ET

import palje.storage_format as storage_format

CHILDREN_MACRO = '<ac:structured-macro ac:macro-id="3f6a7cbe-2142-47ac-a9ef-a5226c237a51" ac:name="children" ac:schema-version="2"><ac:parameter ac:name="all">true</ac:parameter><ac:parameter ac:name="excerptType">simple</ac:parameter></ac:structured-macro>'
DESCRIPTION_MACRO = '<ac:structured-macro ac:macro-id="3f6a7cbe-2142-47ac-a9ef-a5226c237a52" ac:name="excerpt" ac:schema-version="2"><ac:rich-text-body>{}</ac:rich-text-body></ac:structured-macro>'
TABLE_INPUT = [{'Title1': 'A', 'Title2': 'B'}, {'Title1': 'C', 'Title2': 'D'}]
TABLE_OUTPUT = '<table><tbody><tr><th>Title1</th><th>Title2</th></tr><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></tbody></table>'


def test_objects_list_should_return_h1_and_p():
    assert storage_format.objects_list(
    ) == f'<h1>Objects</h1><p>{CHILDREN_MACRO}</p>'


def test_children_macro_should_return_element():
    children_macro = storage_format.children_macro()
    assert isinstance(children_macro, ET.Element)


def test_children_macro_should_match_string():
    children_macro = storage_format.children_macro()
    assert ET.tostring(children_macro, encoding='unicode') == CHILDREN_MACRO


def test_description_header_should_return_h1_and_p():
    description = DESCRIPTION_MACRO.format('test')
    assert storage_format.description_header(
        'test') == f'<h1>Description</h1><p>{description}</p>'


def test_description_macro_should_return_element():
    description_macro = storage_format.description_macro('test')
    assert isinstance(description_macro, ET.Element)


def test_description_macro_should_match_string():
    description_macro = storage_format.description_macro('test')
    assert ET.tostring(description_macro,
                       encoding='unicode') == DESCRIPTION_MACRO.format('test')


def test_html_table_should_return_element():
    table = storage_format.html_table(TABLE_INPUT)
    assert isinstance(table, ET.Element)


def test_html_table_should_match_string():
    table = storage_format.html_table(TABLE_INPUT)
    assert ET.tostring(table, encoding='unicode') == TABLE_OUTPUT


def test_column_table_should_return_h1_and_table():
    assert storage_format.column_table(
        TABLE_INPUT) == f'<h1>Columns</h1>{TABLE_OUTPUT}'


def test_index_table_should_return_h1_and_table():
    assert storage_format.index_table(
        TABLE_INPUT) == f'<h1>Indexes</h1>{TABLE_OUTPUT}'


def test_parameter_table_should_return_h1_and_table():
    assert storage_format.parameter_table(
        TABLE_INPUT) == f'<h1>Parameters</h1>{TABLE_OUTPUT}'


def test_dependencies_table_should_return_h1_and_table():
    assert storage_format.dependencies_table(
        TABLE_INPUT) == f'<h1>Dependencies</h1>{TABLE_OUTPUT}'
