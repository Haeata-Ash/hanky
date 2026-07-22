import inspect
from typing import Any, Callable, List, Dict, Tuple, Union

from hanky.media import CardMedia


# TODO: Not sure these are actually helpful
SimpleProcessor = Callable[[Dict[str, Any]], Dict[str, str]]
SimpleMediaProcessor = Callable[[Dict[str, Any]], Tuple[Dict[str, str], CardMedia]]
ManyMediaProcessor = Callable[[Dict[str, Any]], Tuple[Dict[str, str], List[CardMedia]]]


def _inspect_expected_args(func: Callable) -> Tuple[List[str], List[str]]:
    """Derive the key word arguments a processor function expects from its
    own signature, so callers don't have to declare them separately.

    The first parameter is always the card, so it's skipped. Every named
    parameter after it becomes an expected key word argument: one without
    a default is required (hanky raises if it's missing from --args), one
    with a default is optional (only forwarded if --args supplies it,
    otherwise the function's own default applies).

    Args:
        func: the processor callable to inspect

    Returns:
        A ``(required, optional)`` tuple of key word argument names.
    """
    params = list(inspect.signature(func).parameters.values())[1:]
    named = [p for p in params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
    required = [p.name for p in named if p.default is inspect.Parameter.empty]
    optional = [p.name for p in named if p.default is not inspect.Parameter.empty]
    return required, optional


class CardProcessingException(Exception):
    """Raised when a user-defined card processor raises during execution.

    Some info may not be known at construction so we default to None
    and build string lazily.
    """

    def __init__(self, processor, model=None, card=None, *args):
        self.processor = processor
        self.model = model
        self.card = card
        super().__init__(*args)

    def __str__(self) -> str:
        name = getattr(self.processor, "__name__", repr(self.processor))
        return (
            f"Error in card processor '{name}' for model '{self.model}' "
            f"while processing card: {self.card}"
        )


class CardProcessor:
    """The wrapper for user defined functions which processes cards.

    Wraps a python callable which takes a dictionary representing an anki card,
    plus any key word arguments it declares in its own signature (beyond the
    card), and the fields (keys) it assumes to be already present in the card.

    Attributes:
        f: the user defined callable which processes each card
        expected_args: required key word arguments of the callable, derived
            from its signature (parameters with no default)
        optional_args: optional key word arguments of the callable, derived
            from its signature (parameters with a default)
        required_fields: Anki fields expected to be already present in any cards processed
    """

    def __init__(
        self,
        func: Union[SimpleProcessor, SimpleMediaProcessor, ManyMediaProcessor],
        required_fields: List[str],
    ):
        """Initializes a card processor

        Args:
            func: the user defined callable which processes each card. Its
                key word arguments (every parameter after the card) are
                discovered automatically from its signature - see
                :func:`_inspect_expected_args`.
            required_fields: Anki fields expected to be already present in any cards processed
        """

        self.f = func
        self.expected_args, self.optional_args = _inspect_expected_args(func)
        self.required_fields = required_fields

        if not isinstance(self.required_fields, list):
            raise TypeError("'required_fields' must be a list of strings")

    def __call__(self, card: dict, **kwargs) -> Tuple[Dict[str, str], List[CardMedia]]:
        """Check expected fields are present in card and expected key word arguments
        were provided, call the callable on the card and validate output is a dictionary.

        Args:
            card: dictionary representing field, value pairs of an anki card
            **kwargs: key word arguments for the callable

        Returns:
            card dictionary with possibly new fields added by user defined callable

        """
        for k in self.required_fields:
            if k not in card:
                raise KeyError(
                    f"Processor requires '{k}' to be present in card. \n {str(card)}"
                )

        for k in self.expected_args:
            if k not in kwargs:
                name = getattr(self.f, "__name__", repr(self.f))
                raise KeyError(
                    f"Processor '{name}' expects key word argument '{k}'. Ensure it is passed in via the --args option"
                )

        call_args = {k: kwargs[k] for k in self.expected_args}
        call_args.update({k: kwargs[k] for k in self.optional_args if k in kwargs})

        # catch errors in processor and re throw indicating the name of the processor
        try:
            ret = self.f(card, **call_args)
        except Exception as e:
            raise CardProcessingException(self.f, card=card) from e

        # A processor may return any of:
        #   - a card dict                        -> no media
        #   - a (card, CardMedia) tuple          -> a single media item
        #   - a (card, list[CardMedia]) tuple    -> many media items
        if isinstance(ret, dict):
            card = ret
            media: List[CardMedia] = []
        elif isinstance(ret, tuple) and len(ret) == 2:
            card = ret[0]
            if isinstance(ret[1], CardMedia):
                media = [ret[1]]
            else:
                media = ret[1]
        else:
            raise ValueError(
                "Card processor must return a card dict, a tuple of (card, media) "
                "or a tuple of (card, [media,...])"
            )

        # # check we successfully normalised to (card, l
        if not isinstance(card, dict) or not isinstance(media, list):
            raise ValueError(
                "Could not normalise processor return to "
                "type Tuple[Dict[str, str], List[CardMedia]]."
            )

        return card, media
