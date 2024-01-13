import os
import argparse
import shutil
import json
from typing import Optional
from tabulate import tabulate


from Imports.config import Config
from Modules.Rename.utils import renameAlbumFiles, renameAlbumFolder
from Utility.generalUtils import get_default_logger, getBest, yesNoUserInput, fixDate, cleanSearchTerm

from Modules.Tag.tagFiles import tagFiles
from Utility.audioUtils import getSearchTermAndDate, getAlbumTrackData, getFolderTrackData, doTracksAlign
from Modules.VGMDB.vgmdbrip.vgmdbrip import downloadScans, downloadScansNoAuth

from Modules.VGMDB.models.vgmdb_album_data import VgmdbAlbumData
from Modules.VGMDB.models.search import SearchAlbumData
from Utility.template import TemplateResolver, TemplateValidationException
from Modules.VGMDB.api.client import getAlbumDetails, searchAlbum

logger = get_default_logger("albumTagger")


def argumentParser() -> tuple[argparse.Namespace, Config, str]:
    parser = argparse.ArgumentParser(description="Automatically Tag Music folders using data from VGMDB.net!")

    parser.add_argument("folderPath", type=str, help="Album directory path (Required Argument)")

    parser.add_argument("--id", "-i", type=str, default=None, help="Provide Album ID")
    parser.add_argument("--search", "-s", type=str, default=None, help="Provide Custom Search Term")

    parser.add_argument("--no-title", dest="no_title", action="store_true", help="Do not change the title of tracks")
    parser.add_argument("--keep-title", dest="keep_title", action="store_true", help="keep the current title as well, and add other available titles")
    parser.add_argument("--same-folder-name", dest="same_folder_name", action="store_true", help="While renaming the folder, use the current folder name instead of getting it from album name")
    parser.add_argument("--no-auth", dest="no_auth", action="store_true", help="Do not authenticate for downloading Scans")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip Yes prompt, and when only 1 album comes up in search results")
    parser.add_argument("--no-input", dest="no_input", action="store_true", help="Go full auto mode, and only tag those albums where no user input is required!")
    parser.add_argument("--backup", "-b", action="store_true", help="Backup the albums before modifying")
    parser.add_argument("--no-scans", dest="no_scans", action="store_true", help="Do not download Scans")
    parser.add_argument("--no-pics", dest="no_pics", action="store_true", help="Do not embed album cover into files")
    parser.add_argument("--pic-overwrite", dest="pic_overwrite", action="store_true", help="overwrite album cover within files")

    parser.add_argument("--rename-folder", dest="rename_folder", action="store_true", help="Rename the containing folder")
    parser.add_argument("--no-rename-folder", dest="no_rename_folder", action="store_true", help="Do not Rename the containing folder?")
    parser.add_argument("--rename-files", dest="rename_files", action="store_true", help="rename the files")
    parser.add_argument("--no-rename-files", dest="no_rename_files", action="store_true", help="Do not rename the files")
    parser.add_argument("--tag", dest="tag", action="store_true", help="tag the files")
    parser.add_argument("--no-tag", dest="no_tag", action="store_true", help="Do not tag the files")
    parser.add_argument("--no-modify", dest="no_modify", action="store_true", help="Do not modify the files or folder in any way")
    parser.add_argument("--one-lang", dest="one_lang", action="store_true", help="Only keep the best names")
    parser.add_argument("--translate", dest="translate", action="store_true", help="Translate all text to english")
    parser.add_argument(
        "--album-data-only", dest="album_data_only", action="store_true", help="Only tag album specific details to ALL files in the folder, this option will tag those files as well which are not matching with any track in albumData received from VGMDB. Thus, this is a dangerous option, be careful"
    )

    parser.add_argument("--single", action="store_true", help="enable this if there is only one track in the album")
    parser.add_argument("--performers", action="store_true", help="tag performers in the files")
    parser.add_argument("--arrangers", action="store_true", help="tag arrangers in the files")
    parser.add_argument("--composers", action="store_true", help="tag composers in the files")
    parser.add_argument("--lyricists", action="store_true", help="tag lyricists in the files")

    parser.add_argument("--japanese", "-ja", action="store_true", help="Give Priority to Japanese")
    parser.add_argument("--english", "-en", action="store_true", help="Give Priority to English")
    parser.add_argument("--romaji", "-ro", action="store_true", help="Give Priority to Romaji")

    parser.add_argument("--folder-naming-template", dest="folder_naming_template", type=str, default=None, help='Give a folder naming template like "{[{catalog}] }{albumname}{ [{date}]}"')
    parser.add_argument("--ksl", action="store_true", help="for KSL folder, (custom setting), keep catalog first in naming")

    args = parser.parse_args()

    folderPath: str = args.folderPath

    while folderPath[-1] == "/":
        folderPath = folderPath[:-1]

    flags = Config()
    if args.japanese:
        flags.language_order = ["japanese", "romaji", "english"]
    elif args.english:
        flags.language_order = ["english", "romaji", "japanese"]
    elif args.romaji:
        flags.language_order = ["romaji", "english", "japanese"]

    if args.yes:
        flags.yes_to_all = True
    if args.no_input:
        flags.NO_INPUT = True
    if args.backup:
        flags.backup = True
    if args.rename_folder:
        flags.RENAME_FOLDER = True
    if args.no_rename_folder:
        flags.RENAME_FOLDER = False
    if args.rename_files:
        flags.RENAME_FILES = True
    if args.no_rename_files:
        flags.RENAME_FILES = False
    if args.tag:
        flags.TAG = True
    if args.no_tag:
        flags.TAG = False
    if args.no_title:
        flags.TITLE = False
    if args.keep_title:
        flags.KEEP_TITLE = True
    if args.same_folder_name:
        flags.SAME_FOLDER_NAME = True
    if args.one_lang:
        flags.ALL_LANG = False
    if args.translate:
        flags.TRANSLATE = True

    if args.album_data_only:
        flags.TITLE = False
        flags.DISC_NUMBERS = False
        flags.TRACK_NUMBERS = False
        flags.IGNORE_MISMATCH = True
        flags.RENAME_FILES = False

    if args.no_scans:
        flags.SCANS = False
    if args.no_pics:
        flags.PICS = False
    if args.pic_overwrite:
        flags.PIC_OVERWRITE = True
    if args.no_auth:
        flags.NO_AUTH = True

    if args.single or args.performers:
        flags.PERFORMERS = True
    if args.single or args.arrangers:
        flags.ARRANGERS = True
    if args.single or args.lyricists:
        flags.LYRICISTS = True
    if args.single or args.composers:
        flags.COMPOSERS = True

    if args.no_modify:
        flags.TAG = False
        flags.RENAME_FOLDER = False
        flags.RENAME_FILES = False

    if args.folder_naming_template:
        template = args.folder_naming_template
        try:
            TemplateResolver.validateTemplate(template)
        except TemplateValidationException as e:
            logger.info(f"{e}, aborting")
            return args, flags, ""

        flags.folderNamingTemplate = args.folder_naming_template

    if args.ksl:
        flags.folderNamingTemplate = "{[{catalog}] }{albumname}{ [{date}]}{ [{format}]}"

    if flags.SEE_FLAGS:
        logger.info("\n" + json.dumps(vars(flags), indent=4))
    return args, flags, folderPath


def tagAndRenameFiles(folderPath: str, albumID: str, flags: Config) -> bool:
    try:
        if flags.TRANSLATE:
            logger.info("fetching and translating album data from VGMDB, it will take a while")
        else:
            logger.info("fetching Album Data from VGMDB")
        albumData: VgmdbAlbumData = getAlbumDetails(albumID)
        if albumData is None:
            logger.error("could not fetch album details, Please Try Again.")
            return False
    except Exception as e:
        logger.exception(e)
        return False

    albumData["vgmdb_link"] = albumData["vgmdb_link"].split("?")[0]
    # Setting crucial info for passing further
    albumData["album_id"] = albumID

    if "catalog" in albumData and (albumData["catalog"] == "N/A" or albumData["catalog"] == "NA"):
        del albumData["catalog"]

    if flags.confirm:
        logger.info(f'link - {albumData["vgmdb_link"]}')
        logger.info(f'album - {getBest(albumData["names"], flags.language_order)}')
        if not yesNoUserInput():
            return False

    albumTrackData = getAlbumTrackData(albumData)
    folderTrackData = getFolderTrackData(folderPath)

    if not doTracksAlign(albumTrackData, folderTrackData, flags):
        logger.info("The tracks are not fully fitting the album data received from VGMDB!")
        if flags.NO_INPUT:
            return False
        print("continue? (y/N/no-title/no-tag): ", end="")
        resp = input()
        if resp == "no-title":
            flags.TITLE = False  # type:ignore
        elif resp == "no-tag":
            flags.TAG = False  # type:ignore
        elif resp.lower() != "y":
            return False
    else:
        logger.info("tracks are perfectly aligning with the album data received from VGMDB!")
        if not flags.NO_INPUT and not flags.yes_to_all:
            print("continue? (Y/n/no-title/no-tag): ", end="")
            resp = input()
            if resp == "no-title":
                flags.TITLE = False  # type:ignore
            elif resp == "no-tag":
                flags.TAG = False  # type:ignore
            elif resp.lower() == "n":
                return False

    # Fixing date in data to be in the form YYYY-MM-DD (MM and DD will be Zero if not present)
    fixedDate = fixDate(albumData["release_date"])
    if fixedDate is not None:
        albumData["release_date"] = fixedDate

    if flags.backup:
        try:
            destinationFolder = Config().BACKUPFOLDER
            if not os.path.exists(destinationFolder):
                os.makedirs(destinationFolder)
            logger.info(f"backing Up {folderPath}...")
            backupFolder = os.path.join(destinationFolder, os.path.basename(folderPath))
            shutil.copytree(folderPath, backupFolder, dirs_exist_ok=False)
            logger.info(f"successfully copied {folderPath} to {backupFolder}")
        except Exception as e:
            logger.error("backup couldn't Be completed, but this probably means that this folder was already backed up, so it 'should' be safe ;)")
            logger.exception(e)
            if not flags.NO_INPUT and not flags.yes_to_all and not yesNoUserInput():
                return False

    if flags.SCANS:
        logger.info("downloading scans...")
        if not flags.NO_AUTH:
            # New Algorithm for downloading Scans -> All scans are downloaded, requires Authentication
            downloadScans(folderPath, albumID)
        elif "covers" in albumData:
            # Old algorithm for downloading -> no Authentication -> less covers available!
            downloadScansNoAuth(albumData, folderPath)
        logger.info("downloaded available scans :)")

    # Tagging
    if flags.TAG:
        logger.info("tagging files\n")
        tagFiles(albumTrackData, folderTrackData, albumData)
    # Renaming Files
    if flags.RENAME_FILES:
        logger.info("renaming files\n")
        renameAlbumFiles(folderPath, verbose=True)
    # Renaming Folder
    if flags.RENAME_FOLDER:
        logger.info("renaming folder\n")
        if flags.SAME_FOLDER_NAME:
            # NOT recommended to use this option, just provide the template in CLI argument itself and use foldername instead of albumname
            renameAlbumFolder(folderPath, renameTemplate="{[{date}]} {foldername} {[{catalog}]}")
        else:
            renameAlbumFolder(folderPath, renameTemplate=flags.folderNamingTemplate)
    return True


def getSearchInput() -> Optional[str]:
    print("enter 'exit' to exit or give a new search term: ", end="")
    answer = input()
    if answer.lower() == "exit":
        return None
    return answer


def findAlbumID(folderPath: str, searchTerm: Optional[str], searchYear: Optional[str], flags: Config) -> Optional[str]:
    if flags.NO_INPUT and not searchTerm:
        return None
    folderName = os.path.basename(folderPath)
    logger.info(f"searching album in folder: {folderName}")
    if searchTerm is None:
        searchTerm = getSearchInput()
    # if searchTerm is still None -> user typed Exit
    if searchTerm is None:
        return None
    logger.info(f"searching for: {searchTerm}, year: {searchYear}")
    albums = searchAlbum(searchTerm)
    if not albums:
        logger.error("no results found!, please change search term!")
        return findAlbumID(folderPath, None, None, flags)

    albumData: dict[int, SearchAlbumData] = {}
    tableData = []
    serialNumber: int = 1
    for album in albums:
        albumID = album.link.split("/")[1]
        albumLink: str = f"https://vgmdb.net/{album.link}"
        albumTitle = getBest(album.titles, flags.language_order)
        releaseDate = album.release_date
        year = getYearFromDate(releaseDate)
        catalog = album.catalog
        if not searchYear or searchYear == year:
            albumData[serialNumber] = SearchAlbumData(**album.model_dump(), album_id=albumID, release_year=year, title=albumTitle)
            tableData.append((serialNumber, catalog, albumTitle, albumLink, year))
            serialNumber += 1
    if not tableData:
        # if we are here then that means we are getting some results but none are in the year provided
        return findAlbumID(folderPath, searchTerm, None, flags)
    logger.info("\n" + tabulate(tableData, headers=["S.No", "Catalog", "Title", "Link", "Year"], maxcolwidths=52, tablefmt=Config().tableFormat, colalign=("center", "left", "left", "left", "center")))

    if (flags.NO_INPUT or flags.yes_to_all) and len(tableData) == 1:
        logger.info("continuing with this album!")
        choice = "1"
    elif flags.NO_INPUT:
        return None
    else:
        print(f"give another search term (exit allowed) or choose album serial number (1-{len(tableData)}): ", end="")
        choice = input()
        if choice.lower() == "exit":
            return None
        if choice == "":
            choice = "1"
        if not choice.isdigit() or int(choice) not in albumData:
            logger.info("invalid choice, using that as search term!")
            return findAlbumID(folderPath, choice, None, flags)

    return albumData[int(choice)]["album_id"]


def main():
    args, flags, folderPath = argumentParser()
    if not folderPath:
        return
    logger.info(f"working folder: {folderPath}")
    albumID = args.id
    if albumID is None:
        searchTerm = args.search
        date = None
        if searchTerm is None:
            albumNameOrCatalog, date = getSearchTermAndDate(folderPath)
            if albumNameOrCatalog is None:
                logger.info("could not obtain either album name or catalog number from files in the directory, please provide custom search term!")
            searchTerm = cleanSearchTerm(albumNameOrCatalog)
        albumID = findAlbumID(folderPath, searchTerm, getYearFromDate(date), flags)
    if albumID:
        tagAndRenameFiles(folderPath, albumID, flags)
        logger.info("finished all <Possible> operations")
    else:
        # if album-ID is still not found, script cannot do anything :(
        logger.info(f"cannot tag album in {folderPath} as albumID cannot be deduced :(")


if __name__ == "__main__":
    main()
