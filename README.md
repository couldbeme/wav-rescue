# wav-rescue

Recover a WAV recording that a hardware recorder (DJ player, field recorder, mixer) left at 0 bytes, check the result for damage, and mix simultaneous recordings into one file.

A recording shows as 0 bytes when the recorder lost power or the drive was removed before it finished the file. On FAT32 and exFAT drives the audio is usually still on the disk; only the file's size entry was never written. These tools read the raw disk, find every WAV header, and copy the audio out. They never write to the source drive.

## What is in here

| File | What it does |
|---|---|
| `carve_wav.py` | `scan` lists every WAV header on a disk or image; `extract` copies one recording out. A finished file is copied at exactly its declared size; an unfinished one (size 0) is copied until 64 MiB of zeros, then its header is repaired. |
| `check_splices.py` | Finds dense runs of extreme sample jumps (a sign of foreign data stitched in). Given two simultaneous recordings, it marks bursts that occur at the same moment in both as part of the recording itself. 24-bit WAVs. |
| `mix_two.py` | Sums two time-aligned 24-bit stereo WAVs into one, normalised to -1 dBFS. |

## How to use it (macOS)

1. **Stop writing to the drive.** Do not record, copy or format. Unmount it so the system stops writing too, but leave it plugged in:
   ```
   diskutil list                      # find the drive, e.g. disk4s1
   diskutil unmount /Volumes/<NAME>
   ```
2. **Allow raw disk access.** macOS blocks raw reads even for an administrator unless the terminal app has Full Disk Access: System Settings → Privacy & Security → Full Disk Access → turn on your terminal app, then quit and reopen it. Run the commands below in that terminal (sudo needs a real terminal for the password).
3. **Scan** (read-only; about 1 minute per few GB over USB 3):
   ```
   mkdir -p ~/Desktop/recovery
   sudo python3 carve_wav.py scan /dev/rdisk4s1 ~/Desktop/recovery | tee ~/Desktop/recovery/scan.log
   ```
   Each line is one header: offset, declared size, channels, sample rate, bit depth. A lost recording usually has `riff_size` 0, or is far larger than ordinary tracks. Recorders often split long sessions into files of about 1 GB.
4. **Extract** the candidate by its offset:
   ```
   sudo python3 carve_wav.py extract /dev/rdisk4s1 <offset> ~/Desktop/recovery/set.wav
   ```
   The copy belongs to root; `cp` it to a folder of your own to get a copy you own.
5. **Check it:**
   ```
   python3 check_splices.py ~/Desktop/recovery/set.wav [~/Desktop/recovery/set2.wav]
   ```
   Listen at every time it prints. "in both files" means the burst happened during recording.
6. **Mix** two simultaneous recordings:
   ```
   python3 mix_two.py a.wav b.wav mix.wav
   ```
7. Back up the recovered files before you use the drive again.

`scan` and `extract` also work on a disk image (`dd if=/dev/rdiskN of=disk.img`) if you have room for one, which is the safer route on a failing drive.

## Limits

- Extraction assumes the recording sits in one contiguous run on the disk. That is typical on a mostly empty FAT32/exFAT drive. On a full or fragmented drive pieces may be out of order; `check_splices.py` and listening will show it, and a cluster-by-cluster rebuild is then needed.
- `check_splices.py` flags candidates; it cannot prove a file is clean. Listen to every flagged time.
- Needs Python 3 and numpy (`check_splices.py`, `mix_two.py`); `carve_wav.py` uses only the standard library.

## Related tools and prior art

Nothing here is a new technique. Carving files from raw disks is standard forensics practice, and repairing the size fields of an interrupted WAV is a long-known fix:
- [PhotoRec](https://www.cgsecurity.org/wiki/PhotoRec) (TestDisk project) carves many file types, WAV included, from disks and images.
- RepairWave, part of the WAVE Utilities suite, inserts missing data-chunk size information into ill-formed WAV files.
- The manual route: open the file in a hex editor and set the RIFF size to file length − 8 and the data size to the audio bytes present ([Synalysis write-up](https://www.synalysis.net/developer-weblog/rescue-of-a-wav-file.html)), or import the bytes into Audacity as raw PCM with the recorder's settings.

What this kit adds is convenience for one common case: a recorder's 0-byte file on a mostly empty card, recovered in two commands on macOS, plus a burst check that uses a second simultaneous recording to tell recording artefacts from recovery damage.

## Tests

```
python3 -m pytest -q tests
```
The tests build synthetic disk images with unfinished and finished WAVs, and synthetic recordings with shared and single bursts.
