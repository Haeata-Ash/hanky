from hanky import Hanky


# instantiate the hanky app
hanky = Hanky()


@hanky.card_processor("basic", expected_args=[], card_fields=[])
def lowercase_card(card: dict):
    """Lower-case the text on every field of the card."""
    return {field: value.lower() for field, value in card.items()}


# run the hanky cli application by running this python file, for example:
#   python3 demo_lowercase.py load basic words.csv -d english::vocab
hanky.run()
