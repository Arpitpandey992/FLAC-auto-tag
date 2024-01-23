import os
from typing import Optional
from pydantic import BaseModel

from Modules.Mutagen.mutagenWrapper import IAudioManager
from Modules.Print.utils import LINE_SEPARATOR, SUB_LINE_SEPARATOR


class LocalTrackData(BaseModel):
    file_path: str
    depth_in_parent_folder: int
    audio_manager: IAudioManager

    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path)

    class Config:
        arbitrary_types_allowed = True

    def __hash__(self) -> int:
        return self.file_path.__hash__()  # for being able to create a set

    def get_audio_source(self) -> str | None:
        extension = self.audio_manager.getExtension()
        # Flac contains most info variables, hence using it here for type hints only
        info = self.audio_manager.getInfo()
        if extension.lower() in [".flac", ".wav"]:
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
        return None


class LocalDiscData(BaseModel):
    tracks: dict[int, LocalTrackData] = {}
    folder_name: Optional[str] = None  # It may represent Disc Name for properly stored albums (like Disc 1: The Rime of the Ancient Mariner)

    @property
    def total_tracks(self) -> int:
        return len(self.tracks)


class LocalAlbumData(BaseModel):
    """
    an object containing the data of files representing an audio album present in a file system
    """

    album_folder_path: str
    discs: dict[int, LocalDiscData] = {}  # files with proper disc number (default = 1) and track numbers already present
    unclean_tracks: list[LocalTrackData] = []  # files without track number tags, maybe we can still tag them somehow? (accoust_id, name similarity, etc)

    @property
    def album_folder_name(self) -> str:
        return os.path.basename(self.album_folder_path)

    @property
    def total_discs(self):
        return len(self.discs)

    @property
    def total_tracks_in_album(self):
        return sum(len(disc.tracks) for disc in self.discs.values())

    # helper functions
    def pprint(self) -> str:
        """pretty printing only the useful information"""
        details = f"{LINE_SEPARATOR}\nalbum path: {self.album_folder_path}\n{LINE_SEPARATOR}\n"
        for disc_number, disc in sorted(self.discs.items()):
            details += f"Disc {disc_number}:{f' {disc.folder_name}' if disc.folder_name else ''}\n{SUB_LINE_SEPARATOR}\n"
            for track_number, track in sorted(disc.tracks.items()):
                details += f"Track {track_number}: {track.file_path}\n"
            details += f"{SUB_LINE_SEPARATOR}\n"
        details += f"{LINE_SEPARATOR}\n"
        return details

    def get_track(self, disc_number: int, track_number: int) -> LocalTrackData | None:
        return self.discs[disc_number].tracks[track_number] if self._does_track_exist(disc_number, track_number) else None

    def set_track(self, disc_number: int, track_number: int, track: LocalTrackData):
        """writes over existing track if it exists"""
        if disc_number not in self.discs:
            self.discs[disc_number] = LocalDiscData()
        self.discs[disc_number].tracks[track_number] = track

    def get_all_tracks(self) -> list[LocalTrackData]:
        tracks = [track for track in self.unclean_tracks]
        tracks.extend([track for _, disc in self.discs.items() for _, track in disc.tracks.items()])
        return tracks

    def get_one_sample_track(self) -> LocalTrackData:
        all_tracks = self.get_all_tracks()
        return all_tracks[0] if all_tracks else self.unclean_tracks[0]  # if there are no clean tracks, there must be at least one unclean track

    def _does_track_exist(self, disc_number: int, track_number: int) -> bool:
        if disc_number not in self.discs or track_number not in self.discs[disc_number].tracks:
            return False
        return True


def test():
    from Modules.Scan.Scanner import Scanner

    test_music_dir = "/Users/arpit/Library/Custom/Music/Rewrite OST Bak"
    scanner = Scanner()
    album = scanner.scan_album_in_folder_if_exists(test_music_dir)
    if not album:
        return
    print(album.pprint())
    LocalAlbumData(**album.model_dump())


if __name__ == "__main__":
    test()
