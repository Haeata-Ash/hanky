# mypy: disable-error-code="import-untyped"

"""Hanky script which turns a photo of printed French text into
English-French flash cards. Each word or phrase marked with a highlighter
is turned into a flash card with the sentence it appeared in as context, English
translations of both, the word's dictionary form where possible, and spoken
French audio of the context sentence.

Requires the French spaCy model, and Google Cloud credentials for a project
with the Cloud Translation API (free tier: 500,000 characters/month) and
Cloud Text-to-Speech API (see https://cloud.google.com/text-to-speech/pricing
for its free tier) both enabled, see https://cloud.google.com/translate:

    python -m spacy download fr_core_news_sm
    gcloud auth application-default login
    # or point GOOGLE_APPLICATION_CREDENTIALS at a service-account key file

Handwriting won't work, although maybe if you are incredibly neat?

Requires that a card model/type called ``lang-vocab-ocr`` has been created
with the fields:
- word
- context
- context-translation
- word-translation
- lemma
- audio

Front of card:
```
 {{ word-translation }}

<br>

 {{ context-translation }}
```

Back of card:
```
{{FrontSide}}

<hr id=answer>

 {{ word }}

<br>

{{ lemma }}

<br>

{{ context }}

<br>

{{ audio }}
```

The image processing, OCR, and lemmatisation all run on device with
lightweight CPU models. Only the translation and speech synthesis steps call
out to cloud services (the Google Cloud Translation and Text-to-Speech APIs).

The pipeline:

  The loader (stages 1-4), registered for .jpg/.jpeg/.png files:
    1. Load the photo and preprocess it so the OCR can read the text
       accurately.
    2. Build a mask of where the highlighter ink is.
    3. OCR the page and keep the words that sit on highlighted areas.
    4. Pair each highlighted word or phrase with the sentence it appeared
       in, which becomes the card's context.

  The card processors:
    5. ``lemmatise`` — write the dictionary form of the highlighted word to
       the "lemma" field, so the card shows something you can look up
       ("cachait" → "cacher"). Left empty when no lemma is found.
    6. ``translate`` — translate the word and its context sentence to
       English with the Google Cloud Translation API.
    7. ``synthesise_speech`` — generate spoken French audio of the
       "context" sentence with the Google Cloud Text-to-Speech API, and
       write a reference to it in the "audio" field.

Run, e.g.:
    python3 demo_highlight_words.py pipe emile_zola.jpg --into french::vocab
"""

import functools
from typing import IO, Dict, List

import cv2
import numpy as np
import spacy
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import texttospeech, translate_v2
from PIL import Image, ImageOps
from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
import matplotlib.pyplot as plt
from hanky import CardMedia, HankyPipeline
from spacy.matcher import PhraseMatcher


# Photos larger than this (longest side, pixels) are scaled down
MAX_DIMENSION = 2500

# Multiplier on the saturation channel's standard deviation used to set the
# highlighter threshold (see create_highlighter_mask): mean + multiplier *
# std, following https://github.com/zirkelc/pyhighlight-ocr. Lower it if
# highlighted words are being missed; raise it if plain paper/text is being
# falsely picked up as highlighted.
HIGHLIGHT_SATURATION_STD_MULTIPLIER = 1.5

# minimum mask coverage of a word box to be considered part of a highlighted
# region
MINIMUM_MASK_COVERAGE_PERCENT = 0.3

DEBUG = False

# Cards translate from French to English.
SOURCE_LANG = "fr"
TARGET_LANG = "en"

# Voice used to synthesise the "context" audio - it's French since that's
# the language context (the original sentence from the page) is written in.
SPEECH_VOICE = texttospeech.VoiceSelectionParams(
    language_code="fr-FR",
    ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
)


# the pipeline
hanky = HankyPipeline("lang-vocab-ocr")


def _display_image(image, title="Image", cmap=None):
    if DEBUG is False:
        return
    plt.figure(figsize=(10, 8))
    if len(image.shape) == 3:  # Color image
        plt.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    else:  # Grayscale image
        plt.imshow(image, cmap="gray")
    plt.title(title)
    plt.axis("off")
    plt.show()


def load_page_photo(f_obj: IO) -> np.ndarray:
    """Read a photo into an OpenCV BGR array.

    Pillow does the reading because phone cameras record the photo's rotation
    as EXIF metadata, which OpenCV silently ignores but ``exif_transpose``
    applies.
    """
    image = ImageOps.exif_transpose(Image.open(f_obj))
    page = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)

    scale = MAX_DIMENSION / max(page.shape[:2])
    if scale < 1:
        page = cv2.resize(page, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return page


@functools.cache
def ocr_engine() -> RapidOCR:
    """Load the OCR model.

    Since constructing RapidOCR loads the ONNX models, downloading them on first use,
     we lazy load which so it doesn't happen just because this module was imported.

    French needs the Latin-script model.
    """
    return RapidOCR(
        params={
            "Rec.lang_type": LangRec.LATIN,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.model_type": ModelType.MOBILE,
            "Global.return_word_box": True,
        }
    )


def normalize_illumination(gray: np.ndarray) -> np.ndarray:
    """Smooth illumination estimate so shadowed and lit text end up with
    comparable contrast. Subtracting didn't really work super well for anything
    that wasn't a nice smooth gradual shadow. Supposedly because shadows can
    be considered as multiplicative shading..."""
    short_side = min(gray.shape[:2])

    # Kernel size for the background estimate, in pixels. It has to be:
    #   - bigger than a character's stroke width, so dilate() erases the
    #     text entirely and what's left approximates "page + lighting"
    #     with no ink left in it
    #   - smaller than the spatial scale a shadow's edge moves across, so
    #     the estimate still tracks *where* the shadow is rather than
    #     blurring straight through it
    # These magic numbers seemed to work so must be about right for a
    # phone...
    k = max(3, (short_side // 25) | 1)

    # remove the text via dilation
    dilated = cv2.dilate(gray, np.ones((k, k), np.uint8))
    _display_image(dilated, "dilated")

    # make the image even smoother via a second, larger median blur. The
    # magical numbers need give a kernel big enough to finish smoothing
    # (so bigger than the previous dilation kernel) but not so big that
    # seperate shadows on the page start being considered together.
    bg = cv2.medianBlur(dilated, (k * 2) | 1)
    _display_image(bg, "background")

    norm = gray.astype(np.float32) / (bg.astype(np.float32) + 1.0)

    # Rescale back to 0-255 using the background's mean brightness as
    # the reference "white point"
    norm = np.clip(norm * bg.mean(), 0, 255).astype(np.uint8)
    _display_image(norm, "illumination normalised")
    return norm


def deskew_image(img: np.ndarray) -> np.ndarray:
    """Rotate a photo so its printed text runs horizontally."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, ink_mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    angle = cv2.minAreaRect(cv2.findNonZero(ink_mask))[2]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    height, width = img.shape[:2]
    rotation = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        img, rotation, (width, height), borderMode=cv2.BORDER_REPLICATE
    )


def prepare_for_ocr(img: np.ndarray) -> np.ndarray:
    """Reduce a deskewed photo to an evenly-lit grayscale image for OCR.

    Deliberately left as continuous grayscale because RapidOCR's model
    is trained on natural photos, not binary ink masks.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return normalize_illumination(blurred)


def create_highlighter_mask(img: np.ndarray) -> np.ndarray:
    """Create masks of highlighter ink regions.

    Inspired by pyhighlight-ocr's detect_highlights
    (https://github.com/zirkelc/pyhighlight-ocr/blob/master/main.py).
    """
    saturation = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
    _display_image(saturation.astype(np.uint8), "saturation")

    # A page is mostly not highlighted, so "highlighted" is whatever is
    # unusually saturated relative to the page
    threshold = (
        saturation.mean() + HIGHLIGHT_SATURATION_STD_MULTIPLIER * saturation.std()
    )
    mask_img = (saturation > threshold).astype(np.uint8) * 255
    _display_image(mask_img, "raw mask")

    # Small bits of noise will be left over so we try to remove regions that are
    # too small to be anything useful.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask_img = cv2.morphologyEx(mask_img, cv2.MORPH_OPEN, kernel)
    _display_image(mask_img, "denoised mask")

    return mask_img


def is_word_highlighted(
    highlight_mask, word_bounding_poly, min_mask_coverage=MINIMUM_MASK_COVERAGE_PERCENT
):
    """Decide if a word box sits on a highlighted region via the mask"""
    word_mask = np.zeros((highlight_mask.shape[0], highlight_mask.shape[1]))
    cv2.fillConvexPoly(word_mask, word_bounding_poly, 255)

    word_part_of_highlight_mask = highlight_mask[word_mask > 0]
    if word_part_of_highlight_mask.size < 1:
        return False

    only_highlight_part_count = np.count_nonzero(word_part_of_highlight_mask > 0)
    only_highlight_part_ratio = (
        only_highlight_part_count / word_part_of_highlight_mask.size
    )

    # if enough of the word is detected to be highlighted, consider the
    # whole word highlighted
    if only_highlight_part_ratio > min_mask_coverage:
        return True
    else:
        return False


def get_highlighted_text(ocr_text, mask):
    """Retrieve all the highlighted text using the mask"""
    higlighted_text_obj = []
    for section in ocr_text.word_results:
        extraction = []
        for word_obj in section:
            poly = word_obj[2]
            bounding_poly = np.array(
                [
                    [poly[0][0], poly[0][1]],
                    [poly[1][0], poly[1][1]],
                    [poly[2][0], poly[2][1]],
                    [poly[3][0], poly[3][1]],
                ]
            )
            if is_word_highlighted(mask, bounding_poly):
                extraction.append(word_obj)
        if extraction:
            higlighted_text_obj.append(extraction)

    return higlighted_text_obj


def match_highlighted_text_to_sentences(
    text: str, higlights: List[str]
) -> List[Dict[str, str]]:
    """Get the context of a highlighted word"""
    nlp = get_nlp()
    phrase_matcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp(text) for text in higlights]
    doc = nlp(text)
    phrase_matcher.add("higlighted", patterns)

    results = []
    for sent in doc.sents:
        for _, start, end in phrase_matcher(nlp(sent.text)):
            span = sent[start:end]
            results.append({"word": span.text, "context": sent.text})

    return results


@functools.cache
def get_nlp() -> spacy.language.Language:
    """Load the French spaCy pipeline (tokenisation, sentence boundaries,
    lemmas). The model is a separate download
    ``python -m spacy download fr_core_news_sm``"""
    try:
        return spacy.load("fr_core_news_sm")
    except OSError as err:
        raise RuntimeError(
            "The French spaCy model is missing. Install it with:\n"
            "    python -m spacy download fr_core_news_sm"
        ) from err


def load_highlighted_words_and_contexts(f_obj: IO):
    # load the image
    img = load_page_photo(f_obj)

    # correct rotation
    rotated = deskew_image(img)

    # do ocr preprocessing, then ocr
    ocr = ocr_engine()
    result = ocr(prepare_for_ocr(rotated))
    text = " ".join(result.txts)

    # do highlight word area preprocessing, create mask
    mask = create_highlighter_mask(rotated)

    # mask ocr'd text to get highlighted words
    highlighted_object_list = get_highlighted_text(result, mask)
    highlights = [
        " ".join(word_obj[0] for word_obj in section)
        for section in highlighted_object_list
    ]

    # get each highlighted section's context, and yield word, context dicts
    yield from match_highlighted_text_to_sentences(text, highlights)


@functools.cache
def translate_client() -> translate_v2.Client:
    """The Cloud Translation client, authenticated with Application Default
    Credentials (the standard Google Cloud SDK mechanism: whatever
    ``gcloud auth application-default login`` stored, or the service-account
    key file named by GOOGLE_APPLICATION_CREDENTIALS)."""
    try:
        return translate_v2.Client()
    except (DefaultCredentialsError, OSError) as err:
        raise RuntimeError(
            "Google Cloud credentials were not found (or name no project)."
            " Run `gcloud auth application-default login`, or point"
            " GOOGLE_APPLICATION_CREDENTIALS at a service-account key file,"
            " for a project with the Cloud Translation API enabled."
        ) from err


@functools.cache
def speech_client() -> texttospeech.TextToSpeechClient:
    """The Cloud Text-to-Speech client, authenticated the same way as
    :func:`translate_client`."""
    try:
        return texttospeech.TextToSpeechClient()
    except (DefaultCredentialsError, OSError) as err:
        raise RuntimeError(
            "Google Cloud credentials were not found (or name no project)."
            " Run `gcloud auth application-default login`, or point"
            " GOOGLE_APPLICATION_CREDENTIALS at a service-account key file,"
            " for a project with the Cloud Text-to-Speech API enabled."
        ) from err


# register the loader against the common photo extensions
for extension in (".jpg", ".jpeg", ".png"):
    hanky.register_loader(extension, load_highlighted_words_and_contexts, is_text=False)


@hanky.card_processor(required_fields=["word", "context"])
def lemmatise(card: dict):
    """Take the word field, lemmatise it, and write the result to the "lemma" field
    so the card shows something you can look up: "cachait" → "cacher". Phrases get an
    empty lemma.

    The word is lemmatised inside its context sentence where possible.
    """
    nlp = get_nlp()
    phrase_matcher = PhraseMatcher(nlp.vocab)
    card["lemma"] = ""
    patterns = [nlp(card["word"])]
    phrase_matcher.add("word", patterns)
    card["lemma"] = ""
    doc = nlp(card["context"])
    for sent in doc.sents:
        for _, start, end in phrase_matcher(nlp(sent.text)):
            span = sent[start:end]
            card["lemma"] = span.lemma_

    return card


@hanky.card_processor(required_fields=["word", "context"])
def translate(card: dict):
    """Write Google translations of the highlighted word and of its context
    sentence to 'word-translation' and 'context-translation' (the front of the
    card). Both strings go in a single API call."""
    results = translate_client().translate(
        # add context to word for better translations
        [card["word"], card["context"]],
        source_language=SOURCE_LANG,
        target_language=TARGET_LANG,
        format_="text",
    )
    card["word-translation"] = results[0]["translatedText"]
    card["context-translation"] = results[1]["translatedText"]
    return card


@hanky.card_processor(required_fields=["context"])
def synthesise_speech(card: dict):
    """Generate spoken French audio of the "context" sentence (the original
    sentence from the page) with Google Cloud Text-to-Speech, add it as anki
    media, then reference it in the "audio" field.
    """
    response = speech_client().synthesize_speech(
        input=texttospeech.SynthesisInput(text=card["context"]),
        voice=SPEECH_VOICE,
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        ),
    )
    speech_media = CardMedia(response.audio_content, ".mp3")
    card["audio"] = speech_media.media_ref
    return card, speech_media


# run the hanky cli application by running this python file, for example:
#   python3 demo_highlight_words.py pipe emile_zola.jpg
if __name__ == "__main__":
    hanky.run()
