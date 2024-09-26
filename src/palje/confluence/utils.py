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


def show_page_sorting_progress(pt: ProgressTracker) -> None:
    """Print current page sorting progress to the console.

    Arguments
    ---------

    pt : ProgressTracker
        The progress tracker object.

    """
    click.echo(
        f"\rChild pages sorted: {pt.passed}/{pt.target_total} ... {pt.elapsed_time:.2f}s"
        + f" ... {pt.message : <150}",
        nl=False,
    )


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
