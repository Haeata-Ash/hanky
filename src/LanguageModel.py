from ModelBuilder import ModelBuilder
from anki.collection import Collection

LANGUAGE_MODEL = "LANGUAGE_MODEL"
TARGET_LANG = "TARGET_LANG"
SOURCE_LANG = "SOURCE_LANG"
TARGET_SPEECH = "TARGET_SPEECH"


def get_language_model(collection: Collection):
    m = collection.models.by_name(LANGUAGE_MODEL)
    if m:
        return m
    else:
        builder = ModelBuilder(collection, LANGUAGE_MODEL)
        builder.add_field(TARGET_SPEECH)
        builder.add_field(TARGET_LANG)
        builder.add_field(SOURCE_LANG)
        builder.set_sort_field(2)
        builder.add_templates(
            "Speech Recognition",
            "{{TARGET_SPEECH}}",
            '{{TARGET_LANG}}<hr id="answer">{{SOURCE_LANG}}',
        )
        builder.add_templates(
            "Idiomatic Translation",
            "{{SOURCE_LANG}}",
            '{{TARGET_LANG}}<hr id="answer">{{TARGET_SPEECH}}',
        )
        builder.make_model()

    return collection.models.by_name(LANGUAGE_MODEL)
