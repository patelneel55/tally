"""Command-line interface."""
import click


@click.command()
@click.version_option()
def main() -> None:
    """Tally."""


if __name__ == "__main__":
    main(prog_name="tally")  # pragma: no cover
