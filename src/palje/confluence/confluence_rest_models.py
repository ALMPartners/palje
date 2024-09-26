""" Model classes for holding Confluence REST API data. """

from __future__ import annotations
from dataclasses import dataclass
from pprint import pprint


@dataclass
class ConfluenceApiPageResult:
    """Confluence page result coming from page or page children API."""

    id: str
    status: str
    title: str
    space_id: str
    body_format: str | None = None
    body_content: str | None = None

    @staticmethod
    def from_dict(page_result_data: dict) -> ConfluenceApiPageResult:
        """Create a ConfluenceApiPageResult object from a dictionary.

        Arguments
        ---------
        page_result_data
            The dictionary containing the page result data. Expects dict keys to match
            the camelCase naming used in Confluence API JSON results.

        Returns
        -------

        ConfluenceApiPageResult
            The ConfluenceApiPageResult object created from the dictionary.
        """
        body_format: str | None = None
        body_content: str | None = None

        if "body" in page_result_data:
            body_format = (
                page_result_data.get("body", {})
                .get("storage", {})
                .get("representation", None)
            )
            body_content = (
                page_result_data.get("body", {}).get("storage", {}).get("value", None)
            )

        return ConfluenceApiPageResult(
            id=page_result_data["id"],
            status=page_result_data["status"],
            title=page_result_data["title"],
            space_id=page_result_data["spaceId"],
            body_format=body_format,
            body_content=body_content,
        )
