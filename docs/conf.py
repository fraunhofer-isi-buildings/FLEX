project = "FLEX"
author = "Fraunhofer ISI – Climate-Neutral Buildings"
release = "0.1"

extensions = [
    "myst_parser",
    "sphinx_rtd_theme",
]

source_suffix = {
    ".md": "markdown",
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

html_theme = "sphinx_rtd_theme"
html_title = "FLEX Model Docs"

html_theme_options = {
    "navigation_depth": 3,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "titles_only": False,
}

exclude_patterns = ["_build"]
