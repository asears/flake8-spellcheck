"""Flake8 Spellcheck.

Raises:
    ValueError: [description]

Returns:
    [type]: [description]

Yields:
    [type]: [description]
"""

import os
import re
import tokenize
from string import ascii_lowercase, ascii_uppercase, digits

import pkg_resources

NOQA_REGEX = re.compile(r"#[\s]*noqa:[\s]*[\D]+[\d]+")


def detect_case(name):
    """Really simple detection function.

    Args:
        name ([type]): [description]

    Returns:
        [type]: [description]
    """
    if name.startswith("http"):
        return "url"
    # ignore leading underscores when testing for snake case
    elif "_" in name.lstrip("_"):
        return "snake"
    elif name.isupper():
        return "snake"
    return "camel"


def parse_camel_case(name, position):
    """Parse camel case.

    Args:
        name ([type]): [description]
        position ([type]): [description]

    Yields:
        [type]: [description]
    """
    index = position[1]
    start = index
    buffer = ""
    for character in name:
        index += 1
        if character in ascii_lowercase or character in digits or character == "'":
            buffer += character
        else:
            if buffer:  # noqa: WPS513
                yield (position[0], start), buffer
            if character in ascii_uppercase:
                buffer = character
                start = index - 1
            else:
                buffer = ""
                start = index

    if buffer:
        yield (position[0], start), buffer


def parse_snake_case(name, position):
    """Parse snake case.

    Args:
        name ([type]): [description]
        position ([type]): [description]

    Yields:
        [type]: [description]
    """
    index = position[1]
    start = index
    buffer = ""
    for character in name:
        index += 1
        if character in ascii_lowercase or character in digits or character in ascii_uppercase:
            buffer += character
        else:
            if buffer:  # noqa: WPS513
                yield (position[0], start), buffer

            buffer = ""
            start = index

    if buffer:
        yield (position[0], start), buffer


def is_number(token):
    """Is number.

    Args:
        token ([type]): [description]

    Returns:
        [type]: [description]
    """
    try:
        float(token)
    except ValueError:
        return False
    else:
        return True


def get_code(token_type):
    """Get code.

    Args:
        token_type ([type]): Token type

    Raises:
        ValueError: Unknown token_type

    Returns:
        str: SC100 for token_type COMMENT, SC200 for token_type NAME.
    """
    if token_type == tokenize.COMMENT:
        return "SC100"
    elif token_type == tokenize.NAME:
        return "SC200"
    raise ValueError("Unknown token_type {0}".format(token_type))


class SpellCheckPlugin:  # noqa: WPS306
    """SpellCheckPlugin.

    Returns:
        [type]: [description]

    Yields:
        [type]: [description]
    """

    name = "flake8-spellcheck"
    version = "0.20.0"

    def __init__(self, tree, filename="(none)", file_tokens=None):  # noqa: WPS210
        """Init SpellCheckPlugin.

        Args:
            tree (any): Unused
            filename (str, optional): [description]. Defaults to "(none)".
            file_tokens ([type], optional): [description]. Defaults to None.
        """
        self.file_tokens = file_tokens

        self.words = set()
        for dictionary in self.dictionaries:
            dictionary_data = pkg_resources.resource_string(__name__, dictionary)
            dictionary_data = dictionary_data.decode("utf8")
            self.words |= set(word.lower() for word in dictionary_data.split("\n"))  # noqa: C401

        # legacy
        if os.path.exists(self.whitelist_path):
            with open(self.whitelist_path, "r") as whitelist_file:
                allowlist = whitelist_file.read()

            allowlist = set(word.lower() for word in allowlist.split("\n"))  # noqa: C401
            self.words |= allowlist

        if os.path.exists(self.allowlist_path):
            with open(self.allowlist_path, "r") as allowlist_file:
                allowlist = allowlist_file.read()

            allowlist = set(word.lower() for word in allowlist.split("\n"))  # noqa: C401
            self.words |= allowlist

        # Hacky way of getting dictionary with symbols stripped
        self.no_symbols = set()
        for word in self.words:
            if word.endswith("'s"):
                self.no_symbols.add(word.replace("'s", ""))
            else:
                self.no_symbols.add(word.replace("'", ""))

    @classmethod
    def add_options(cls, parser):
        """Add options.

        Args:
            parser ([type]): [description]
        """
        parser.add_option(
            "--allowlist",
            help="Path to text file containing allowed words",
            default="allowlist.txt",
            parse_from_config=True,
        )
        parser.add_option(
            "--whitelist",
            help="(Legacy) Path to text file containing allowed words",
            default="whitelist.txt",
            parse_from_config=True,
        )
        parser.add_option(
            "--dictionaries",
            # Unfortunately optparse does not support nargs="+" so we
            # need to use a command separated list to work round it
            help="Command separated list of dictionaries to enable",
            default="en_US,python,technical",
            comma_separated_list=True,
            parse_from_config=True,
        )
        parser.add_option(
            "--spellcheck-targets",
            help="Specify the targets to spellcheck",
            default="names,comments",
            comma_separated_list=True,
            parse_from_config=True,
        )

    @classmethod
    def parse_options(cls, options):
        """Parse options.

        Args:
            options ([type]): Argparse options
        """
        cls.allowlist_path = options.allowlist
        cls.whitelist_path = options.whitelist
        cls.dictionaries = ["".join([dicts, ".txt"]) for dicts in options.dictionaries]
        cls.spellcheck_targets = set(options.spellcheck_targets)

    def run(self):
        """Run.

        Yields:
            [type]: [description]
        """
        for token_info in self.file_tokens:
            yield from self._parse_token(token_info)

    def _detect_errors(self, tokens, use_symbols, token_type):
        """Detect errors.

        Args:
            tokens ([type]): [description]
            use_symbols (bool): [description]
            token_type ([type]): [description]

        Yields:
            [type]: [description]
        """
        code = get_code(token_type)

        for position, token in tokens:
            test_token = token.lower().strip("'").strip('"')

            if use_symbols:
                valid = test_token in self.words
            else:
                valid = test_token in self.no_symbols

            # Need a way of matching words without symbols
            if not valid and not is_number(token):
                yield (
                    position[0],
                    position[1],
                    "{} Possibly misspelt word: '{}'".format(code, token),
                    type(self),
                )

    def _is_valid_comment(self, token_info):
        """Is valid comment.

        Args:
            token_info ([type]): Token info.

        Returns:
            [type]: [description]
        """
        return (
            token_info.type == tokenize.COMMENT
            and "comments" in self.spellcheck_targets
            # Ensure comment is non-empty, github.com/MichaelAquilina/flake8-spellcheck/issues/34
            and token_info.string.strip() != "#"
            # Ignore flake8 pragma comments
            and token_info.string.lstrip("#").split()[0] != "noqa:"
        )

    def _parse_token(self, token_info):  # noqa: WPS210, WPS231
        """Parse token.

        Check for valid comments, remove lint comments.

        Args:
            token_info ([type]): Token info.

        Returns:
            str: Parsed token.  Name or cleansed comment.

        Yields:
            tuple: error tuple
        """
        if token_info.type == tokenize.NAME and "names" in self.spellcheck_targets:
            value = token_info.string  # noqa: WPS110
        elif self._is_valid_comment(token_info):
            # strip out all `noqa: [code]` style comments so they aren't erroneously checked
            # see https://github.com/MichaelAquilina/flake8-spellcheck/issues/36 for info
            value = NOQA_REGEX.sub("", token_info.string.lstrip("#"))  # noqa: WPS110
        else:
            return

        tokens = []
        for word in value.split(" "):
            case = detect_case(word)
            if case == "url":
                # Nothing to do here
                continue
            elif case == "snake":
                tokens.extend(parse_snake_case(word, token_info.start))
            elif case == "camel":
                tokens.extend(parse_camel_case(word, token_info.start))

        use_symbols = False
        if token_info.type == tokenize.NAME:
            use_symbols = False
        elif token_info.type == tokenize.COMMENT:
            use_symbols = True

        for error_tuple in self._detect_errors(tokens, use_symbols, token_info.type):  # noqa: WPS526
            yield error_tuple
