import json

from models import Style
from settings import Settings


class StyleService:

    def __init__(self):
        self._styles = self._load_styles()

    def _load_styles(self) -> list[Style]:

        styles = []

        for file in Settings.FOOOCUS_PATH.glob("sdxl_styles/*.json"):

            with open(file, encoding="utf-8") as f:
                data = json.load(f)

            for entry in data:
                styles.append(
                    Style(
                        name=entry["name"],
                        source=file.stem
                    )
                )

        styles.sort(key=lambda s: s.name.lower())

        return styles
    
    def get_all(self) -> list[Style]:
        return self._styles.copy()

    def get_names(self) -> list[str]:
        """
        Gibt alle Style-Namen alphabetisch sortiert zurück.
        """
        return [style.name for style in self.get_all()]

    def find(self, name: str) -> Style | None:
        """
        Sucht einen Style anhand seines Namens.
        """
        for style in self.get_all():
            if style.name.casefold() == name.casefold():
                return style

        return None