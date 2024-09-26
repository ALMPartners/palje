import lxml.etree as ET

from palje.confluence.xml_handling import (
    _unwrap_confluence_xml_content,
    _wrap_confluence_xml_content,
)


def test_wrapping_adds_root_element():
    page_content = "some content"
    wrapped_content = _wrap_confluence_xml_content(page_content)
    assert wrapped_content.endswith("</root>")


def test_unwrapping_removes_root_element():
    page_content = "<foo><p>some content</p></foo>"
    wrapped_content = _wrap_confluence_xml_content(page_content)

    parser = ET.XMLParser(
        strip_cdata=False,
        remove_pis=True,
        resolve_entities=False,
    )
    tree = ET.fromstring(wrapped_content, parser=parser)
    unwrapped_content = _unwrap_confluence_xml_content(tree)
    # FIXME: unwrapped_content should equal to page_content without extra attrs
    assert (
        unwrapped_content
        == '<foo xmlns:ac="ac" xmlns:ri="ri"><p>some content</p></foo>'
    )
