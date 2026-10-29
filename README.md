# Curitiba bus map

A timelapse of one day of scheduled bus service in Curitiba. Routes glow where service is heavy, and every dot is a vehicle moving along its route. A clock, vehicle counts and a daily activity graph run alongside.

> **Not live.** Despite the repository name, this plays back the published timetable. It does not use live GPS. Positions are where the timetable says each bus should be, with trip durations estimated from route length.

## Features

- Weekday, Saturday and Sunday timetables
- Three groups with their own colour, each toggled by tapping its count: buses (orange), Ligeirinho (gray), Expresso and Ligeirão BRT (red)
- Tap a dot to highlight that route and see how many of its buses are running; tap the map again to clear
- Pinch to zoom, drag to pan (mouse wheel on desktop)
- Opens at 03:00, using today's timetable on your device (weekday, Saturday or Sunday)
- Speeds: Sluggish, Slow, Normal, Fast and Live (real time from wherever the timelapse is)
- Portuguese and English, picked from the browser language, with a PT/EN switch above the control bar (choice is remembered)
- Larger clock card and route tag on desktop and on mobile in portrait
- Starts paused; background music (“Stranger Things” by Music_Unlimited, Pixabay Content License) plays with the timelapse. A speaker button next to PT/EN mutes it; it starts unmuted on desktop and muted on touch devices. The track is downloaded only the first time it plays, then loops
- The track ships as `snd/snd.opus.bin` (Opus, 52 kbps) with `snd/snd.mp3.bin` (MP3, 56 kbps) as a fallback for browsers without Opus, about 1 MB each. `python3 scripts/encode_sound.py` makes both from `snd/snd.mp3` with ffmpeg and scrambles them. The mp3 itself is not committed

## Data

Source: URBS Curitiba static GTFS, taken from [benaytms/urbs-gtfs](https://github.com/benaytms/urbs-gtfs/releases/download/latest/gtfs_curitiba.zip) (a snapshot covering late September 2026).

How it is processed (`scripts/build_data.py`):

1. Each stop pattern is matched to the nearest road line in `shapes.txt` (610 of 653 patterns match; the rest are drawn as straight lines between stops).
2. The timetable lists each bus once per timing stop it passes, so the same bus appears several times. Only one timing stop per route and day type is kept, preferring the pattern's first stop. Loop lines listed with rotated stop lists (for example Circular Sul) are merged when they serve the same stops.
3. The file has no travel times, so duration is route length divided by an assumed speed: 18 km/h buses, 21 km/h Ligeirinho, 24 km/h BRT.
4. Trips whose listed time is before 04:00 are shown after midnight, so the day runs 04:00 to 04:00.

Checked against real departure times for lines 250 (Terminal Santa Cândida, 169 of 169 match) and 022 (Terminal Cabral, 144 of 144 match).

### Vehicle groups

- **Ligeirinho:** 022, 023, 024, 206, 220, 305, 307, 469, 505, 506, 507, 508, 601, 700, 702 (601 is not in this feed)
- **Expresso / BRT:** 203, 302, 303, 500, 502, 503, 602, 603, X11, X12, X20, 250, 350, 550
- Everything else is a regular bus.

## Rebuild

```bash
pip install numpy scipy
curl -L -o gtfs.zip https://github.com/benaytms/urbs-gtfs/releases/download/latest/gtfs_curitiba.zip
unzip gtfs.zip -d gtfs
python scripts/build_data.py gtfs data/curitiba_data.json
python scripts/build_page.py   # writes index.html
```

Open `index.html` in a browser; it is a single self-contained file (fonts load from Google Fonts).

## Known limits

- Timetable, not live positions; real buses will differ.
- Some multi-pattern lines (for example 250 and 303) may still look busy; they are not merged because their stop sets differ.
- Neighbourhood labels use approximate positions.
