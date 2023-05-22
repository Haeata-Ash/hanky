# hanki
Tool to create and update Anki Decks for language learning


## Setup

This tool requires anki has been installed.

To install the python requirements, run `pip install -r requirements.txt` at the root of the project.

A yaml config file with must be provided with the path to the anki database (collection) file. On my computer (mac) it is located at `~/Library/Application Support/Anki2/User 1/collection.anki2`. If no path to a config file is given to the cli, it is assumed that there is a config file named `config.yaml` present at the root of this project. An example config file has been provided.

This tool requires an aws account and account credentials to be used. It uses the aws service [Amazon Polly](https://aws.amazon.com/polly/). You will need to create an aws account and setup the [aws cli](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html) (the credentials will be used to interact with the aws api via the boto3 library). AWS Polly provideds millions of characters per month free so for a single user, no cost should be incurred when making cards.

## Usage
**Warning:** This tool should not be used while anki is running on the same computer (it will throw an exception if you try) due to possible damage to database (although unlikely)

There are two available models:

*CONJUGATION_MODEL* -> This model places the source lang on the front of the card and the target languages speech and text on the back. Only one card is created for a given note using this model.

*LANGUAGE_MODEL* -> This model creates two cards per note. One card has the only the target lang speech, with the target and source lang text on the back, while the other has the source lang text on the front and the target lang speech and text on the back.

Using the *CONJUGATION_MODEL*:
`python3 ankigen.py --deck-name "MyGermanDeck" --model lang-recall --lang German -i "~/Path/To/Excel/Spreadsheet/ExampleGermanSpreadsheet.xlsx"`

Using the *LANGUAGE_MODEL*:
`python3 ankigen.py --deck-name "French::Phrases" --model lang-understand --lang French -i "Phrases.xlsx"`

An example spreadsheet has been provided.
