""" Model classes for holding Confluence REST API data. """

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ConfluenceApiPageResult:
    """Confluence page result coming from page or page children API."""

    id: str
    status: str
    title: str
    space_id: str

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
        return ConfluenceApiPageResult(
            id=page_result_data["id"],
            status=page_result_data["status"],
            title=page_result_data["title"],
            space_id=page_result_data["spaceId"],
        )
