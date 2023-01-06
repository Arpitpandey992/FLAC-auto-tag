import math
import shutil

from flagsAndSettings import *
from utilityFunctions import *

forbiddenCharacters = {
    '<': 'ᐸ',
    '>': 'ᐳ',
    ':': '꞉',
    '"': 'ˮ',
    '\'': 'ʻ',
    '/': '／',
    '\\': '∖',
    '|': 'ǀ',
    '?': 'ʔ',
    '*': '∗',
    '+': '᛭',
    '%': '٪',
    '!': 'ⵑ',
    '`': '՝',
    '&': '&',  # keeping same as it is not forbidden, but it may cause problems
    '{': '❴',
    '}': '❵',
    '=': '᐀',
    # Not illegal, but the bigger version looks good (JK, it's kinda illegal, cd ~/Downloads :))
    '~': '～',
    '#': '#',  # couldn't find alternative
    '$': '$',  # couldn't find alternative
    '@': '@'  # couldn't find alternative
}


def cleanName(name):
    output = name
    for invalidCharacter, validAlternative in forbiddenCharacters.items():
        output = output.replace(invalidCharacter, validAlternative)
    return output


def renameFiles(albumTrackData, folderTrackData, data, languages):
    totalTracks = 0
    for disc in albumTrackData:
        totalTracks += len(albumTrackData[disc])
    totalDisks = len(albumTrackData)
    tracksUpperBound = int(math.ceil(math.log10(totalTracks+1)))
    disksUpperBound = int(math.ceil(math.log10(totalDisks+1)))
    albumName = cleanName(getBest(data['names'], languages))
    folderPath = data['folderPath']
    date = data['release_date'].replace('-', '.')

    if MOVE:
        if 'catalog' in data and data['catalog'] != 'N/A':
            albumFolder = f'[{date}] {albumName} [{data["catalog"]}]'
        else:
            albumFolder = f'[{date}] {albumName}'
    else:
        albumFolder = ''

    albumFolderPath = os.path.join(folderPath, albumFolder)
    if not os.path.exists(albumFolderPath):
        os.makedirs(albumFolderPath)

    tableData = []
    for discNumber, tracks in folderTrackData.items():
        properDiscNumber = str(discNumber).zfill(disksUpperBound)
        if totalDisks > 1:
            discFolderPath = os.path.join(
                albumFolderPath, f'Disc {properDiscNumber}')
            baseDiscFolder = os.path.basename(discFolderPath)
        else:
            discFolderPath = albumFolderPath
            baseDiscFolder = ''
        if not os.path.exists(discFolderPath):
            os.makedirs(discFolderPath)
        for trackNumber, filePath in folderTrackData[discNumber].items():
            fileName = os.path.basename(filePath)
            fileNameWithPath, extension = os.path.splitext(filePath)
            properTrackNumber = str(trackNumber).zfill(tracksUpperBound)
            if discNumber not in albumTrackData or trackNumber not in albumTrackData[discNumber]:
                tableData.append(
                    (discNumber, trackNumber, fileName, '**NO CHANGE**'))
                continue
            newName = cleanName(albumTrackData[discNumber][trackNumber])
            # File Names
            finalNewName = f'{properTrackNumber} - {newName}{extension}'
            newPath = os.path.join(discFolderPath, finalNewName)
            shutil.move(filePath, newPath)
            tableData.append(
                (discNumber, trackNumber, fileName, os.path.join(baseDiscFolder, ' '+finalNewName)))

    print('Files Renamed as Follows\n')
    tableData.sort()
    print(tabulate(tableData,
                   headers=['Disc', 'Track', 'Old Name', 'New Name'],
                   colalign=('center', 'center', 'left', 'left'),
                   maxcolwidths=53, tablefmt=tableFormat), end='\n\n')
    if MOVE:
        scansFolder = os.path.join(folderPath, 'Scans')
        if not os.path.exists(os.path.join(albumFolderPath, 'Scans')) and os.path.exists(scansFolder):
            shutil.move(scansFolder, albumFolderPath)
        print(f'Successfully moved files into {albumFolder}')
        print('\n', end='')
