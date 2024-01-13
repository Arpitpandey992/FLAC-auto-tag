import os
from typing import Optional
from typing_extensions import TypedDict
from tabulate import tabulate
from mutagen.flac import StreamInfo
from Imports.config import Config
from Modules.Mutagen.mutagenWrapper import supportedExtensions
from Utility.audioUtils import getFolderTrackData, getOneAudioFile
from Utility.generalUtils import cleanName, fixDate, getProperCount, printAndMoveBack
from Modules.Mutagen.mutagenWrapper import AudioFactory, IAudioManager
from Utility.template import TemplateResolver
from Utility.generalUtils import get_default_logger

FOLDER_NAMING_TEMPLATE = {
    "default": "{[{date}] }{albumname}{ [{catalog}]}{ [{format}]}",
    "catalog_first": "{[{catalog}] }{albumname}{ [{date}]}{ [{format}]}",
    "same_folder_name_default": "{[{date}] }{foldername}{ [{catalog}]}{ [{format}]}",
    "same_folder_name_catalog_first": "{[{catalog}] }{foldername}{ [{date}]}{ [{format}]}",
}


def get_folder_naming_template(folder_naming_template: Optional[str], catalog_first: bool, same_folder_name: bool) -> str:
    if folder_naming_template:
        TemplateResolver.validateTemplate(folder_naming_template)
        return folder_naming_template
    elif catalog_first:
        return FOLDER_NAMING_TEMPLATE["same_folder_name_catalog_first"] if same_folder_name else FOLDER_NAMING_TEMPLATE["catalog_first"]
    return FOLDER_NAMING_TEMPLATE["same_folder_name_default"] if same_folder_name else FOLDER_NAMING_TEMPLATE["catalog_first"]


logger = get_default_logger(__name__, "info")


class TableData(TypedDict):
    table_data: list[tuple]
    headers: list[str]
    colalign: tuple
    maxcolwidths: int
    tablefmt: str


class RenameOptions(TypedDict):
    folder_path: str
    recur: bool
    verbose: bool
    folder_naming_template: str
    results_table: list[TableData]
    pause_on_update: bool


def rename(
    folder_path: str,
    recur: bool = False,
    verbose: bool = True,
    folder_naming_template: Optional[str] = None,
    catalog_first: bool = False,
    same_folder_name: bool = False,
    pause_on_update: bool = False,
):
    folder_naming_template = get_folder_naming_template(folder_naming_template, catalog_first, same_folder_name)
    results_table = []
    rename_options: RenameOptions = {"folder_path": folder_path, "recur": recur, "verbose": verbose, "folder_naming_template": folder_naming_template, "results_table": results_table, "pause_on_update": pause_on_update}


def _rename(rename_options: RenameOptions):
    for item in os.listdir(rename_options["folder_path"]):
        totalTracks = countAudioFiles(folderPath)
        if recur and os.path.isdir(item):
            renameFilesInternal(item, verbose, pauseOnFinish, recur, tableData)


def countAudioFiles(folderPath: Optional[str] = None, folderTrackData: Optional[dict[int, dict[int, str]]] = None) -> int:
    """
    count the number of audio files present inside a directory (not recursive),
    or return the count of tracks given in folderTrackData format
    """
    if folderTrackData:
        return sum([len(tracks) for _, tracks in folderTrackData.items()])
    if folderPath:
        count = 0
        for filename in os.listdir(folderPath):
            _, extension = os.path.splitext(filename)
            if extension.lower() in supportedExtensions:
                count += 1
        return count
    return 0


def deduceAudioDetails(audio: IAudioManager) -> str:
    extension = audio.getExtension()
    # Flac contains most info variables, hence using it here for type hints only
    info: StreamInfo = audio.getInfo()  # type:ignore
    if extension in [".flac", ".wav"]:
        format = "FLAC" if extension == ".flac" else "WAV"
        bits = info.bits_per_sample
        sample_rate = info.sample_rate / 1000
        if sample_rate.is_integer():
            sample_rate = int(sample_rate)
        source = "CD" if bits == 16 else "WEB"
        if sample_rate >= 192 or bits > 24:
            source = "VINYL"  # Scuffed way, but assuming Vinyl rips have extremely high sample rate, but Qobuz does provide 192kHz files so yeah...
        # Edge cases should be edited manually later
        return f"{source}-{format} {bits}bit {sample_rate}kHz"
    elif extension == ".mp3":
        # CD-MP3 because in 99% cases, an mp3 album is a lossy cd rip
        bitrate = int(info.bitrate / 1000)
        return f"CD-MP3 {bitrate}kbps"
    elif extension == ".m4a":
        # aac files are usually provided by websites directly for lossy versions. apple music files are also m4a
        bitrate = int(info.bitrate / 1000)
        return f"WEB-AAC {bitrate}kbps"
    elif extension == ".ogg":
        # Usually from spotify
        bitrate = int(info.bitrate / 1000)
        return f"WEB-OGG {bitrate}kbps"
    elif extension == ".opus":
        # YouTube bruh, couldn't figure out a way to retrieve bitrate
        return f"YT-OPUS"
    return ""


def renameAlbumFolder(folderPath: str, renameTemplate: str) -> None:
    """rename a folder contains exactly ONE album"""

    filePath = getOneAudioFile(folderPath)
    if not filePath:
        logger.error("no audio file in directory!, aborting")
        return

    audio = AudioFactory.buildAudioManager(filePath)
    folderName = os.path.basename(folderPath)
    albumName = audio.getAlbum()
    if albumName is None and "foldername" not in renameTemplate.lower():
        logger.error(f"no album Name in {filePath}, aborting!")
        return
    date = fixDate(audio.getDate())
    if not date:
        date = fixDate(audio.getCustomTag("year"))
    if date:
        date = date.replace("-", ".")

    templateMapping: dict[str, Optional[str]] = {"albumname": albumName, "catalog": audio.getCatalog(), "date": date, "foldername": folderName, "barcode": audio.getCustomTag("barcode"), "format": deduceAudioDetails(audio)}

    templateResolver = TemplateResolver(templateMapping)
    newFolderName = templateResolver.evaluate(renameTemplate)
    newFolderName = cleanName(newFolderName)

    baseFolderPath = os.path.dirname(folderPath)
    newFolderPath = os.path.join(baseFolderPath, newFolderName)
    if folderName != newFolderName:
        if os.path.exists(newFolderPath):
            logger.error(f"{newFolderName} exists, cannot rename {folderName}")
        else:
            os.rename(folderPath, newFolderPath)
            logger.info(f"rename: {folderName} => {newFolderName}")


def renameAlbumFiles(folderPath: str, noMove: bool = False, verbose: bool = False):
    """Rename all files present inside a directory which contains files corresponding to ONE album only"""
    folderTrackData = getFolderTrackData(folderPath)
    totalDiscs = len(folderTrackData)

    tableData = []
    for discNumber, tracks in folderTrackData.items():
        totalTracks = len(tracks)
        isSingle = totalTracks == 1
        for trackNumber, filePath in tracks.items():
            fullFileName = os.path.basename(filePath)
            fileName, extension = os.path.splitext(fullFileName)

            audio = AudioFactory.buildAudioManager(filePath)
            title = audio.getTitle()
            if not title:
                logger.error(f"title not present in file: {fileName}, skipped!")
                continue

            trackNumberStr = getProperCount(trackNumber, totalTracks)
            discNumberStr = getProperCount(discNumber, totalDiscs)

            oldName = fullFileName

            if isSingle:
                newName = f"{cleanName(f'{title}')}{extension}"
            else:
                newName = f"{cleanName(f'{trackNumberStr} - {title}')}{extension}"
            discName = audio.getDiscName()

            if discName:
                discFolderName = f"Disc {discNumber} - {discName}"
            else:
                discFolderName = f"Disc {discNumber}"

            if totalDiscs == 1 or noMove:
                discFolderName = ""
            discFolderPath = os.path.join(folderPath, discFolderName)
            if not os.path.exists(discFolderPath):
                os.makedirs(discFolderPath)
            newFilePath = os.path.join(discFolderPath, newName)
            if filePath != newFilePath:
                try:
                    if os.path.exists(newFilePath):
                        logger.error(f"{newFilePath} exists, cannot rename {fileName}")
                    else:
                        os.rename(filePath, newFilePath)
                        printAndMoveBack(f"renamed: {newName}")
                        tableData.append((discNumberStr, trackNumberStr, oldName, os.path.join(discFolderName, newName)))

                except Exception as e:
                    logger.exception(f"cannot rename {fileName}\n{e}")
    printAndMoveBack("")
    if verbose and tableData:
        logger.info("files renamed as follows:")
        tableData.sort()
        logger.info("\n" + tabulate(tableData, headers=["Disc", "Track", "Old Name", "New Name"], colalign=("center", "center", "left", "left"), maxcolwidths=50, tablefmt=Config().tableFormat))


def renameFilesInternal(folderPath, verbose: bool, pauseOnFinish: bool, recur: bool, tableData: list):
    """
    Rename all files recursively or iteratively in a directory.
    Considers no particular relatioship between files (unlike the albumRename function)
    Does not move files (in Disc folders or anything)
    Use for general folders containing files from various albums
    """
    for item in os.listdir(folderPath):
        totalTracks = countAudioFiles(folderPath)
        if recur and os.path.isdir(item):
            renameFilesInternal(item, verbose, pauseOnFinish, recur, tableData)
        else:
            file = item
            _, extension = os.path.splitext(file)
            if extension.lower() not in supportedExtensions:
                logger.info(f"{file} has unsupported extension ({extension})")
                continue
            filePath = os.path.join(folderPath, file)
            audio = AudioFactory.buildAudioManager(filePath)

            title = audio.getTitle()
            if not title:
                logger.info(f"title not present in {file}, skipping!")
                continue
            artist = audio.getArtist()
            date = fixDate(audio.getDate())
            if not date:
                date = fixDate(audio.getCustomTag("year"))
            if date:
                date = date.replace("-", ".")
            year = date[:4] if date and len(date) >= 4 else ""
            oldName = file
            names = {1: f"{artist} - {title}{extension}" if artist else f"{title}{extension}", 2: f"{title}{extension}", 3: f"[{date}] {title}{extension}", 4: f"[{year}] {title}{extension}"}
            multiTrackName, singleTrackName = 2, 2

            # Change the naming template here :
            # Single here means that the folder itself contains only one file
            isSingle = totalTracks == 1
            nameChoice = singleTrackName if isSingle else multiTrackName

            newName = cleanName(names[nameChoice])

            newFilePath = os.path.join(folderPath, newName)
            if oldName != newName:
                try:
                    if os.path.exists(newFilePath):
                        logger.error(f"{newFilePath} exists, cannot rename {file}")
                    else:
                        os.rename(filePath, newFilePath)
                        printAndMoveBack(f"renamed : {newName}")
                        tableData.append((len(tableData) + 1, oldName, newName))
                except Exception as e:
                    logger.exception(f"cannot rename {file}\n{e}")


def organizeAlbum(folderPath: str, folderNamingtemplate: str, pauseOnFinish: bool = False):
    """Organize a folder which represents ONE album"""
    renameAlbumFiles(folderPath, verbose=True)
    renameAlbumFolder(folderPath, folderNamingtemplate)
    if pauseOnFinish:
        input("Press Enter to continue...")


def organizeFiles(folderPath: str, verbose: bool = True, pauseOnFinish: bool = False, recur: bool = False):
    tableData = []
    renameFilesInternal(folderPath, verbose, pauseOnFinish, recur, tableData)

    printAndMoveBack("")
    if verbose and tableData:
        logger.info("files renamed as follows:")
        tableData.sort()
        logger.info("\n" + tabulate(tableData, headers=["S.no", "Old Name", "New Name"], colalign=("center", "left", "left"), maxcolwidths=45, tablefmt=Config().tableFormat))
    if pauseOnFinish:
        input("Press Enter to continue...")
