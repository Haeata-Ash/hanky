# mypy: disable-error-code="import-untyped"

"""Example hanky script which turns a photo of a printed French page into
French→English flash cards: each word or phrase marked with a highlighter pen
becomes a card with the sentence it appeared in as context, English
translations of both, and the word's dictionary form (lemma) when spaCy can
find one.

Requires that a card model/type called ``lang-vocab-ocr`` has been created
with the fields:
- word
- context
- context-translation
- word-translation
- lemma (possibly empty)

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
```

The image processing, OCR, and lemmatisation all run on device with
lightweight CPU models; only the translation step calls out to a cloud
service (the Google Cloud Translation API).

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

Requires the French spaCy model, and Google Cloud credentials for a project
with the Cloud Translation API enabled (its free tier covers 500,000
characters per month, see https://cloud.google.com/translate):

    python -m spacy download fr_core_news_sm
    gcloud auth application-default login
    # or point GOOGLE_APPLICATION_CREDENTIALS at a service-account key file

Handwriting won't work (unless you are incredibly neat), the OCR model reads
printed text.

Run, e.g.:
    python3 demo_highlight_words.py pipe emile_zola.jpg --into french::vocab
"""

import functools
from typing import IO, Dict, List

import cv2
import numpy as np
import spacy
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import translate_v2
from PIL import Image, ImageOps
from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR
import matplotlib.pyplot as plt
from hanky import HankyPipeline
from spacy.matcher import PhraseMatcher


# Photos larger than this (longest side, pixels) are scaled down
MAX_DIMENSION = 2500

DEBUG = False

# Cards translate from French to English.
SOURCE_LANG = "fr"
TARGET_LANG = "en"


def display_image(image, title="Image", cmap=None):
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


def preprocess(img: np.ndarray):
    # convert to grayscale
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # display_image(img_gray, "gray")

    # gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
    # display_image(blurred, "blurred")

    dilated = cv2.dilate(blurred, np.ones((7, 7), np.uint8))
    # display_image(dilated, "dilated")

    bg = cv2.medianBlur(dilated, 21)
    # display_image(bg, "background")

    # Calculate the difference between the original and the background we just obtained.
    # The bits that are identical will be black (close to 0 difference), the text will be white (large difference).
    # Since we want black on white, we invert the result.
    diff_img = 255 - cv2.absdiff(blurred, bg)

    # Normalize background to [0, 255]
    background_normalized = diff_img.copy()
    background_normalized = cv2.normalize(
        diff_img,
        background_normalized,
        alpha=0,
        beta=255,
        norm_type=cv2.NORM_MINMAX,
        dtype=cv2.CV_8UC1,
    )
    # display_image(background_normalized, "background normalised")

    _, img_thresh = cv2.threshold(
        background_normalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # display_image(img_thresh, "threshold")

    ink_pixels = cv2.findNonZero(img_thresh)
    angle = cv2.minAreaRect(ink_pixels)[2]
    if angle < -45:  # adjust angle
        angle = -(90 + angle)
    else:
        angle = -angle

    height, width = img.shape[:2]
    rotation = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        img, rotation, (width, height), borderMode=cv2.BORDER_REPLICATE
    ), cv2.warpAffine(
        img_thresh, rotation, (width, height), borderMode=cv2.BORDER_REPLICATE
    )


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
    """Load the OCR model lazily: constructing RapidOCR loads the ONNX models
    (downloading them on first use), which shouldn't happen just because this
    module was imported.

    RapidOCR's default recognition model only knows Chinese and English glyphs
    and mangles accents (é, è, â, ç...), so French needs the Latin-script
    model.
    """
    return RapidOCR(
        params={
            "Rec.lang_type": LangRec.LATIN,
            "Rec.ocr_version": OCRVersion.PPOCRV5,
            "Rec.model_type": ModelType.MOBILE,
            "Global.return_word_box": True,
        }
    )


def create_highlighter_mask(img: np.ndarray) -> np.ndarray:
    ycrbc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    display_image(ycrbc, "colour change")
    ycrbc[:, :, 0] = cv2.equalizeHist(ycrbc[:, :, 0])
    equalized_img = cv2.cvtColor(ycrbc, cv2.COLOR_YCrCb2BGR)
    display_image(equalized_img, "hist equalisation")

    for column in equalized_img:
        for pixel in column:
            min_color = min(pixel[0], pixel[1], pixel[2])
            max_color = max(pixel[0], pixel[1], pixel[2])
            pixel[0] = max_color - min_color
            pixel[1] = pixel[0]
            pixel[2] = pixel[0]

    grey = cv2.cvtColor(equalized_img, cv2.COLOR_BGR2GRAY)
    _, mask_img = cv2.threshold(grey, 0, 255, cv2.THRESH_OTSU)
    display_image(mask_img)
    return mask_img


def is_word_highlighted(highlight_mask, word_bounding_poly):
    word_mask = np.zeros((highlight_mask.shape[0], highlight_mask.shape[1]))
    cv2.fillConvexPoly(word_mask, word_bounding_poly, 255)

    word_part_of_highlight_mask = highlight_mask[word_mask > 0]
    if word_part_of_highlight_mask.size < 1:
        return False

    only_highlight_part_count = np.count_nonzero(word_part_of_highlight_mask > 0)
    only_highlight_part_ratio = (
        only_highlight_part_count / word_part_of_highlight_mask.size
    )

    # if at least 30% of the word is detected to be highlighted,
    # then consider the whole word to be highlighted
    if only_highlight_part_ratio > 0.3:
        return True
    else:
        return False


def get_highlighted_text(ocr_text, mask):
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


def load_photo_words_and_contexts(f_obj: IO):
    # read the image
    img = load_page_photo(f_obj)

    # do some preprocessing to ensure text is readable
    rotated_img, preprocessed = preprocess(img.copy())

    # use ocr to get all text from photo
    ocr = ocr_engine()
    result = ocr(preprocessed)

    # join all the lines together
    lines = [line for line in result.txts]
    text = " ".join(lines)

    # make masks for highlighted areas
    mask = create_highlighter_mask(img.copy())

    # pull out all text which highlighted
    higlighted_object_list = get_highlighted_text(result, mask)
    higlights = []
    for section in higlighted_object_list:
        higlights.append(" ".join([x[0] for x in section]))

    yield from match_highlighted_text_to_sentences(text, higlights)


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


hanky = HankyPipeline("lang-vocab-ocr")

# register the loader against the common photo extensions
for extension in (".jpg", ".jpeg", ".png"):
    hanky.register_loader(extension, load_photo_words_and_contexts, is_text=False)


@hanky.card_processor(expected_args=[], required_fields=["word", "context"])
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


@hanky.card_processor(expected_args=[], required_fields=["word", "context"])
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


# run the hanky cli application by running this python file, for example:
#   python3 demo_highlight_words.py pipe emile_zola.jpg
if __name__ == "__main__":
    hanky.run()
