"""Shrink snd/snd.mp3 and scramble it so the track can't be played straight from its URL.

Writes two encodes with ffmpeg, each about 1 MB for the 2:36 track:
  snd/snd.opus.bin  Opus 52 kbps stereo in WebM (preferred: much better quality at this size)
  snd/snd.mp3.bin   MP3 56 kbps stereo, for browsers that can't decode Opus (older Safari)
Each is XORed with a xorshift keystream. This is obfuscation, not real protection: the page undoes
it with the same keystream. Keep the seed in sync with SND_SEED in src/template.html.
"""
import pathlib
import subprocess
import tempfile
root = pathlib.Path(__file__).resolve().parent.parent
SEED = 0x9E3779B9
ENCODES = {
    "snd.opus.bin": ["-c:a", "libopus", "-b:a", "52k", "-f", "webm"],
    "snd.mp3.bin": ["-c:a", "libmp3lame", "-b:a", "56k", "-f", "mp3"],
}


def scramble(data):
    out = bytearray(data)
    x = SEED
    for i in range(len(out)):
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        out[i] ^= x & 0xFF
    return bytes(out)


with tempfile.TemporaryDirectory() as tmp:
    for name, args in ENCODES.items():
        enc = pathlib.Path(tmp) / name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(root / "snd" / "snd.mp3"),
                        "-map", "0:a", "-map_metadata", "-1", *args, str(enc)], check=True)
        data = scramble(enc.read_bytes())
        (root / "snd" / name).write_bytes(data)
        print(f"wrote snd/{name} ({len(data) / 1024:.0f} KB)")
