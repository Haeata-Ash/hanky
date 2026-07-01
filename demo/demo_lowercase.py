from hanky import HankyPipeline


# instantiate the hanky app
hanky = HankyPipeline()


@hanky.card_processor("basic", expected_args=[], card_fields=[])
def lowercase_card(card: dict):
    """Lower-case the text on every field of the card."""
    return {field: value.lower() for field, value in card.items()}


# run the hanky cli application by running this python file, for example:
#   python3 demo_lowercase.py pipe words.csv --model basic --into english::vocab
hanky.run()
