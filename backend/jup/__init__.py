"""JUP's own domain layer, deliberately a sibling of `open_webui` rather than part of it.

Keeping it outside the vendor tree means the quarterly upstream rebase (ADR-0007) never
has to merge it, and the fast test suite can import it without installing the open_webui
runtime tree. Nothing under this package may reach beyond the standard library and PyYAML.
"""

from jup.portfolio import GATES, GateAssessment, Portfolio, Project, RecordError, project_portfolio

__all__ = [
    'GATES',
    'GateAssessment',
    'Portfolio',
    'Project',
    'RecordError',
    'project_portfolio',
]
