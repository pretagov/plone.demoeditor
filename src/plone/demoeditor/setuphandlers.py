from Acquisition import aq_inner
from Acquisition import aq_parent
from plone.base.interfaces import INonInstallable
from plone.demoeditor.demo import delete_demo_editor
from plone.demoeditor.demo import demo_settings
from plone.demoeditor.demo import ensure_demo_editor
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:
    def getNonInstallableProfiles(self) -> list[str]:
        return ["plone.demoeditor:uninstall"]


def post_install(setup_tool) -> None:
    """Make the demo account now, if the environment turns the demo on."""
    settings = demo_settings()
    if settings is not None:
        ensure_demo_editor(aq_parent(aq_inner(setup_tool)), *settings)


def uninstall(setup_tool) -> None:
    """Delete the demo account: its public password must not outlive the add-on."""
    delete_demo_editor(aq_parent(aq_inner(setup_tool)))
