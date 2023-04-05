from typing import Optional
import requests
import io
from PIL import Image

from Imports.flagsAndSettings import Flags, languages
from Types.albumData import AlbumData, TrackData
from Utility.generalUtils import fixDate, getBest, getProperCount
from Utility.mutagenWrapper import AudioFactory


def getImageData(albumData: AlbumData) -> Optional[bytes]:
    if 'picture_full' not in albumData:
        return None

    response = requests.get(albumData['picture_full'])
    imageData = response.content
    image = Image.open(io.BytesIO(imageData))
    image = image.convert('RGB')  # Remove transparency if present
    width, height = image.size

    if width > 800:
        new_height = int(height * (800 / width))
        image = image.resize((800, new_height), resample=Image.LANCZOS)

    imageData = io.BytesIO()
    image.save(imageData, format='JPEG', quality=70)
    imageData = imageData.getvalue()
    return imageData


def tagAudioFile(trackData: TrackData, flags=Flags()):
    audio = AudioFactory.buildAudioManager(trackData['file_path'])

    def addMultiValues(tag: str, tagInFile: str, flag: bool = True) -> None:
        if tag in trackData and flag:
            listOfValues: list[str] = []
            for val in trackData[tag]:
                listOfValues.append(getBest(val['names'], flags.languageOrder))
            audio.setCustomTag(tagInFile, listOfValues)

    def getAllLanguages(languageObject: dict[str, str]) -> list[str]:
        ans: list[str] = []
        for currentLanguage in flags.languageOrder:
            for languageKey in languages[currentLanguage]:
                if languageKey in languageObject:
                    ans.append(languageObject[languageKey])
                    break
        # removing duplicates
        res: list[str] = []
        [res.append(x) for x in ans if x not in res]
        if len(res) == 0:
            res = [list(languageObject.items())[0][1]]
        return res

    # Tagging Album specific Details
    if flags.TITLE:
        titles = [getBest(trackData['track_titles'], flags.languageOrder)]
        if flags.ALL_LANG:
            titles: list[str] = getAllLanguages(trackData['track_titles'])
        if flags.KEEP_TITLE:
            title = audio.getTitle()
            titles.append(title) if title else None
        # removing duplicate titles
        res = []
        [res.append(x) for x in titles if x not in res]
        titles = res

        audio.setTitle(titles)

    if flags.ALL_LANG and 'album_names' in trackData:
        albumNames = getAllLanguages(trackData['album_names'])
        audio.setAlbum(albumNames)
    else:
        audio.setAlbum([trackData['album_name']])
    audio.setTrackNumbers(getProperCount(trackData['track_number'], trackData['total_tracks']), str(trackData['total_tracks']))
    audio.setDiscNumbers(getProperCount(trackData['disc_number'], trackData['total_discs']), str(trackData['total_discs']))
    audio.setComment(f"Find the tracklist at {trackData['album_link']}")

    if flags.PICS and 'picture_cache' in trackData:
        imageData = trackData['picture_cache']
        if audio.hasPictureOfType(3):
            if flags.PIC_OVERWRITE:
                audio.deletePictureOfType(3)
                audio.setPictureOfType(imageData, 3)
        else:
            audio.setPictureOfType(imageData, 3)

    if flags.DATE:
        fixed_date = fixDate(trackData.get('release_date'))
        if fixed_date:
            audio.setDate(fixed_date)

    if flags.YEAR and 'release_date' in trackData and len(trackData['release_date']) >= 4:
        audio.setCustomTag('Year', trackData['release_date'][0:4])

    if flags.CATALOG and 'catalog' in trackData:
        audio.setCatalog(trackData['catalog'])

    if flags.BARCODE and 'barcode' in trackData:
        audio.setCustomTag('Barcode', trackData['barcode'])

    if flags.ORGANIZATIONS and 'organizations' in trackData:
        for org in trackData['organizations']:
            audio.setCustomTag(org['role'], getBest(org['names'], flags.languageOrder))

    addMultiValues('lyricists', 'lyricist', flags.LYRICISTS)
    addMultiValues('performers', 'performer', flags.PERFORMERS)
    addMultiValues('arrangers', 'arranger', flags.ARRANGERS)
    addMultiValues('composers', 'composer', flags.COMPOSERS)

    try:
        audio.save()
        return True
    except Exception as e:
        print(e)
    return False
