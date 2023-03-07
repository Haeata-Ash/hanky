from anki.collection import Collection


class NoteBuilder:
    def __init__(self, name, model, deck_name: str, collection: Collection) -> None:
        self.name: str = name
        self.col: Collection = collection
        self.model = model
        self.note = self.col.new_note(self.model)
        self.deck_name: str = deck_name

    def _is_valid_field_for_model(self, field_name: str):
        if field_name not in self.col.models.field_names(self.model):
            raise Exception("Setting non existant field for note model.")

    def set_field(self, field_name: str, value: str):
        self._is_valid_field_for_model(field_name)
        self.note[field_name] = value

    def set_sound_field(self, field_name: str, media_url: str):
        self._is_valid_field_for_model(field_name)
        self.note[field_name] = f"[sound:{media_url}]"

    def make_note(self, deck_id):
        self.col.add_note(self.note, deck_id)
        self.col.save()
