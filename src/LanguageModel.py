from src.ModelBuilder import ModelBuilder
from anki.collection import Collection

LANGUAGE_MODEL = "LANGUAGE_MODEL"
CONJUGATION_MODEL = "CONJUGATION_MODEL"
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


# french_verb_table = """ <table>
#   <tr>
#     <th>Company</th>
#     <th>Contact</th>
#     <th>Country</th>
#   </tr>
#   <tr>
#     <td>Alfreds Futterkiste</td>
#     <td>Maria Anders</td>
#     <td>Germany</td>
#   </tr>
#   <tr>
#     <td>Centro comercial Moctezuma</td>
#     <td>Francisco Chang</td>
#     <td>Mexico</td>
#   </tr>
# </table>
# """
def conjugation_model(collection: Collection):
    m = collection.models.by_name(CONJUGATION_MODEL)
    if m:
        return m
    else:
        builder = ModelBuilder(collection, CONJUGATION_MODEL)
        builder.add_field(TARGET_SPEECH)
        builder.add_field(TARGET_LANG)
        builder.add_field(SOURCE_LANG)
        builder.set_sort_field(2)
        builder.add_templates(
            "English to Conjugations",
            "{{SOURCE_LANG}}",
            '{{TARGET_LANG}}<hr id="answer">{{TARGET_SPEECH}}',
        )
        builder.make_model()

    return collection.models.by_name(CONJUGATION_MODEL)
