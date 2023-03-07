from typing import List, Dict
from anki.collection import Collection


class ModelBuilder:
    def __init__(self, collection: Collection, model_name: str) -> None:
        self.col: Collection = collection
        self.name: str = model_name
        self.fields: List[str] = []
        self.sort_idx = 0
        self.templates: List = []

    def add_field(self, f_name: str, ord=None):
        if not isinstance(f_name, str):
            raise TypeError("Field must be a string.")
        f = self.col.models.new_field(f_name)
        if ord:
            f["ord"] = ord
        self.fields.append(f)

    def add_templates(self, name: str, qfmt: str, afmt: str, ord=None):
        template = self.col.models.new_template(name)
        template["qfmt"] = qfmt
        template["afmt"] = afmt
        if ord:
            template["ord"] = ord

        self.templates.append(template)

    def set_sort_field(self, idx):
        if not (0 <= idx < len(self.fields)):
            raise Exception("Sort idx must be a field")
        self.sort_idx = idx

    def make_model(self) -> None:
        models = self.col.models
        m = models.new(self.name)

        [models.add_field(m, f) for f in self.fields]
        [models.add_template(m, t) for t in self.templates]
        self.col.models.add(m)
        models.set_sort_index(m, self.sort_idx)
        models.save(m)
