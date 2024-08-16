""" Classes for representing and managing Confluence data for Palje purposes. """

from __future__ import annotations


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
    """Identifies a Confluence page and holds references to its children."""

    def __init__(self, id: int, title: str, child_pages: list[ConfluencePage]):
        self._id = id
        self._title = title
        self._child_pages = child_pages

    @property
    def child_pages(self) -> list[ConfluencePage]:
        return self._child_pages

    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    def __str__(self):
        return f"{self.title} ({self.id})"
