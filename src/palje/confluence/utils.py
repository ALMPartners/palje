import random
import string

import click
from palje.progress_tracker import ProgressTracker


def construct_confluence_page_title(
    title: str, prefix: str | None = None, postfix: str | None = None
) -> str:
    """Construct a Confluence page title based on the original title and optional
    prefix/postfix strings.

    Arguments
    ---------

    title : str
        The original page title.

    prefix : str, optional
        A string to be prepended to the title.

    postfix : str, optional
        A string to be appended to the title.

    Returns
    -------

    str
        The new page title.

    """
    prefix = "" if prefix is None else prefix
    postfix = "" if postfix is None else postfix
    new_page_title = f"{prefix}{title}{postfix}"
    # TODO: sanitize, make sure it's a valid page title
    return new_page_title.strip()


def to_safe_filename(s: str, add_random_tail: bool = False) -> str:
    """Converts a string to a safe filename by removing special characters. Optionally
       adds a random tail to enforce uniqueness.

    Arguments:
    ----------

    s : str
        String to convert.

    Returns:
    --------

    str
    """
    allowed_non_alphanums = (".", "_")
    filename = "".join(
        c for c in s if c.isalnum() or c in allowed_non_alphanums
    ).rstrip()
    if add_random_tail:
        random_tail = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=8)
        )
        filename = f"{filename}_{random_tail}"
    return filename


def show_page_finding_progress(pt: ProgressTracker) -> None:
    """Print current page finding progress to the console.

    Arguments
    ---------

    pt : ProgressTracker
        The progress tracker object.

    """
    click.echo(
        f"\rChild pages found: {pt.target_total} ... {pt.elapsed_time:.2f}s",
        nl=False,
    )


def show_page_sorting_progress(pt: ProgressTracker) -> None:
    """Print current page sorting progress to the console.

    Arguments
    ---------

    pt : ProgressTracker
        The progress tracker object.

    """
    click.echo(
        f"\rPages sorted: {pt.passed}/{pt.target_total} ... {pt.elapsed_time:.2f}s"
        + f" ... {pt.message : <150}",
        nl=False,
    )


def show_page_creation_progress(pt: ProgressTracker) -> None:
    """Print current page creation progress to the console.

    Arguments
    ---------

    pt : ProgressTracker
        The progress tracker object.

    """
    click.echo(
        f"\rCreating Confluence pages: {pt.passed} / {pt.target_total}"
        + f" ... {pt.elapsed_time:.2f}s ... {pt.message: <150}",
        nl=False,
    )


def show_db_data_collecting_progress(pt: ProgressTracker) -> None:
    """Print current data collecting progress to the console.

    Arguments
    ---------

    pt : ProgressTracker
        The progress tracker object.

    """
    click.echo(
        f"\rGathering data from the db: {pt.passed} / {pt.target_total}"
        + f" ... {pt.elapsed_time:.2f}s ... {pt.message: <150}",
        nl=False,
    )
