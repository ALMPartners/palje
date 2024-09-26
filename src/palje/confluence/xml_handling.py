import lxml.etree as ET


def _wrap_confluence_xml_content(raw_confluence_page_content: str) -> str:
    """Wrap the given Confluence page content with enough tags to make it parsable XML."""
    entity = """<!DOCTYPE root SYSTEM "test" [
            <!ENTITY nbsp ' '>
            <!ENTITY ouml 'Ã¶'>
            <!ENTITY Ouml 'Ã–'>
            <!ENTITY auml 'Ã¤'>
            <!ENTITY Auml 'Ã„'>
            <!ENTITY aring 'Ã¥'>
            <!ENTITY Aring 'Ã…'>
            <!ENTITY lt '<'>
            <!ENTITY gt '>'>]>"""
    root_start = '<root xmlns:ac="ac" xmlns:ri="ri">'
    root_end = "</root>"
    return entity + root_start + raw_confluence_page_content + root_end


def _unwrap_confluence_xml_content(e: ET.ElementTree) -> str:
    """Remove the extra elements set with _wrap_confluence_xml_content."""
    if len(e) == 1:
        return ET.tostring(e[0], encoding="unicode")
    else:
        return ET.tostring(e, encoding="unicode")


def _find_attachment_by_title(attachments: list[dict], title: str) -> dict | None:
    """Get attachment by title.

    Parameters
    ----------

    attachments : list[dict]
        List of attachments.

    title : str
        Title of the attachment to find.

    Raises
    ------
        ValueError if there were multiple matches.

    Returns
    -------
      dict: matching attachment data
      None: if no matching data was found
    """

    matches = [att for att in attachments if att["title"] == title]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        # Assuming that this is not possible with real data but just in case
        raise ValueError(f"Multiple attachments found with title '{title}'")

    return None


def relink_gliffy_attachments(page_content: str, attachments: dict) -> str:
    """Relink Gliffy attachments in the Confluence page content using the data found in
    given dict.


    Parameters
    ----------

    page_content : str
        Confluence page content as a string.

    attachments : dict
        Dict containing the attachments data to be used for updating.

    Returns
    -------

    str
        Updated Confluence page content as a string.
    """

    GLIFFY_MATCH = '//*[local-name()="structured-macro"][@*="gliffy"]'
    PARAM_MATCH = '*[local-name()="parameter"]'

    base_url: str = attachments["_links"]["base"]

    parser = ET.XMLParser(
        strip_cdata=False,
        remove_pis=True,
        resolve_entities=False,
    )

    requires_unwrap = False
    try:
        tree = ET.fromstring(page_content, parser=parser)
    except ET.ParseError as e:
        # Malformed XML, try to fix it by wrapping it with a root element
        parsable_xml_str = _wrap_confluence_xml_content(page_content)
        tree = ET.fromstring(parsable_xml_str, parser=parser)
        requires_unwrap = True

    gliffy_els: list[ET.Element] = tree.xpath(GLIFFY_MATCH)

    for el in gliffy_els:
        param_els: list[dict] = el.xpath(PARAM_MATCH)  # TODO: fix typing

        params_dict = {p.attrib["{ac}name"]: p.text for p in param_els}
        diagram_name = params_dict.get("name")
        diagram_png_name = f"{diagram_name}.png"

        new_diagram_attachment = _find_attachment_by_title(
            attachments["results"], title=diagram_name
        )
        new_image_attachment = _find_attachment_by_title(
            attachments["results"], title=diagram_png_name
        )

        for p_el in param_els:
            match p_el.attrib["{ac}name"]:
                case "imageAttachmentId":
                    p_el.text = new_image_attachment["id"]
                case "macroId":
                    ...
                case "baseUrl":
                    p_el.text = base_url
                case "name":
                    ...
                case "diagramAttachmentId":
                    p_el.text = new_diagram_attachment["id"]
                case "containerId":
                    p_el.text = new_diagram_attachment["pageId"]
                case "timestamp":
                    ...
                case "displayName":
                    ...
                case "version":
                    ...
                case _:
                    raise ValueError(
                        f"relink_gliffy_attachments: Unknown attribute: {p_el.attrib}"
                    )

    if requires_unwrap:
        return _unwrap_confluence_xml_content(tree)
    else:
        return ET.tostring(tree, encoding="unicode")
