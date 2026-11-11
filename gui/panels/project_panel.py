from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


class ProjectPanel(QGroupBox):
    """Project explorer panel."""

    def __init__(self) -> None:
        super().__init__("Project Explorer")

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)

        self.populate()

    def populate(self) -> None:
        """Temporary demo data."""

        rooms = QTreeWidgetItem(["Rooms"])
        characters = QTreeWidgetItem(["Characters"])
        props = QTreeWidgetItem(["Props"])
        concepts = QTreeWidgetItem(["Concepts"])

        rooms.addChild(
            QTreeWidgetItem(["Bridge"])
        )

        rooms.addChild(
            QTreeWidgetItem(["Corridor"])
        )

        rooms.addChild(
            QTreeWidgetItem(["Engine Room"])
        )

        characters.addChild(
            QTreeWidgetItem(["Captain"])
        )

        characters.addChild(
            QTreeWidgetItem(["Robot"])
        )

        self.tree.addTopLevelItem(
            rooms
        )

        self.tree.addTopLevelItem(
            characters
        )

        self.tree.addTopLevelItem(
            props
        )

        self.tree.addTopLevelItem(
            concepts
        )

        self.tree.expandAll()