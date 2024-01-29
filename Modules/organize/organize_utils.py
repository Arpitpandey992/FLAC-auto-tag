import os
import re

forbiddenCharacters = {
    "<": "ᐸ",
    ">": "ᐳ",
    ":": "꞉",
    '"': "ˮ",
    "'": "ʻ",
    # '/': '／', # Looks far too stretched, but is more popular for some reason
    "/": "Ⳇ",  # This one looks more natural
    "\\": "∖",
    "|": "ǀ",
    "?": "ʔ",
    "*": "∗",
    "+": "＋",
    "%": "٪",
    "!": "ⵑ",
    "`": "՝",
    "&": "&",  # keeping same as it is not forbidden, but it may cause problems
    "{": "❴",
    "}": "❵",
    "=": "᐀",
    "~": "～",  # Not using this because it could be present in catalog number as well, may cause problems though
    "#": "#",  # couldn't find alternative
    "$": "$",  # couldn't find alternative
    "@": "@",  # couldn't find alternative
}


def clean_name(name: str) -> str:
    output = name.strip()
    for invalidCharacter, validAlternative in forbiddenCharacters.items():
        output = output.replace(invalidCharacter, validAlternative)
    return output


def get_base_folder_under_parent(file_path: str, parent_directory: str) -> str | None:
    """
    extract the middle level folder if exists
    for example:
    shakespeare/poems/mariner.wav -> poems
    touhou/opening_theme.flac -> `None`  # Because there is no folder at depth 1
    """
    relative_path = os.path.relpath(os.path.normpath(file_path), os.path.normpath(parent_directory))
    base_dir = os.path.dirname(relative_path)
    return base_dir if base_dir not in ["", ".", "/"] else None


def extract_disc_name_from_folder_name(disc_folder_name: str | None) -> str | None:
    """
    extract the name from a folder representing a disc
    for example:
    CD01: Ryme of the Ancient Mariner -> Ryme of the Ancient Mariner
    Disc 01 - Et tu, Brute? -> Et tu, Brute
    1. Damn son -> Damn Son
    Disc3 -> `None`
    yooo -> `None`  [Because we expect disc name to have a number as well]
    """
    matches = _split_disc_folder_name(disc_folder_name)
    return matches.get("disc_name", None)


def extract_disc_number_from_folder_name(disc_folder_name: str | None) -> int | None:
    """
    extract the name from a folder representing a disc
    for example:
    CD01: Ryme of the Ancient Mariner -> 01
    Disc 01 - Et tu, Brute? -> 01
    Damn son -> `None`
    Disc3 -> 3
    """
    disc_number = _split_disc_folder_name(disc_folder_name).get("disc_number", None)
    return int(disc_number) if disc_number and disc_number.isdigit() else None


def extract_track_number_from_file_name(file_name: str | None) -> int | None:
    """
    extracts file number from file names for audio files
    for example:
    01. track 1.flac -> 1
    122 - damn.mp3 -> 122
    file.aac -> `None`
    3 author.m4a -> 3
    14 -> 14
    """
    if not file_name:
        return None


def extract_track_name_from_file_name(file_name_full: str) -> str | None:
    """
    extracts file number from file names for audio files (without extension)
    for example:
    01. track 1.flac -> track 1
    122 - damn.mp3 -> damn
    file.aac -> file
    3 author.m4a -> author
    14 -> `None`
    """
    file_name, _ = os.path.splitext(file_name_full)
    return file_name.strip()


def _split_disc_folder_name(disc_folder_name: str | None) -> dict[str, str | None]:
    if not disc_folder_name:
        return {}
    separators = ":-. _~"
    separators += clean_name(separators)
    separators = "".join(set(separators))
    disc_names = ["disc", "cd", "dvd", ""]
    spaces = " *"
    pattern = f"^{spaces}({'|'.join(disc_names)}){spaces}([0-9]+){spaces}([{re.escape(separators)}])(.*)$"
    matches = re.findall(pattern, disc_folder_name, re.IGNORECASE)
    if len(matches) == 0:
        return {}
    return {
        "disc_number": matches[0][1].strip() if matches[0][1].strip() else None,
        "disc_name": matches[0][3].strip() if matches[0][3].strip() else None,
    }


if __name__ == "__main__":
    test_disc_names = [
        "disc01- what da dog doin?",
        "cd 4 : damn",
        "6.    disc name   .",
        " 8 ",
        "  Disc 003.  ",
        "  DIsc 003.  disc 005 - damn boi",
        "CD - huh",
        "CD 55- huh",
        "Diks 3        :  disc name?",
        "      Disc   3        :  disc name?",
    ]
    for disc_folder_name in test_disc_names:
        print(f'foldername: "{disc_folder_name}"\ndisc number: "{extract_disc_number_from_folder_name(disc_folder_name)}"\ndisc name: "{extract_disc_name_from_folder_name(disc_folder_name)}"\n\n')
