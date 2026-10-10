from plone.demoeditor.testing import FUNCTIONAL_TESTING
from pytest_plone import fixtures_factory


pytest_plugins = ["pytest_plone"]


globals().update(fixtures_factory(((FUNCTIONAL_TESTING, "functional"),)))
