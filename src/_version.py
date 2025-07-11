from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("ai-novel-editor")
except PackageNotFoundError:
    __version__ = "dev"