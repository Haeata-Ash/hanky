from typing import Callable, List


class ModelProcessor:
    """The wrapper for user defined functions which process cards of a certain model.

    Wraps a python callable which takes a dictionary representing an anki card,
    the key word arguments the callable expects and the fields (keys) it
    assumes to be already present in the card.

    Attributes:
        f: the user defined callable which processes each card
        model: The type of card (anki model) which the callable processes
        expected_args: Expected key word arguments of the callable
        card_fields: Anki fields expected to be already present in any cards processed
    """

    def __init__(
        self,
        model_name: str,
        func: Callable[[dict], dict],
        expected_args: List[str],
        card_fields: List[str],
    ):
        """Initializes a model processor

        Args:
            func: the user defined callable which processes each card
            model_name: The name of the anki model whose car
            expected_args: Expected key word arguments of the callable
            card_fields: Anki fields expected to be already d
        """

        self.f = func
        self.model = model_name
        self.expected_args = expected_args
        self.card_fields = card_fields

        if not isinstance(self.expected_args, list):
            raise TypeError("'expected_args' must be a list of strings")
        if not isinstance(self.card_fields, list):
            raise TypeError("'required_fields' must be a list of strings")

    def __call__(self, card: dict, **kwargs) -> dict:
        """Check expected fields are present in card and exp
        were provided, call the callable on the card and validate output is a dictionary.

        Args:
            card: dictionary representing field, value pairs
            **kwargs: key word arguments for the callable

        Returns:
            card dictionary with possibly new fields added b

        """
        for k in self.card_fields:
            if k not in card:
                raise KeyError(f"Processor requires '{k}' to be present")

        for k in self.expected_args:
            if k not in kwargs:
                raise KeyError(
                    f"Processor for {self.model} expects keyit is passed in via the --args option"
                )

        ret = self.f(card, **kwargs)
        if not isinstance(ret, dict):
            raise TypeError(f"Processor function did not return a dictiope {type(ret)}")

        return ret
