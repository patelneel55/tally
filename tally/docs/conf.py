"""Sphinx configuration."""
project = "Tally"
author = "Neel Patel"
copyright = "2025, Neel Patel"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
