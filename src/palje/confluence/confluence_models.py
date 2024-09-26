""" Classes for representing and managing Confluence data for Palje purposes. """

from __future__ import annotations
from dataclasses import dataclass
import pathlib

from palje.confluence.confluence_types import ConfluencePageBodyFormat


class ConfluencePageHierarchy:
    """A hierarchy of Confluence pages."""

    def __init__(self, root_page: ConfluencePage):
        self._root_page = root_page

    def __str__(self):
        return f"ConfluencePageHierarchy(root_page={self._root_page})"

    @property
    def root_page(self) -> ConfluencePage:
        return self._root_page

    def _collect_pages(self, node: ConfluencePage, pages: list[ConfluencePage]) -> None:
        """Collect all pages in the hierarchy into a list"""
        pages.append(node)
        for child in node.child_pages:
            self._collect_pages(child, pages)

    @property
    def pages(self) -> list[ConfluencePage]:
        """All pages in the hierarchy as a flat list"""
        pages = []
        self._collect_pages(self._root_page, pages)
        return pages

    # TODO: remove id stuff if not needed
    def _collect_page_ids(self, node: ConfluencePage, page_ids: list[int]) -> None:
        """Collect all page ids in the hierarchy into a list"""
        page_ids.append(node.id)
        for child in node.child_pages:
            self._collect_page_ids(child, page_ids)

    @property
    def page_ids(self) -> list[int]:
        """All page IDs in the hierarchy"""
        page_ids = []
        self._collect_page_ids(self._root_page, page_ids)
        return page_ids

    def tree_str(
        self,
        page: ConfluencePage | None = None,
        indent: int = 0,
        result_str: str | None = None,
        sort: bool = True,
    ) -> str:
        """Return a string representation of the page hierarchy.

        Arguments
        ---------

        page: ConfluencePage | None
            The page to start the tree from. If None, the root page is used.

        indent: int
            The number of spaces to indent the tree per level.

        result_str: str | None
            The string representation of the hierarchy. Used for recursion.

        sort: bool
            Whether to sort the child pages by title.

        Returns
        -------

        str
            A string representation of the hierarchy.

        """
        if result_str is None:
            result_str = ""
        if page is None:
            page = self.root_page
        result_str = f"{' ' * indent}{page.title} ({page.id})\n"
        if sort:
            pages = sorted(page.child_pages, key=lambda x: x.title)
        else:
            pages = page.child_pages
        for child in pages:
            result_str += self.tree_str(
                page=child, indent=indent + 2, result_str=result_str
            )
        return result_str

    def __len__(self):
        return len(self.pages)


class ConfluencePage:
    """Confluence page details."""

    def __init__(
        self,
        id: int,
        title: str,
        child_pages: list[ConfluencePage] | None = None,
        parent_page: ConfluencePage | None = None,
        body_content: str | None = None,
        body_format: str | None = None,
    ):
        self._id = id
        self._title = title
        self._child_pages = child_pages or []
        self._body_content = body_content
        self._parent_page = parent_page
        if body_content and not body_format:
            raise ValueError("body_format must be provided if body_content is provided")
        if body_format and (body_format not in ConfluencePageBodyFormat):
            formats_str = [x for x in ConfluencePageBodyFormat].join(", ")
            raise ValueError(
                f"Invalid body_format: '{body_format}'. Expected one of: {formats_str}"
            )
        self._body_format = body_format

    @property
    def child_pages(self) -> list[ConfluencePage]:
        return self._child_pages

    @property
    def parent_page(self) -> ConfluencePage | None:
        return self._parent_page

    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def body_content(self) -> str | None:
        return self._body_content

    @property
    def body_format(self) -> str | None:
        return self._body_format

    def __str__(self):
        return f"ConfluencePage({self.id}, {self.title}, parent={self.parent_page})"


@dataclass
class ConfluencePageAttachment:
    title: str
    file_path: pathlib.Path
    content_type: str
