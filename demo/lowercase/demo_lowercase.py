from hanky import HankyPipeline


# instantiate the hanky app, creating cards with the "basic" model
hanky = HankyPipeline("basic")


@hanky.card_processor(expected_args=[], required_fields=[])
def lowercase_card(card: dict):
    """Lower-case the text on every field of the card."""
    return {field: value.lower() for field, value in card.items()}


# run the hanky cli application by running this python file, for example:
#   python3 demo_lowercase.py pipe words.csv --into english::vocab
if __name__ == "__main__":
    hanky.run()
