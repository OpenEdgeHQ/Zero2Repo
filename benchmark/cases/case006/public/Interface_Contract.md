# Interface Contract

<!-- assembled from contract_sections/; edit shards, not this file -->

### Product overview

**ClipKit** is a Python library for video editing: cuts, concatenations, title insertions, video compositing (non-linear editing), video processing, and creation of custom effects. It reads and writes the common audio and video formats, including GIF. It runs on Windows, macOS, and Linux with Python 3.9 or newer.

The advertised happy path is: open a video file, keep only a timed slice, scale the soundtrack volume, generate a title as a still picture, overlay that title on the video, and write the result to a new file.

The product imports pictures and sounds, exposes every frame as a numeric array so pixels and samples are accessible, lets the caller mix clips in time and space, and encodes the finished clip back to MP4, WebM, GIF, and similar containers. Frames pass through Python; file encode and decode go through an external FFmpeg binary. The product does not stream live cameras or remote live output, and it is not a command-line editor of its own.

Exact published symbol names, import paths, and call signatures belong with those symbols, not here.

### Shape of the public surface

The product is an **importable Python library**, not a network service and not a wire protocol. It does not ship a required console-script entry of its own.

**Distribution and import.** The installable distribution name and the importable top-level package are both `clipkit`. Callers write `import `clipkit`` or `from `clipkit` import …` and obtain clip classes from that package root. The package is a single top-level directory named `clipkit` at the repository root. Importing the package binds encoder configuration (see below); changing the process environment after that import does not rewrite the chosen binary.

**Library.** Callers construct clip objects, ask them for a frame at a time value, assign duration and frame rate, attach or strip a soundtrack, iterate frames of a finite clip, encode to a video file, an audio file, an animated GIF, or a numbered image sequence, and save one still frame. Modifying a clip returns a distinct clip; the original is left unchanged.

**Not a CLI.** There is no product command that authors type as an editor. Programs import the package and call it.

**Numeric arrays.** Picture and sound frames are arrays from the numeric-array library `numpy`. That library is a dependency, not a module of this product. A standard video frame is height × width × 3 with integer channel values in 0–255 (red, green, blue). A mask frame is greyscale height × width with values in 0–1. A sound frame is length 1 (mono) or length 2 (stereo) with floating-point samples.

Exact parameter lists, return shapes, and raised types for individual symbols belong with those symbols, not here.

### Naming conventions

**Product and package.** The product identity is ClipKit. The distribution and the import package are spelled `clipkit`.

**Clip classes.** Public clip types imported from the package root use PascalCase: `VideoClip`, `ColorClip`, `AudioClip`.

**Copy-on-modify.** Operations that assign timing, frame rate, or soundtrack are named with_… / without_… and return a new clip: `with_duration`, `with_fps`, `with_start`, `with_end`, `with_audio`, `without_audio`. `copy` returns a distinct replica.

**Frame access and encode.** Asking for one picture or sound is `get_frame`. Iterating every frame is `iter_frames`. Writing a video file is `write_videofile`; writing an audio file is `write_audiofile`; writing an animated GIF is `write_gif`; writing a numbered image sequence is `write_images_sequence`; saving one frame is `save_frame`.

**Timing attributes.** Composition placement and length are `start`, `end`, and `duration` (seconds). Frame rate is `fps`. A video clip’s soundtrack, if any, is `audio`.

**Keywords.** Constructor and method keywords used on this surface include `frame_function`, `duration`, `fps`, `color`, `is_mask`, `change_end`, `change_duration`, `audio`, `logger`, `codec`, `bitrate`, `audio_bitrate`, `pixel_format`, `preset`, `threads`, `temp_audiofile`, `remove_temp`, `loop`, `with_mask`, and `t`.

### Global observables an implementer must reproduce

**Time values.** Wherever a time or duration is accepted, all of the following convert to a number of seconds:

- A number of seconds (`5`, `1.5`, `1.25`).
- A pair (minutes, seconds), for example `(1, 30)` → 90 and `(0, 1.5)` → 1.5.
- A triple (hours, minutes, seconds), for example `(0, 0, 5)` → 5 and `(0, 1, 0)` → 60.
- A colon-separated clock string. Hours:minutes:seconds with a fractional part is accepted (`00:00:01.5`); minutes:seconds (`1:30`) and seconds-only (`8`, `1.25`) are accepted. A comma is accepted as the decimal separator as well as a period (`1,25` equals `1.25`; `00:00:01,5` equals `00:00:01.5`). Hours in the clock string are not dropped: `01:00:01` is 3601 seconds, not 1.

The number `5`, the triple `(0, 0, 5)`, and the clock string `00:00:05` all produce duration 5.

**New clips.** A newly constructed clip starts at composition time 0. End and duration are either supplied at construction or absent (`None`, infinite) until the caller assigns them. Assigning a duration D to a clip that starts at S sets end to S + D. Assigning an end E to a clip that starts at S sets duration to E − S. `start` / `end` are composition placement; they do not change which frame is the clip’s own first frame. Default start is 0.

**Copy-on-modify.** Assigning duration, frame rate, start, end, or soundtrack never mutates the input clip. The operation returns a distinct object. Asking the original for a frame at time t still yields the pre-modification picture or sound.

**Frame rate.** Assigning `fps` without conserving frames (`change_duration` false, which is the default) leaves duration unchanged. The new rate is the default used by `iter_frames` and by encode. Assigning `fps` with `change_duration` true conserves every frame 1:1 and scales duration inversely (halving the rate doubles duration). File-backed clips inherit a rate from the file; still pictures and generated clips have none until the caller assigns one.

**Iteration.** A finite clip with a frame rate iterates `duration` × `fps` whole frames: a 1-second clip at 60 frames per second yields 60 pictures. Each yielded picture is the frame at the corresponding time.

**Missing duration.** Asking a clip that has no duration to iterate all frames, or to encode to a video file, GIF, or image sequence, does not succeed. The failure identifies that duration is missing. The same clip becomes writable and iterable after a duration is assigned. Asking to assign a missing duration while also asking to keep the existing end (`change_end` false) does not succeed. Exception class names and exact message wording are not pinned beyond identifying duration as the missing quantity.

**Soundtrack.** A video clip may carry an audio clip on `audio`, or `None` when there is none. Encode to a video file includes that soundtrack when audio is left on (the default), omits it when `audio` is `False` at write time, and replaces it when `audio` is a filesystem path string naming another sound file. Encode omits audio when the soundtrack has been stripped — even if audio is left on at write time. A named `temp_audiofile` is a companion used while muxing; `remove_temp`=`False` keeps that companion after write.

**Media encoder.** Video file write (`write_videofile`) and audio file write (`write_audiofile`) use an external FFmpeg binary. If the caller names none, the library uses the bundled FFmpeg that ships with the image-IO plugin. The caller may name a binary already on the process path, or a filesystem path to an invocable binary, by setting the process environment variable `FFMPEG_BINARY` **before the library is imported**, or by placing a dotenv file in the working directory that the library reads at import. Changing the environment after import does not rewrite that choice. GIF write, image-sequence write, and still-frame write do not require FFmpeg.

When that encoder is missing, disabled, or not invocable, writing a video file does not succeed: the process does not exit 0, and a zero-byte file is not a successful encode. When the binary is present and invocable, the same write exits 0 and produces a nonempty media file the encoder can open. Hand-built container bytes, a renamed dummy file, or an in-memory fake do not satisfy file write.

**Library substrate.** When the `clipkit` package is not importable, a program that does `from `clipkit` import `ColorClip`` does not run to completion. When the package is importable, that import succeeds and constructing a color clip then asking `get_frame`(0) yields the requested picture.

**No product CLI config syntax.** Encoder choice is the process environment and an optional dotenv file in the working directory. The library does not parse a configuration-file syntax of its own beyond that dotenv lookup.

**Process status (child interpreter).** A successful short program that constructs a finite color clip, assigns a frame rate, and writes an MP4 exits with status 0. The same program exits with a nonzero status when the encoder is unreachable, and when the package cannot be imported.

## `PIL`

`PIL` is the still-image library used to encode and decode picture files (PNG, JPEG, TIFF, and similar). It is **not** a module of this product. Depend on it; do not reimplement it. Callers write `from `PIL` import `Image``.

These names are importable as `from `PIL` import <name>`:

- `Image`

## `PIL.Image`

Import `Image` from `PIL` (`from `PIL` import `Image``). Picture type and factory for building a still image from a numeric array and writing it to a file. Not a product symbol.

These names are callable as ``Image`.<name>` after that import:

- `fromarray`

## `PIL.ImageSequence`

Import `ImageSequence` from `PIL` (`from `PIL` import `ImageSequence``). Still-image helper for walking the frames of a multi-frame picture file (an animated GIF). Not a product symbol. Depend on it; do not reimplement it.

These names are callable as ``ImageSequence`.<name>` after that import:

- `Iterator`

## `PIL.Iterator`

Call `Iterator` on `ImageSequence` after `from `PIL` import `ImageSequence`` (``ImageSequence`.`Iterator``). Walk every frame of a multi-frame still image. Not a product symbol.

### Signature

```
`Iterator`(image)
```

- `image` — first positional. An image object from `open` on `Image`. Callers pass a GIF opened from a path written by `write_gif`.

Call form used: ``ImageSequence`.`Iterator`(image)`.

Returns an iterator. `for frame in `ImageSequence`.`Iterator`(image)` yields one image object per animation frame. A nonempty GIF yields at least one frame; an animated GIF yields more than one. Opening or walking a path that is not a readable GIF does not succeed.

Each yielded frame is a still of that step. Callers snapshot it:

```
`copy`()
```

No arguments. Returns a distinct image holding that frame’s pixels and metadata.

On that still, callers convert pixels:

```
`convert`("`RGBA`")
```

Returns an image that converts with `asarray` to height × width × 4: RGB in the first three channels and alpha in channel 3, with alpha values in 0–255. A GIF written from ordinary color frames has RGB near the source picture; it does not store the clip’s mask as GIF transparency.

The still also has an `info` mapping:

- `duration` — optional. Per-frame delay as a number of milliseconds. `float(duration) / 1000.0` is that frame’s delay in seconds; the sum over every frame is the GIF’s playback length, which matches the source clip’s duration at the write frame rate.
- `loop` — optional. Loop count stored in the GIF. Two writes with different loop counts store different values under this key.

If `loop` is absent from every yielded frame’s `info`, the opened image’s own `info` may still carry it (`image.`info`.get("`loop`")`).

## `PIL.fromarray`

Call `fromarray` on `Image` after `from `PIL` import `Image`` (``Image`.`fromarray``). Build a still image from a numeric array. Not a product symbol.

### Signature

```
`fromarray`(obj, mode=None)
```

- `obj` — a numeric array. Height × width × 3 unsigned 8-bit channels for an RGB picture; height × width × 4 unsigned 8-bit channels for an RGBA picture.
- `mode` — pixel layout. Callers pass ``mode`="RGB"` for three-channel RGB and ``mode`="RGBA"` for four-channel RGB plus alpha.

Call form used: ``Image`.`fromarray`(rgb, `mode`="RGB")` and ``Image`.`fromarray`(packed, `mode`="RGBA")`.

Returns an image object that writes itself to a filesystem path:

```
`save`(fp, format=None)
```

- `fp` — destination path.
- `format` — container name. Callers pass ``format`="PNG"`, ``format`="JPEG"`, or ``format`="TIFF"`.

A three-channel RGB array saved as PNG or TIFF round-trips through a still-image clip as the same pixels. A JPEG save is lossy: a solid color is recovered near the requested RGB, and two JPEGs of different colors remain distinguishable. A four-channel RGBA array saved as PNG keeps the alpha layer so a still-image clip can turn it into a mask.

## `PIL.open`

Call `open` on `Image` after `from `PIL` import `Image`` (``Image`.`open``). Decode a still-image file on disk into an image object. Not a product symbol.

### Signature

```
`open`(fp)
```

- `fp` — first positional. A filesystem path (path object or string) to a picture file. Callers pass a PNG path written by a clip’s frame save.

Call form used: ``Image`.`open`(src)`.

Returns an image object. Decode of a path that is not a readable picture file does not succeed. Callers then load pixels:

```
`load`()
```

No arguments. After `load`, converting the image with `asarray` yields a numeric array of the stored pixels:

- height × width (2-D) — greyscale; the file has no alpha layer.
- height × width × 3 — RGB; no alpha layer.
- height × width × 4 — RGB in the first three channels and alpha in channel 3, with alpha values in 0–255.
- height × width × 2 — greyscale in channel 0 and a second channel.

A PNG that carries an alpha layer round-trips as the four-channel form: a spatial block that was opaque has a high alpha mean, a transparent block a low alpha mean, and two different in-between mask levels remain distinguishable after that decode.

## `clipkit`

The installable distribution and the importable top-level package are both `clipkit`. Callers declare clips from this package root (`import `clipkit`` or `from `clipkit` import …`). The package is a single top-level directory named `clipkit` next to the packaging files.

These names are importable as `from `clipkit` import <name>`:

- `AudioClip`
- `ColorClip`
- `VideoClip`

Typical import:

```
from `clipkit` import `AudioClip`, `ColorClip`, `VideoClip`
```

A program that only needs a solid-color clip may import that name alone, for example `from `clipkit` import `ColorClip``.

When the package is not importable, `from `clipkit` import `ColorClip`` does not run. When the package is importable, that import succeeds.

## `clipkit.AccelDecel`

Construct `AccelDecel` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`AccelDecel`). Accelerate then decelerate: playback eases in and out. The easing curve is not pinned.

### Signature

```
`AccelDecel`()
```

No required arguments.

Call form used: `vfx`.`AccelDecel`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`AccelDecel`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip whose picture changes at an interior time, the result’s picture at time `0` matches the source at time `0`, and the result’s picture near the end of the duration matches the source at that same late time. At an interior time, the result’s picture does not match the source’s picture at that same time (playback is warped versus linear).

## `clipkit.AudioArrayClip`

Import `AudioArrayClip` from the package root `clipkit` (`from `clipkit` import `AudioArrayClip``). Audio clip from a numeric sound array of N samples. `AudioArrayClip` is an `AudioClip`. Construction does not require the media encoder.

### Signature

```
`AudioArrayClip`(array, fps)
```

- `array` — first positional. Numeric array of shape `N × 1` (mono) or `N × 2` (stereo). Samples are floating-point, conventionally in −1 to 1.
- `fps` — second positional. Sample rate in samples per second (a positive number `R`).

Call form used: ``AudioArrayClip`(stereo, rate)` and ``AudioArrayClip`(mono, rate)`.

Returns an audio clip. `duration` is `N / R` seconds. Newly constructed `start` is `0`; `end` is that duration.

### Frame at a time

```
`get_frame`(t)
```

- `t` — a time in seconds. The sample at index `i` is the sound at time `i / R`.

Returns a numeric array of length 1 (mono) or length 2 (stereo) with floating-point samples. At time `0` the samples match `array[0]`. At time `(N - 1) / R` they match array[-1]. At time `i / R` for an interior index they match `array[i]`. Asking twice at the same time returns samples that match.

### Convert back to an array

```
`to_soundarray`()
```

No arguments required. Returns a numeric array of the stored samples. For stereo input the return has two columns. Length is `N` or `N + 1` (sampling a duration `N / R` at rate `R` may include one extra instant). The first `N` rows match the input array within ordinary numeric tolerance (`rtol=1e-5`, `atol=1e-6`).

## `clipkit.AudioClip`

Import `AudioClip` from the package root `clipkit` (`from `clipkit` import `AudioClip``). Generated audio clip: a caller function of time returns mono or stereo samples.

### Signature

```
`AudioClip`(frame_function=None, duration=None, fps=None)
```

- `frame_function` — callable `t → samples`. Required for a generated clip. `t` is a time in seconds. The return is a numeric array of length 1 (mono) or length 2 (stereo) whose samples are floating-point. The clip’s samples at a time t are that function’s array at t.
- `duration` — length in seconds, or `None` (infinite). A generated clip that will be asked for frames at a time inside a finite interval supplies a duration at construction.
- `fps` — sample rate in samples per second. A generated tone used as a soundtrack supplies this at construction (44100 is a valid rate).

Keyword arguments as used: ``AudioClip`(`frame_function`=…, `duration`=…, `fps`=…)`.

Returns an audio clip. Asking twice at the same time on a deterministic function returns samples that match.

### `get_frame`

```
`get_frame`(t)
```

- `t` — a time value (number of seconds, (minutes, seconds) pair, (hours, minutes, seconds) triple, or clock string; comma accepted as decimal separator). Converted to seconds before the frame function runs. `t` may also be a 1-D array of times (a scalar plus a range of offsets of length n).

When `t` is a single time, returns the sound at that time: a numeric array of length 1 or 2 with floating-point samples (the array’s dtype kind is floating or complex). A mono function that returns a length-1 array yields size 1; a stereo function that returns a length-2 array yields size 2. Samples are conventionally in −1 to 1; those bounds may be exceeded.

When `t` is a 1-D array of n times, the return is a sample matrix whose first axis has one row per time. A 1-D return of n samples is n mono samples and reshapes to `(n, 1)`. A stereo clip yields shape `(n, 2)`: the second axis is the two channels. Channel means along the first axis are the per-channel levels at those times.

### `nchannels`

`nchannels` is a public integer on the clip. Channel count is taken from the frame function at time 0: `nchannels` is `1` when that return is mono (length 1), and `2` when that return is stereo (length 2). The attribute stays at that time-0 count after a later `get_frame`: a function that is mono at time 0 and stereo later still has `nchannels` `1`; a function that is stereo at time 0 and mono later still has `nchannels` `2`.

### Soundtrack use

A video clip’s `with_audio` accepts an `AudioClip`. After attach, video.`audio`.`get_frame`(t) yields the assigned clip’s samples at `t`.

### Mix placement

```
`with_start`(t)
```

- `t` — first positional. New composition `start` (a number of seconds as used).

Returns a distinct clip. Clip-local samples are unchanged: `get_frame`(0) still matches the original `get_frame`(0). The result’s `start` is `t`. Used so a member of `CompositeAudioClip` begins later, and so a soundtrack can be delayed before comparing a video overlay mix: before that start the mix matches the already-playing member; during an overlap the mix is distinguishable from either member and is not silence. Duration of that mix is the maximum of the members’ ends (a member that starts at S and lasts D ends at S + D).

### Time slice and skip

Each of the following returns a **distinct** clip and leaves the original’s `duration` and samples unchanged.

```
`subclipped`(A, B)
```

Positional time slice. First argument is the start time value; second is the end time value and may be omitted. With both arguments, `duration` of the result is B − A. `get_frame`(t) is the source samples at A + t, not the source samples at t.

```
`with_section_cut_out`(C, D)
```

Two positional time values. Plays the source up to C and then continues from D. `duration` is shortened by D − C. `get_frame` before C matches the source at that time; `get_frame` just after C matches the source just after D, not the skipped interval.

### Sound filter

```
`transform`(…)
```

First positional is a callable `(get_frame, t) → samples`. The first argument fetches the source samples: `get_frame(t)` is the source sound at time t. Scaling as `k * get_frame(t)` multiplies amplitude by k: the result’s samples at a time match the source samples at that time times k.

Call form used: ``transform`(lambda get_frame, t: k * get_frame(t))`.

Returns a distinct clip. The original’s samples are unchanged.

### Encode

`logger`=`None` is accepted. Audio-file write uses FFmpeg.

```
`write_audiofile`(filename, logger=None, codec=…)
```

- `filename` — destination path as a string. First positional argument.
- `logger` — `None` is accepted (no progress bar).
- `codec` — audio encoder name. When omitted, default by extension: mp3 uses libmp3lame; ogg uses libvorbis; wav uses 16-bit PCM (`pcm_s16le`); m4a uses the AAC encoder `libfdk_aac`; flac uses FLAC.

Call forms used: ``write_audiofile`(path, `logger`=None)` and ``write_audiofile`(path, `codec`=…, `logger`=None)`.

On success the path is a nonempty media file FFmpeg can open. For mp3, ogg, wav, and flac, loading the file reproduces the samples within ordinary codec tolerance (a generated tone’s duration and peak frequency match). Writing to m4a with that default, or with `codec`=`"libfdk_aac"`, is the unknown-codec case: no nonempty media file that FFmpeg can open, even if the write call returns as completed; that return is not a successful encode. The same clip still writes an openable wav, mp3, ogg, or flac.

When FFmpeg is unreachable, the call does not succeed and the process status is not 0. A zero-byte file is not a successful encode.

## `clipkit.AudioDelay`

Construct `AudioDelay` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`AudioDelay`). Repeat the sound at a constant interval, each repeat quieter by a factor, a given number of times.

### Signature

```
`AudioDelay`(offset=…, n_repeats=…, decay=…)
```

- `offset` — gap between repetitions, in seconds.
- `n_repeats` — number of extra repetitions (not counting the original).
- `decay` — volume factor for later repetitions. A larger `decay` is louder at a later slot than a smaller `decay` with the same `n_repeats`.

Call form used: ``afx`.`AudioDelay`(`offset`=0.1, `n_repeats`=1, `decay`=0.5)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on an audio clip, or on a video clip that has a soundtrack:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`afx`.`AudioDelay`(`offset`=offset, `n_repeats`=n, `decay`=decay)])`.

Returns a **distinct** clip. The original clip is unchanged.

On a short pulse, a later slot at `n * `offset`` has energy when `n_repeats` is large enough to reach that slot, and is near silent when `n_repeats` is too small. Two otherwise equal delays with different `decay` differ in amplitude at a shared later slot.

On a video clip that has a soundtrack, picture timing is unchanged (pictures at a given time match the source) and `duration` is unchanged. The soundtrack carries the delayed repeats.

## `clipkit.AudioFadeIn`

Construct `AudioFadeIn` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`AudioFadeIn`). From silence to full over a duration.

### Signature

```
`AudioFadeIn`(duration)
```

- `duration` — first positional. Fade length in seconds. Amplitude goes from near silence at time near `0` to the source level once this duration has elapsed.

Call form used: `afx`.`AudioFadeIn`(0.15).

### Application

Pass the constructed effect in a one-element list to `with_effects` on an audio clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`afx`.`AudioFadeIn`(D)]).

Returns a **distinct** clip. The original clip’s samples are unchanged.

On a constant-amplitude clip, the amplitude near time `0` is lower than after the fade duration by a clear margin, and a mid-fade amplitude sits strictly between near-silence and the post-fade level. The easing curve is not pinned.

## `clipkit.AudioFadeOut`

Construct `AudioFadeOut` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`AudioFadeOut`). From full to silence over a duration at the end of the clip.

### Signature

```
`AudioFadeOut`(duration)
```

- `duration` — first positional. Fade length in seconds. Amplitude is the source level until the last `duration` seconds, then falls toward silence as time approaches the clip’s end.

Call form used: `afx`.`AudioFadeOut`(0.15).

### Application

Pass the constructed effect in a one-element list to `with_effects` on an audio clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`afx`.`AudioFadeOut`(D)]).

Returns a **distinct** clip. The original clip’s samples are unchanged.

On a constant-amplitude clip whose own length is that same duration `D`, the amplitude near time `0` is higher than near the end by a clear margin, and a mid-fade amplitude sits strictly between those two. The easing curve is not pinned.

## `clipkit.AudioFileClip`

Import `AudioFileClip` from the package root `clipkit` (`from `clipkit` import `AudioFileClip``). File-backed audio clip: samples come from a sound file (or the audio stream of a video container) through the FFmpeg decoder. `AudioFileClip` is an `AudioClip`. Construction requires an invocable FFmpeg decoder.

### Signature

```
`AudioFileClip`(filename, fps=44100)
```

- `filename` — first positional. Filesystem path as a string to an audio file FFmpeg can decode, including WAV, MP3, OGG, and FLAC, or to a video container that has an audio stream.
- `fps` — decode rate in samples per second. Default `44100`. This is the rate at which the decoder yields samples, not necessarily the source file’s stored rate. A source stored at 22050 still decodes at 44100 when this argument is omitted.

Call form used: `AudioFileClip`(path) and ``AudioFileClip`(path, `fps`=22050)`.

Returns an audio clip. Newly constructed `start` is `0`. `duration` matches the file’s audio stream (within ordinary muxer / container tolerance). `end` is that duration. The clip’s `fps` is the decode rate that was used (44100 by default, or the named `fps`).

A path that does not exist does not succeed. A path that is a directory does not succeed (opening a nested readable audio file inside that directory does succeed). A file that is not readable media does not succeed. In each of those failures, the caller-visible failure identifies the offending path (the path’s filename or the full path string appears in the failure), and no clip that yields frames is returned. Exception class and exact wording are not pinned.

### Decode

The decoder yields **stereo** samples: two channels, even when the source is mono. Sample values are floating-point, conventionally in −1 to 1.

When `fps` is omitted, asking for a sample at each decode instant and stacking those rows produces about `duration × 44100` stereo frames, not a count that follows a different source rate. When `fps` is named, that named rate is the one used.

A stereo WAV written at 44100 from a known array round-trips those samples within ordinary encode/decode tolerance. Lossy formats (MP3, OGG) carry the stored tone at that decode rate within ordinary codec tolerance; lossless FLAC matches the stored waveform the same way WAV does.

### `get_frame`

```
`get_frame`(t)
```

- `t` — a time in seconds inside the clip (less than `duration`).

Returns the sound at that instant: a numeric array of length 2 with floating-point samples (the array’s dtype kind is floating or complex). A 1-D length-2 array is a valid return; converting with `asarray` and flattening yields two channel values. Asking at each time `i / `fps`` for `i = 0, 1, …` while `i / `fps` < `duration``, then stacking those rows, yields a 2-D array of shape `(N, 2)` whose first column is the left channel. A written tone at frequency `f` is present on that channel at the decode rate.

### `close` and context manager

```
`close`()
```

No arguments. Releases the file. After `close`, `get_frame` on that instance does not succeed. Exception class is not pinned.

The clip is a context manager:

```
with `AudioFileClip`(path) as clip:
    ...
```

Inside the block, `get_frame` succeeds. Leaving the block has the same effect as `close`: further `get_frame` on that instance does not succeed.

## `clipkit.AudioLoop`

Construct `AudioLoop` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`AudioLoop`). Repeat the sound a given number of times or out to a given duration; duration becomes that looped length.

### Signature

```
`AudioLoop`(n_loops=None, duration=None)
```

- `n_loops` — repeat count. `AudioLoop`(`n_loops`=3) on a clip of length `d` yields duration `3 * d`.
- `duration` — total duration in seconds. `AudioLoop`(`duration`=D) yields duration `D`.

Call form used: `afx`.`AudioLoop`(`n_loops`=2) and `afx`.`AudioLoop`(`duration`=D).

At least one of `n_loops` or `duration` must be supplied. Constructing `AudioLoop`() with neither is accepted; applying that object does not succeed. Exception class is not pinned.

### Application

Pass the constructed effect in a one-element list to `with_effects` on an audio clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`afx`.`AudioLoop`(`n_loops`=2)]).

Returns a **distinct** clip. The original clip’s samples are unchanged.

The result’s samples at time `d + t` match the source’s samples at time `t` (playback wraps): a pulse near the start of the source repeats at `d` plus that start offset, and a quiet mid-source region stays quiet at the corresponding looped time.

## `clipkit.AudioNormalize`

Construct `AudioNormalize` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`AudioNormalize`). Scale volume so the peak reaches full scale.

### Signature

```
`AudioNormalize`()
```

No required arguments.

Call form used: `afx`.`AudioNormalize`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on an audio clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`afx`.`AudioNormalize`()]).

Returns a **distinct** clip. The original clip’s samples are unchanged.

On a quiet constant-amplitude clip (peak well below 1), the result’s peak is near full scale (above `0.9`). On a clip already at full scale, samples stay at that full-scale amplitude.

## `clipkit.BlackAndWhite`

Construct `BlackAndWhite` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`BlackAndWhite`). Desaturates the picture.

### Signature

```
`BlackAndWhite`()
```

No required arguments.

Call form used: `vfx`.`BlackAndWhite`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`BlackAndWhite`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a solid RGB clip, the three channels of a sampled pixel become nearly equal (the picture is no longer chromatic). Two solids whose luminances differ still differ in mean channel value after desaturation; their pictures are not equal.

This is a color-only effect: an attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.Blink`

Construct `Blink` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Blink`). Alternates visible and invisible for given on/off durations. Observable when the clip is a layer in an overlay; the standalone picture is unchanged.

### Signature

```
`Blink`(duration_on, duration_off)
```

- `duration_on` — first positional. Seconds the clip is visible in each cycle.
- `duration_off` — second positional. Seconds the clip is invisible in each cycle.

Call form used: ``vfx`.`Blink`(on_d, off_d)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`Blink`(on_d, off_d)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

### Overlay

Place the result as the later (upper) layer of a `CompositeVideoClip` whose first layer is an opaque same-size clip. On that composite, during the on interval the picture is the upper clip’s color; during the off interval the picture is the lower clip’s color.

RGB frames of the blinked clip taken in isolation remain the source color at both an on time and an off time. An overlay of the unblinked source does not toggle.

## `clipkit.ColorClip`

Import `ColorClip` from the package root `clipkit` (`from `clipkit` import `ColorClip``). Solid-color video clip: every pixel is the requested color (or, in mask mode, the requested scalar) at every time. `ColorClip` is a `VideoClip`.

### Signature

```
`ColorClip`(size, color=None, is_mask=False, duration=None)
```

- `size` — pair `(width, height)` in pixels. First positional argument. Stored on the clip as observable `size` (width then height). Frame shape uses height × width: an RGB clip of size `(32, 24)` yields a picture of shape `(24, 32, 3)`.
- `color` — when `is_mask` is false (the default), an RGB triple of channel values, for example `(255, 0, 0)`, or a four-channel color `(R, G, B, alpha)`. Default when omitted is black `(0, 0, 0)`. The first three channels are the picture. A four-channel color’s fourth channel is alpha and becomes the clip’s `mask` (see below). A non-mask clip does not accept a scalar color or a color given as a string. When `is_mask` is true, a single scalar in 0–1 (not an RGB triple).
- `is_mask` (`bool`) — default `False`. `True`: the clip is a mask; frames are greyscale height × width with values in 0–1. `False`: frames are height × width × 3 with integer channels in 0–255.
- `duration` — length in seconds, or `None` (the default): the clip is infinite until the caller assigns a duration.

Call form used: ``ColorClip`(size, `color`=…)`, ``ColorClip`((width, height), `color`=(R, G, B, alpha))`, ``ColorClip`((width, height), `color`=…, `is_mask`=True)`, and ``ColorClip`((width, height), `color`=…, `duration`=…)`. Methods chain: ``ColorClip`(…, `duration`=…).`with_fps`(8)`.

Returns a video clip. A newly constructed clip has `start` `0`. When `duration` is omitted, `duration` and `end` are `None`. When `duration` is supplied, `end` is `start` plus that duration.

### Frame at a time

```
`get_frame`(t)
```

- `t` — a time value (number, pair, triple, or clock string). The picture does not depend on `t`: every time shows the same solid color (or mask level). Asking twice at the same time returns pictures that match.

RGB return: numeric array of shape `(height, width, 3)`, integer channels in 0–255, pixels equal to the requested RGB (within half a channel). Indexing `frame[0, 0, 0]`, `frame[0, 0, 1]`, `frame[0, 0, 2]` is the first pixel’s red, green, blue. `frame.shape` is that `(height, width, 3)` triple.

Mask return (`is_mask` true): numeric array of shape `(height, width)` with values in 0–1 matching the requested scalar.

### Mask from a four-channel color

When `is_mask` is false and `color` is a four-channel color, `mask` is not `None`. `mask`.`get_frame`(t) is a greyscale height × width array with values in 0–1. The mean of that mask frame tracks the fourth channel: a larger alpha yields a larger mean than a smaller alpha, and the two masks are distinguishable. The RGB picture from `get_frame` matches the first three channels.

### Copy-on-modify timing and rate

Each of the following returns a **distinct** clip and leaves the original’s `start`, `end`, `duration`, `fps`, and frames unchanged.

```
`with_duration`(duration, change_end=True)
```

- `duration` — a time value, or `None` to clear duration. `5`, `(0, 0, 5)`, and `"00:00:05"` all set `duration` to 5. `(1, 30)` and `"1:30"` set 90. `"00:00:01.5"` sets 1.5. `"1,25"` equals `"1.25"`. `"01:00:01"` sets 3601.
- `change_end` (`bool`) — default `True`: `end` becomes `start` + duration (`None` when duration is `None`). `False`: keep `end` and move `start` so that `end` − `start` is the new duration. Passing `duration=None` with `change_end` `False` does not succeed; the original clip is unchanged. Exception class is not pinned.

```
`with_end`(t)
```

- `t` — a time value for the new `end`. Sets `duration` to `end` − `start`.

```
`with_start`(t, change_end=True)
```

- `t` — a time value for the new composition `start`. Does not change which picture is the clip-local frame at time 0.
- `change_end` (`bool`) — default `True`: keep `duration` and set `end` to new start + duration. `False`: keep `end` and set `duration` to `end` − new start.

```
`with_fps`(fps, change_duration=False)
```

- `fps` — frames per second. Becomes the default for `iter_frames` and encode.
- `change_duration` (`bool`) — default `False`: duration unchanged. `True`: conserve frames 1:1; duration scales inversely with the rate.

```
`copy`()
```

No arguments. Returns a distinct replica. Changing the replica’s duration does not change the original’s duration.

### Soundtrack

```
`with_audio`(audioclip)
```

Returns a distinct copy whose `audio` is the given `AudioClip`. The original’s `audio` stays as it was (`None` if it had none). Pictures at time t are unchanged.

```
`without_audio`()
```

No arguments. Returns a distinct copy whose `audio` is `None`. The original still has its soundtrack.

```
`with_opacity`(factor)
```

First positional factor. Distinct copy. Call form used: `with_opacity`(0.5) on a solid-color clip before overlay. Overlaying the faded clip as the upper layer of a `CompositeVideoClip` blends with the layer below: the overlay picture is not the lower color and not the upper color. Blend formula is not pinned.

### Color ↔ mask conversion

`ColorClip` is a `VideoClip` and exposes `to_mask` and `to_RGB` with no arguments.

```
`to_mask`()
```

No arguments. Call form used: `to_mask`().

On an RGB `ColorClip`, one channel is scaled from 0–255 into 0–1: white `(255, 255, 255)` yields values near 1; black `(0, 0, 0)` yields values near 0; a grey `(v, v, v)` yields values near `v / 255`. On a mask-mode `ColorClip` (`is_mask` true), frames are unchanged.

```
`to_RGB`()
```

No arguments. Call form used: `to_RGB`().

On a mask-mode `ColorClip`, the greyscale value is repeated into three 0–255 channels: a mask of `1` yields white `(255, 255, 255)`; a mask of level `L` yields three equal channels near `L * 255`. On an RGB `ColorClip`, pictures are unchanged.

### Time slice

`ColorClip` is a `VideoClip` and exposes `subclipped` with the same positional signature: start time value, optional end time value.

```
`subclipped`(A, B)
```

Returns a distinct clip. On a clip whose `duration` is `None`, a negative start or a negative end does not succeed and does not return a clip. After `with_duration` assigns a duration D, `subclipped`(-X) has duration X (counting from the end) and still shows the solid color; ``subclipped`(0, -X)` has duration D − X.

### Iteration and encode

`ColorClip` is a `VideoClip` and exposes the same encode operations, including the keywords below. Still-frame write (`save_frame`) does not require FFmpeg, does not use the clip’s `fps`, and does not require `duration`. Iteration and video/GIF/sequence write require a finite `duration` and a frame rate (on the clip or supplied at write). `logger`=`None` is accepted (no progress bar).

```
`save_frame`(filename, t=…, with_mask=…)
```

- `filename` — filesystem path as a string (a `.png` path). First positional argument.
- `t` — time of the frame to write. A numeric second or a clock string. Omitted: time 0.
- `with_mask` — omitted: alpha is left on (the default). `False`: omit the attached mask as alpha.

Call forms used: `save_frame`(path), ``save_frame`(path, `t`=…)`, and ``save_frame`(path, `with_mask`=False)`. On success the path is a nonempty PNG whose pixels match `get_frame` at that time. When a `mask` is attached and alpha is left on, that PNG’s alpha channel matches the mask: mask 1 is near-opaque, mask 0 is near-transparent, and distinct in-between mask values produce distinct in-between alpha. Passing `with_mask`=`False` writes the picture without that mask as alpha.

```
`iter_frames`(logger=None)
```

Returns an iterator of pictures. Count is `int(`duration` × `fps`)` whole frames. Each picture is the RGB (or mask) frame at the corresponding time. Without `duration` the call does not succeed; the failure identifies that duration is missing.

```
`write_videofile`(filename, fps=None, audio=True, logger=None, codec=…, bitrate=…, audio_bitrate=…, pixel_format=…, preset=…, threads=…, temp_audiofile=…, remove_temp=…)
```

- `filename` — filesystem path as a string (for example a `.mp4` path). First positional argument.
- `fps` — default `None`: use the clip’s `fps`. A write-time rate is used when supplied.
- `audio` — default `True`. When `True` and a soundtrack is attached, the file contains that soundtrack. `False` omits audio from the container even if a soundtrack is attached. When the soundtrack has been stripped, the file has no audio stream even if this flag is `True`. A filesystem path string names a replacement soundtrack file: the container’s audio is that file’s sound, not the clip’s attached soundtrack.
- `codec` — video encoder name. When omitted, default by extension: mp4, mkv, and mov use libx264; ogv uses libtheora; webm uses libvpx. Extension avi has no default: the caller must name a codec (for example `"mpeg4"`). A named `codec` overrides the extension default. A codec name FFmpeg does not know does not produce a nonempty media file FFmpeg can open.
- `bitrate` — video bitrate string. Distinct values produce distinct encoded file sizes.
- `audio_bitrate` — soundtrack bitrate string. Distinct values produce distinct encoded file sizes.
- `pixel_format` — pixel format written into the file (for example `"rgb24"`, `"rgba"`). Distinct values produce distinct probed formats.
- `preset` — compression preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow, placebo). Changes file size and encode time, not the documented picture. Omitted matches medium.
- `threads` — integer thread count. The write still produces a loadable picture.
- `temp_audiofile` — companion audio path used while muxing. When omitted, a successful write leaves no leftover companion audio file next to the video.
- `remove_temp` — omitted: the named companion is not left. `False`: keep the named `temp_audiofile`; that path exists after write and contains the soundtrack.

Invokes the FFmpeg encoder. On success, `filename` is a nonempty media file whose container frame rate matches the assigned `fps` (within a small muxer tolerance). Without `duration`, or without a frame rate on the clip and none at write, the call does not succeed and does not leave a nonempty media file. When the encoder is unreachable, the write does not succeed.

```
`write_gif`(filename, fps=None, logger=None, loop=…)
```

- `filename` — destination path as a string (`.gif`).
- `fps` — default `None`: use the clip’s `fps`. A write-time rate is used when supplied.
- `loop` — optional loop count stored in the GIF. Distinct values produce distinguishable stored loop counts.

Call forms used: ``write_gif`(path, `logger`=None)` and ``write_gif`(path, `loop`=…)`. Does not require FFmpeg. GIF write iterates ordinary color frames; it does not store the clip’s mask as GIF transparency. Without `duration`, or without a frame rate on the clip and none at write, the call does not succeed and does not leave a nonempty GIF.

```
`write_images_sequence`(name_format, fps=None, logger=None, with_mask=…)
```

- `name_format` — path pattern with an integer placeholder, for example a folder joined with `frame%03d.png`. First positional.
- `fps` — default `None`: use the clip’s `fps`. A write-time rate is used when supplied.
- `with_mask` — omitted: alpha is left on. When a mask is present and alpha is left on, PNG sequences include that mask as alpha. Passing `with_mask`=`False` omits the mask as alpha.

Call forms used: ``write_images_sequence`(pattern, `logger`=None)` and ``write_images_sequence`(pattern, `with_mask`=False)`. Returns the list of paths; each path exists and is nonempty. Without `duration`, or without a frame rate on the clip and none at write, the call does not succeed and does not leave a nonempty `frame*.png`. After duration and rate are assigned, at least one nonempty `frame*.png` exists.

### Equality

Two `ColorClip` instances built the same way from the same still color, same size, same `duration`, and same `fps` compare equal (`==`). Changing the pictures or the duration makes them unequal (`!=`).

### Observable attributes

- `start` — composition start in seconds (default `0`).
- `end` — composition end in seconds, or `None` when infinite.
- `duration` — length in seconds, or `None` when infinite.
- `fps` — assigned frame rate, after `with_fps`.
- `audio` — attached `AudioClip`, or `None`.
- `mask` — attached greyscale clip when `color` is four-channel; not `None` in that case. `mask`.`get_frame`(t) is height × width with values in 0–1 whose mean tracks that alpha.
- `size` — pair `(width, height)` in pixels, matching the constructor’s first positional. Indexing `size`[0], `size`[1] is width then height. This is not the same observable as a frame’s `shape` from `get_frame`.

## `clipkit.CompositeAudioClip`

Import `CompositeAudioClip` from the package root `clipkit` (`from `clipkit` import `CompositeAudioClip``). Overlay mix: an audio clip that plays several audio clips together. `CompositeAudioClip` is an `AudioClip`.

### Signature

```
`CompositeAudioClip`(clips)
```

- `clips` — first positional. A list of audio clips (for example `AudioClip` or `AudioArrayClip` instances). Members may begin at different composition times; each member’s `start` is when that member becomes audible.

Call form used: ``CompositeAudioClip`([clip_a, clip_b])`.

Returns an audio clip. Newly constructed `start` is `0`.

### Play-together mix

Members play together according to each member’s `start`. Before a later member’s `start`, `get_frame` matches the already-playing member’s samples at that member’s local time (`t` minus that member’s `start`). During an overlap, the mix is distinguishable from either member alone and is not silence. The exact mix formula is not pinned.

```
`get_frame`(t)
```

- `t` — composition time in seconds.

Returns a numeric array of length 1 (mono) or length 2 (stereo) with floating-point samples. Channel count is the maximum channel count among the members: mixing mono with stereo yields size 2; mixing two mono clips yields size 1.

Asking twice at the same time on deterministic members returns samples that match.

### Duration and sample rate

`duration` is the maximum of the members’ ends (a member that starts at S and lasts D ends at S + D). That value is not the maximum of the raw durations when a later start pushes an end past every other member, and it is not the sum of the durations.

`fps` is the maximum sample rate among members that have one.

## `clipkit.CompositeVideoClip`

Import `CompositeVideoClip` from the package root `clipkit` (`from `clipkit` import `CompositeVideoClip``). Overlay composition: a video clip made of other video clips displayed together. `CompositeVideoClip` is a `VideoClip`.

### Signature

```
`CompositeVideoClip`(clips, `size`=…, `bg_color`=…, `use_bgclip`=…)
```

- `clips` — first positional. A list of video clips (for example two `VideoFileClip` instances, or `ColorClip` layers). Later clips in the list are drawn on top of earlier clips when they share the same layer index.
- `size` — optional keyword. Pair `(width, height)` in pixels. Omit: composition size is the size of the first clip. A named larger size is the canvas: `get_frame` pictures have that width and height, and smaller layers float on it.
- `bg_color` — optional keyword. Omit: unfilled canvas pixels are black `(0, 0, 0)`, and that unfilled region is opaque (the composite’s `mask` is `None`, or the unfilled mask value is high). Pass `None`: unfilled regions are transparent — the composite has a `mask`; an unfilled pixel has a low mask value and a filled pixel a high one. Omitting `bg_color` is not the same as passing `None`.
- `use_bgclip` — optional keyword. Pass `True`: the first clip is designated as the background canvas and must match the final size. The composition origin shows that first clip’s picture even if that clip was placed off-origin with `with_position`. If that background has no `mask`, the composite’s `mask` is `None`. Omit: a shifted first clip does not fill the origin; unfilled origin pixels are black.

Call forms used: ``CompositeVideoClip`([clip_a, clip_b])`, ``CompositeVideoClip`([a, placed_b], `size`=(canvas_w, canvas_h))`, ``CompositeVideoClip`([a, placed_b], `size`=(canvas_w, canvas_h), `bg_color`=None)`, and ``CompositeVideoClip`([shifted, placed], `use_bgclip`=True)`.

Returns a video clip. The listed clips remain independently usable after construction.

### `close`

```
`close`()
```

No arguments. Releases resources owned by the composition.

Closing the composition does **not** close the clips it was built from. After composition.`close`(), each source clip still yields frames: source.`get_frame`(t) still returns that source’s picture at `t`. Those sources still need their own `close`; after a source is closed, `get_frame` on that source does not succeed.

## `clipkit.Crop`

Construct `Crop` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Crop`). Keep a rectangular subregion of the picture. Coordinates are in pixels. Frames of the result are exactly that rectangle; pixels outside it are absent.

### Signature

```
`Crop`(x1=…, y1=…, x2=…, y2=…)
```

- `x1`, `y1` — top-left corner of the kept rectangle.
- `x2`, `y2` — opposite corner. The kept rectangle is the half-open pixel window from `(`x1`, `y1`)` to `(`x2`, `y2`)`.

Call form used: ``vfx`.`Crop`(`x1`=0, `y1`=0, `x2`=5, `y2`=10)`.

A 10×10 clip with those corners yields frames 5 pixels wide and 10 pixels tall, still the source color inside the kept region.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`Crop`(`x1`=0, `y1`=0, `x2`=w // 2, `y2`=h)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

An attached `mask` is cropped the same way. An attached soundtrack’s samples at a given time match the source soundtrack at that time (geometry does not rewrite samples).

## `clipkit.CrossFadeIn`

Construct `CrossFadeIn` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`CrossFadeIn`). Cross-fade in: the clip appears progressively from fully transparent to fully opaque over a duration. Overlay of that clip as the upper layer of a `CompositeVideoClip` therefore moves from the lower clip visible to the upper clip visible.

### Signature

```
`CrossFadeIn`(duration)
```

- `duration` — first positional. Fade length in seconds. The clip goes from fully transparent at time 0 to fully opaque once this duration has elapsed.

Call form used: `vfx`.`CrossFadeIn`(D) where `D` is a number of seconds.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`CrossFadeIn`(D)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

### Overlay

Place the result as the later (upper) layer of a `CompositeVideoClip` whose first layer is an opaque same-size clip. On that composite:

- At time `0`, the picture is the lower clip’s color (the faded clip is fully transparent).
- After the fade duration, still inside the composite’s play window, the picture is the upper clip’s color (the faded clip is fully opaque).
- At a time strictly inside `(0, D)` the sampled pixel is not the time-0 color and not the post-fade color.

The interior mix formula and any easing curve are not pinned. RGB frames of the faded clip taken in isolation are not the specified observable; the specified observable is this overlay.

## `clipkit.CrossFadeOut`

Construct `CrossFadeOut` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`CrossFadeOut`). Cross-fade out: the clip disappears progressively from fully opaque to fully transparent over a duration. Overlay of that clip as the upper layer of a `CompositeVideoClip` therefore moves from the upper clip visible to the lower clip visible.

### Signature

```
`CrossFadeOut`(duration)
```

- `duration` — first positional. Fade length in seconds. The clip is fully opaque at time 0 and fully transparent as time approaches this duration.

Call form used: `vfx`.`CrossFadeOut`(D) where `D` is a number of seconds.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`CrossFadeOut`(D)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

### Overlay

Place the result as the later (upper) layer of a `CompositeVideoClip` whose first layer is an opaque same-size clip. The faded clip’s own length is that same duration `D`. On that composite:

- At time `0`, the picture is the upper clip’s color (the faded clip is fully opaque).
- Near the end of the fade duration, still strictly before time `D` (still inside the play window), the picture is the lower clip’s color (the faded clip is effectively fully transparent).
- At a time strictly inside `(0, D)` the sampled pixel is not the time-0 color and not that near-end color.

The interior mix formula and any easing curve are not pinned. RGB frames of the faded clip taken in isolation are not the specified observable; the specified observable is this overlay.

## `clipkit.Effect`

Import `Effect` from the package root `clipkit` (`from `clipkit` import `Effect``). Base type for a reusable transformation applied to a clip. Applying an effect returns a modified copy; the original clip is left unchanged.

A caller-defined effect is a subclass of `Effect`. Construct an instance and pass it in the same effect list as built-in catalog members.

### `apply`

A subclass implements:

```
`apply`(clip)
```

- `clip` — the target clip (video or audio).

Returns a clip. That returned clip is what `with_effects` yields for this list entry.

Call form used inside a subclass: `def `apply`(self, clip):`.

A constructed instance satisfies `isinstance(obj, `Effect`)`.

### Application through `with_effects`

Pass one or more effect objects in a list to `with_effects` on a clip:

```
`with_effects`([effect, …])
```

Several effects in one list are applied in list order. The same effect object may be applied to several clips; each application behaves independently.

A caller-defined `Effect` in that list produces the clip its `apply` returns. Mixing it with a built-in (for example a custom effect then `InvertColors`) applies both, in that order.

## `clipkit.EvenSize`

Construct `EvenSize` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`EvenSize`). Crop so width and height are even.

### Signature

```
`EvenSize`()
```

No required arguments.

Call form used: `vfx`.`EvenSize`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`EvenSize`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip whose width and height are both odd, the result’s frame width and height are both even, and neither axis is larger than the source.

## `clipkit.FadeIn`

Construct `FadeIn` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`FadeIn`). Appear from a color (black by default) over a duration. On a mask, the color is a 0–1 scalar.

### Signature

```
`FadeIn`(duration, initial_color=None)
```

- `duration` — first positional. Fade length in seconds. The clip goes from the initial color at time `0` to the source picture once this duration has elapsed.
- `initial_color` — optional. An RGB triple for a color clip, or a 0–1 scalar for a mask. When omitted, the initial color is black `(0, 0, 0)` on a color clip and `0` on a mask.

Call form used: `vfx`.`FadeIn`(D) and ``vfx`.`FadeIn`(D, `initial_color`=color)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`FadeIn`(D)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a white RGB clip faded from black: at time `0` the picture is darker than after the fade duration; after the fade duration a sampled pixel is white; at a time strictly inside `(0, D)` the pixel is neither black nor white. The interior mix formula and any easing curve are not pinned.

When `initial_color` is a named RGB triple, time `0` is that color, time after `D` is the source color, and a mid-fade pixel is neither.

On a mask of level `1`, time `0` is darker (near `0` when `initial_color` is omitted); after `D` the mask is near `1`. With `initial_color` a scalar `S` in 0–1, time `0` is near `S` and time after `D` is near `1`.

## `clipkit.FadeOut`

Construct `FadeOut` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`FadeOut`). Fade to a color (black by default) over a duration at the end of the clip.

### Signature

```
`FadeOut`(duration, final_color=None)
```

- `duration` — first positional. Fade length in seconds. The clip is the source picture until the last `duration` seconds, then fades to the final color as time approaches the clip’s end.
- `final_color` — optional. An RGB triple. When omitted, the final color is black `(0, 0, 0)`.

Call form used: `vfx`.`FadeOut`(D) and ``vfx`.`FadeOut`(D, `final_color`=color)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`FadeOut`(D)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a white clip whose own length is that same duration `D`: at time `0` the picture is brighter than near the end; a mid-fade pixel is neither white nor black. The interior mix formula and any easing curve are not pinned.

When `final_color` is a named RGB triple, time `0` is white (the source), a time near the end is that named color, and a mid-fade pixel is neither.

## `clipkit.Freeze`

Construct `Freeze` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Freeze`). Hold the frame at a given time for a duration.

### Signature

```
`Freeze`(t=0, freeze_duration=…)
```

- `t` — time, in seconds, whose frame is held. Callers pass `t`=0.0.
- `freeze_duration` — how long that frame is held, in seconds.

Call form used: ``vfx`.`Freeze`(`t`=0.0, `freeze_duration`=D)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`Freeze`(`t`=0.0, `freeze_duration`=D)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip whose picture changes after time `0`, a longer freeze still shows the frozen time-`0` picture at a probe time where a shorter freeze has already resumed the moving source.

## `clipkit.FreezeRegion`

Construct `FreezeRegion` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`FreezeRegion`). One rectangle stays frozen while the rest of the picture animates.

### Signature

```
`FreezeRegion`(region=(x1, y1, x2, y2))
```

- `region` — a 4-tuple `(x1, y1, x2, y2)` in pixels defining the frozen rectangle.

Call form used: ``vfx`.`FreezeRegion`(`region`=(x1, y1, x2, y2))`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`FreezeRegion`(`region`=(1, 1, 6, 6))])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip whose whole-frame color changes over time, a pixel inside the rectangle keeps the same color at two later times, while a pixel outside the rectangle changes. Interior and exterior colors at the same time are not the same.

## `clipkit.GammaCorrection`

Construct `GammaCorrection` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`GammaCorrection`). Apply a gamma exponent to the picture.

### Signature

```
`GammaCorrection`(gamma)
```

- `gamma` — first positional. The exponent. `1.0` leaves a mid-grey picture unchanged (mean channel value within a couple of levels of the source).

Call form used: `vfx`.`GammaCorrection`(1.0), `vfx`.`GammaCorrection`(0.5), and `vfx`.`GammaCorrection`(2.0).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`GammaCorrection`(g)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a mid-grey `(128, 128, 128)` clip, gamma `0.5` changes the mean channel value relative to the source, and gamma `0.5` and gamma `2.0` produce different pictures. The byte polynomial is not pinned.

This is a color-only effect: an attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.HeadBlur`

Construct `HeadBlur` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`HeadBlur`). Blur a moving region whose position is a function of time. The blur kernel is not pinned.

### Signature

```
`HeadBlur`(fx, fy, radius)
```

- `fx` — first positional. Callable of time returning the horizontal center of the blur, in pixels.
- `fy` — second positional. Callable of time returning the vertical center of the blur, in pixels.
- `radius` — third positional. Radius of the blurred region, in pixels.

Call form used: ``vfx`.`HeadBlur`(fx, fy, radius)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`HeadBlur`(fx, fy, radius)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a still picture with a sharp vertical color edge, a region around `(fx(t), fy(t))` is blurred (the edge bleeds) while a region around a different y at the same x stays sharp. When `fy` moves to a new y at a later time, the blur follows: the new center is blurred and the old center is sharp again.

## `clipkit.ImageClip`

Import `ImageClip` from the package root `clipkit` (`from `clipkit` import `ImageClip``). Still-image video clip: the same picture at every time. `ImageClip` is a `VideoClip`. Construction from a picture file or array does not require the media encoder.

### Signature

```
`ImageClip`(img, transparent=True, duration=None)
```

- `img` — first positional. Either a filesystem path as a string to an image file (PNG, JPEG, TIFF, and similar), or a numeric picture array. An RGB array has shape height × width × 3 with integer channels in 0–255. A four-channel array has shape height × width × 4: the first three channels are the picture and the fourth is alpha in 0–255.
- `transparent` (`bool`) — default `True`. When `True` and the picture has an alpha layer, that alpha becomes the clip’s `mask` (values in 0–1, alpha divided by 255). When `False`, the alpha layer is not used as that mask.
- `duration` — length in seconds, or `None` (the default): the clip is infinite until the caller assigns a duration.

Call form used: `ImageClip`(array), ``ImageClip`(array, `duration`=…)`, `ImageClip`(path), ``ImageClip`(array, `transparent`=True)`, and ``ImageClip`(path, `transparent`=False)`.

Returns a video clip. Newly constructed `start` is `0`. When `duration` is omitted, `duration` is `None`. When `duration` is supplied, `duration` equals that value.

A path that is not an image file does not succeed. Exception class and failure wording are not pinned. A real image path at the same size does succeed.

### Frame at a time

```
`get_frame`(t)
```

- `t` — a time value. The picture does not depend on `t`: every time shows the same still.

Returns a numeric array of shape `(height, width, 3)` with integer channels in 0–255. Size is the source picture’s height and width. For a PNG or TIFF file, or for an RGB array, pixels match the source. For a JPEG file, pixels are near the stored color (lossy), and two JPEGs of different colors are distinguishable. Asking twice at the same time, or at two different times, returns pictures that match.

### Mask from alpha

When the source is a four-channel array or a PNG with alpha, and `transparent` is left on (the default, or `True`), `mask` is not `None`. `mask`.`get_frame`(t) is a greyscale height × width array with values in 0–1 matching `alpha / 255`. Passing `transparent` `False` does not attach that alpha as the mask: `mask` is `None`, or its frame does not match `alpha / 255`.

### Still from a video clip

A video clip (including `ColorClip` and a generated `VideoClip`) exposes:

```
`to_ImageClip`(t=0)
```

- `t` — a time value. First positional. The still is taken from the source’s frame at that time.

Returns an `ImageClip`. `get_frame` at time 0 and at a later time both match the source’s `get_frame`(t), not a different time of a time-varying source.

## `clipkit.ImageSequenceClip`

Import `ImageSequenceClip` from the package root `clipkit` (`from `clipkit` import `ImageSequenceClip``). Video clip that plays a list of same-size pictures in order. `ImageSequenceClip` is a `VideoClip`. Construction does not require the media encoder.

### Signature

```
`ImageSequenceClip`(sequence, fps=None, durations=None, with_mask=True)
```

- `sequence` — first positional. One of:
  - A list of numeric RGB pictures, all the same shape (height × width × 3, integer channels in 0–255).
  - A list of filesystem paths as strings to image files, in the order they should play (the given order is kept; names are not re-sorted).
  - A folder path as a string: every image in that folder, in alphanumerical order of filename.
- `fps` — frames per second. When supplied, each picture lasts `1 / `fps`` seconds and `duration` is `N / `fps`` for `N` pictures.
- `durations` — list of per-image durations in seconds, same length as the sequence. When supplied instead of `fps`, `duration` is the sum of those values. The picture whose interval contains time `t` is the one shown at `t`.
- `with_mask` (`bool`) — default `True`. When `True` and the pictures are PNG files with an alpha layer, that alpha becomes the clip’s `mask` (values in 0–1, alpha divided by 255). When `False`, that alpha is not used as the mask.

Exactly one of `fps` or `durations` must be supplied. With neither, the call does not succeed. Exception class and failure wording are not pinned.

Call form used: ``ImageSequenceClip`([a, b], `fps`=1)`, ``ImageSequenceClip`([path_a, path_b], `fps`=2)`, ``ImageSequenceClip`(folder, `fps`=2)`, ``ImageSequenceClip`([a, b], `durations`=[d0, d1])`, and ``ImageSequenceClip`([path_a, path_b], `fps`=2, `with_mask`=False)`.

Returns a video clip. Newly constructed `start` is `0`. `end` equals `duration`.

If any picture has a different size (including a different shape) from the first, the call does not succeed, for both arrays and files. A sequence of matching sizes does succeed.

### Frame at a time

```
`get_frame`(t)
```

- `t` — a time in seconds inside the clip.

Returns the picture that occupies that time. With two pictures `[a, b]` and `fps` `1`, `duration` is 2, time `0` is `a`, and time `1` is `b`. With `durations` `[d0, d1]`, a time inside the first interval is `a` and a time inside the second interval is `b`. File lists play in the listed order. A folder plays the alphanumerically first filename at time `0`, not the file that was created first if that name sorts later.

### Mask from PNG alpha

When `with_mask` is left on (the default) and the files are PNGs with alpha, `mask` is not `None`. `mask`.`get_frame`(0) is greyscale height × width with values in 0–1 matching `alpha / 255`. Passing `with_mask` `False` does not attach that alpha as the mask: `mask` is `None`, or its frame does not match `alpha / 255`.

## `clipkit.InvertColors`

Construct `InvertColors` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`InvertColors`). Each channel is inverted against full scale.

### Signature

```
`InvertColors`()
```

No required arguments.

Call form used: `vfx`.`InvertColors`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`InvertColors`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

A red `(255, 0, 0)` pixel becomes cyan `(0, 255, 255)`. In general a pixel `(r, g, b)` becomes `(255 - r, 255 - g, 255 - b)`: green `(0, 255, 0)` becomes `(255, 0, 255)` and blue `(0, 0, 255)` becomes `(255, 255, 0)`.

The same constructed object applied to two different clips inverts each independently and leaves the originals unchanged.

Several effects in one list are applied in list order: invert then multiply-color matches sequential invert-then-multiply and differs from multiply-then-invert.

This is a color-only effect: an attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.Loop`

Construct `Loop` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Loop`). Repeat the clip. When a repeat count or a total duration is given, duration becomes that looped length; otherwise the result has no duration (infinite loop). Soundtrack and mask follow.

### Signature

```
`Loop`(n=None, duration=None)
```

- `n` — optional repeat count. `Loop`(`n`=3) on a clip of length `d` yields duration `3 * d`.
- `duration` — optional total duration in seconds. `Loop`(`duration`=D) yields duration `D`.

Call form used: `vfx`.`Loop`(), `vfx`.`Loop`(`n`=2), and `vfx`.`Loop`(`duration`=D).

Omitting both `n` and `duration` is accepted: the result’s `duration` is `None`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`Loop`(`n`=2)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

The result’s picture at time `d + t` matches the source’s picture at time `t` (playback wraps). An attached `mask` and soundtrack wrap the same way: mask frames and samples at `d + t` match the source streams at `t`.

Looping a clip that has no duration does not succeed. After a duration is assigned, the same loop succeeds. Exception class is not pinned.

## `clipkit.LumContrast`

Construct `LumContrast` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`LumContrast`). Add a luminosity offset and a contrast factor.

### Signature

```
`LumContrast`(lum=0, contrast=0)
```

- `lum` — luminosity offset. A positive value brightens the picture.
- `contrast` — contrast factor. A nonzero value changes the spread between dark and bright regions.

Call form used: `vfx`.`LumContrast`(), `vfx`.`LumContrast`(`lum`=40), and `vfx`.`LumContrast`(`contrast`=0.6).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`LumContrast`(`lum`=40)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a picture with a dark half and a bright half, `lum`=40 raises the mean channel value relative to the source. A nonzero `contrast` changes the dark-to-bright spread. The two results are different pictures. Exact polynomials are not pinned.

This is a color-only effect: an attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.MakeLoopable`

Construct `MakeLoopable` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MakeLoopable`). Fade the end into the beginning so a loop is seamless.

### Signature

```
`MakeLoopable`(overlap_duration)
```

- `overlap_duration` — first positional. Duration of the fade, in seconds.

Call form used: `vfx`.`MakeLoopable`(0.2).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MakeLoopable`(overlap)]).

Returns a **distinct** clip with a finite `duration`. The original clip’s pictures are unchanged.

Near the end of the result, a sampled picture is neither the source’s first frame nor the source’s last frame (the end is mixed with the beginning). Changing the source’s start color or end color changes that near-end mix. The mix formula is not pinned.

## `clipkit.Margin`

Construct `Margin` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Margin`). Add a colored (or transparent) border around the frame, growing the size.

### Signature

```
`Margin`(margin_size=…, color=…, opacity=1.0)
```

- `margin_size` — border width in pixels on every side. Result width is source width plus `2 * `margin_size``; result height is source height plus `2 * `margin_size``.
- `color` — RGB triple of the border.
- `opacity` — default `1.0` (opaque border). `0.0` yields a transparent border.

Call form used: `vfx`.`Margin`(`margin_size`=1), ``vfx`.`Margin`(`margin_size`=m, `color`=border)`, and ``vfx`.`Margin`(`margin_size`=m, `color`=border, `opacity`=0.0)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`Margin`(`margin_size`=m, `color`=border)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

With an opaque border, a corner pixel is the border `color` and a pixel inside the original rectangle is the source color.

With `opacity` `0.0`, overlaying the result as the upper layer of a `CompositeVideoClip` whose lower layer fills the grown size shows the lower clip’s color at the border and the source color in the interior.

## `clipkit.MaskColor`

Construct `MaskColor` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MaskColor`). Build a transparency mask where the picture matches a given color (with a tolerance).

### Signature

```
`MaskColor`(color=…, threshold=…)
```

- `color` — RGB triple to key.
- `threshold` — distance tolerance. Pixels whose color is within this distance of `color` become transparent; pixels far from `color` stay opaque. Exact distance formula is not pinned.

Call form used: ``vfx`.`MaskColor`(`color`=(0, 0, 0))` and ``vfx`.`MaskColor`(`color`=match, `threshold`=80)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`MaskColor`(`color`=match, `threshold`=80)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

Overlay the result as the later (upper) layer of a `CompositeVideoClip`. Pixels that matched `color` show the lower clip. Pixels far from `color` keep the upper clip. Pixels near `color` (within the tolerance) are closer to the lower clip than to their original near color.

## `clipkit.MasksAnd`

Construct `MasksAnd` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MasksAnd`). Pixelwise minimum of two masks.

### Signature

```
`MasksAnd`(other_clip)
```

- `other_clip` — first positional. The second mask clip.

Call form used: `vfx`.`MasksAnd`(other).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a mask clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MasksAnd`(other)]).

Returns a **distinct** clip. The original clip’s frames are unchanged.

The result’s mask frame at a time is the element-wise minimum of the two source mask frames at that time.

## `clipkit.MasksOr`

Construct `MasksOr` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MasksOr`). Pixelwise maximum of two masks.

### Signature

```
`MasksOr`(other_clip)
```

- `other_clip` — first positional. The second mask clip.

Call form used: `vfx`.`MasksOr`(other).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a mask clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MasksOr`(other)]).

Returns a **distinct** clip. The original clip’s frames are unchanged.

The result’s mask frame at a time is the element-wise maximum of the two source mask frames at that time.

## `clipkit.MirrorX`

Construct `MirrorX` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MirrorX`). Flip left-right (mask too, by default).

### Signature

```
`MirrorX`()
```

No required arguments.

Call form used: `vfx`.`MirrorX`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MirrorX`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a picture whose left half and right half are different colors, a left-side pixel of the result is the source’s right color and a right-side pixel is the source’s left color.

An attached `mask` is flipped the same way (a left-heavy mask becomes right-heavy). An attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.MirrorY`

Construct `MirrorY` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MirrorY`). Flip top-bottom (mask too, by default).

### Signature

```
`MirrorY`()
```

No required arguments.

Call form used: `vfx`.`MirrorY`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MirrorY`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a picture whose top half and bottom half are different colors, a top-side pixel of the result is the source’s bottom color and a bottom-side pixel is the source’s top color.

An attached `mask` is flipped the same way (a top-heavy mask becomes bottom-heavy). An attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.MultiplyColor`

Construct `MultiplyColor` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MultiplyColor`). Multiply RGB by a factor.

### Signature

```
`MultiplyColor`(factor)
```

- `factor` — first positional. Channel multiplier. `1.0` leaves the picture unchanged. A value in `(0, 1)` darkens.

Call form used: `vfx`.`MultiplyColor`(0.5) and `vfx`.`MultiplyColor`(1.0).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MultiplyColor`(factor)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a red `(255, 0, 0)` clip, the result’s red channel is `255 * factor` (within a couple of levels) and the other channels stay near `0`. Factor `1.0` matches the source picture.

This is a color-only effect: an attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.MultiplySpeed`

Construct `MultiplySpeed` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`MultiplySpeed`). Play faster or slower by a factor, or fit a final duration; duration changes accordingly. Soundtrack and mask follow.

### Signature

```
`MultiplySpeed`(factor=None, final_duration=None)
```

- `factor` — first positional. Speed multiplier. `MultiplySpeed`(2) on a 4-second clip yields duration `2`. The result’s picture at time `t` is the source’s picture at time `2 * t`.
- `final_duration` — keyword. Desired duration in seconds. The speed factor is `source_duration / `final_duration``. The result’s picture at time `t` is the source’s picture at time `t * (source_duration / `final_duration`)`.

Call form used: `vfx`.`MultiplySpeed`(2), `vfx`.`MultiplySpeed`(1.0), and `vfx`.`MultiplySpeed`(`final_duration`=D).

At least one of `factor` or `final_duration` must be supplied. Constructing `MultiplySpeed`() with neither is accepted; applying that object does not succeed. Exception class is not pinned.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`MultiplySpeed`(2)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

The same constructed object (fitted to a `final_duration`) applied to two clips yields that duration on each and maps each clip’s own timeline independently.

An attached `mask` and soundtrack are time-mapped the same way: the result’s mask frame and samples at time `t` match the source streams at the corresponding source time. Geometry-only siblings (crop, resize, rotate, mirrors) leave samples unchanged; this effect does not.

## `clipkit.MultiplyStereoVolume`

Construct `MultiplyStereoVolume` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`MultiplyStereoVolume`). Scale left and right channels by independent factors.

### Signature

```
`MultiplyStereoVolume`(left=1, right=1)
```

- `left` — multiplier for the left channel (channel 0).
- `right` — multiplier for the right channel (channel 1).

Call form used: ``afx`.`MultiplyStereoVolume`(`left`=0.2, `right`=1.0)` and ``afx`.`MultiplyStereoVolume`(`left`=1.0, `right`=1.0)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a stereo audio clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`afx`.`MultiplyStereoVolume`(`left`=L, `right`=R)])`.

Returns a **distinct** clip. The original clip’s samples are unchanged.

On a stereo clip whose both channels are amplitude `0.8`, `left`=0.2 and `right`=1.0 yields about `0.16` on the left and `0.8` on the right. Swapping the factors swaps which channel is attenuated. The result’s sample frame has two channels.

## `clipkit.MultiplyVolume`

Construct `MultiplyVolume` on the audio-effect catalog `afx` after `from `clipkit` import `afx`` (`afx`.`MultiplyVolume`). Scale volume by a factor, optionally only between two time values. Applies to an audio clip, or to a video clip’s soundtrack.

### Signature

```
`MultiplyVolume`(factor, start_time=None, end_time=None)
```

- `factor` — first positional. Volume multiplication factor. Factor `0.5` halves sample amplitude; factor `0.8` yields samples `0.8` times the original; factor `0` silences.
- `start_time` — optional. Time from which the scale applies, in seconds.
- `end_time` — optional. Time until which the scale applies, in seconds.

Call form used: `afx`.`MultiplyVolume`(0.5), `afx`.`MultiplyVolume`(1.0), `afx`.`MultiplyVolume`(0), and ``afx`.`MultiplyVolume`(k, `start_time`=t0, `end_time`=t1)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on an audio clip or a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`afx`.`MultiplyVolume`(0.5)]).

Returns a **distinct** clip. The original clip is unchanged.

Without a time window, every sample at a given time is the source sample times `factor`.

With `start_time` and `end_time`, samples inside that window are scaled and samples before and after the window match the source.

On a video clip that has a soundtrack, pictures at a given time match the source pictures (picture timing is unchanged) and the soundtrack is scaled. On a video clip that has no soundtrack, the picture is unchanged and `audio` stays `None` (no samples are invented).

## `clipkit.Painting`

Construct `Painting` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Painting`). Posterize toward a painted look.

### Signature

```
`Painting`()
```

No required arguments.

Call form used: `vfx`.`Painting`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`Painting`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

The result’s picture at a given time is not equal to the source picture at that time. Exact filters and byte polynomials are not pinned.

## `clipkit.Resize`

Construct `Resize` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Resize`). Scale the picture. Same outcomes as clip resize: naming a width keeps aspect ratio on the other axis.

### Signature

```
`Resize`(width=…)
```

- `width` — keyword. Target width in pixels. Height follows the source aspect ratio: `round(source_height * (new_width / source_width))`.

Call form used: `vfx`.`Resize`(`width`=480).

A 1024×800 clip with `width` `480` is 480 pixels wide and 375 pixels tall.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`Resize`(`width`=w)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

An attached `mask` is scaled to the same new size. An attached soundtrack’s samples at a given time match the source soundtrack at that time.

## `clipkit.Rotate`

Construct `Rotate` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Rotate`). Rotate the picture. Same outcomes as clip rotate: anticlockwise, degrees by default.

### Signature

```
`Rotate`(angle, expand=True)
```

- `angle` — first positional. Anticlockwise turn in degrees.
- `expand` — `True`: grow the canvas so the rotated picture is not clipped. Callers pass `expand`=True with `180`.

Call form used: `vfx`.`Rotate`(90) and ``vfx`.`Rotate`(180, `expand`=True)`.

`180` with `expand` true is a half turn: on a clip whose corners differ, the source top-left color sits at the result bottom-right.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`Rotate`(180, `expand`=True)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

An attached `mask` is rotated with the picture (the same corner mapping applies to mask values). An attached soundtrack’s samples at a given time match the source soundtrack at that time. Exact expanded canvas sizes and interpolation kernels are not pinned.

## `clipkit.Scroll`

Construct `Scroll` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`Scroll`). Move the picture horizontally and/or vertically.

### Signature

```
`Scroll`(x_speed=0)
```

- `x_speed` — horizontal speed in pixels per second. Positive values shift the sampled window so a mark at pixel `x` at time `0` appears near `x - round(`x_speed` * t)` at time `t`.

Call form used: `vfx`.`Scroll`(`x_speed`=1) and `vfx`.`Scroll`(`x_speed`=speed).

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`Scroll`(`x_speed`=speed)]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a still picture with a colored mark, the picture at time `0` still shows that mark at its source location. At a later time the picture is not equal to the time-`0` picture, and the mark has shifted by about `round(`x_speed` * t)` pixels horizontally when that location is still inside the frame.

## `clipkit.SlideIn`

Construct `SlideIn` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`SlideIn`). The clip enters from left, right, top, or bottom over a duration. Observable when the clip is a layer in an overlay; the standalone picture is unchanged.

### Signature

```
`SlideIn`(duration, side)
```

- `duration` — first positional. Time taken for the clip to be fully visible, in seconds.
- `side` — second positional. One of "`left`", "`right`", "`top`", "`bottom`". A value outside that set does not succeed. Exception class is not pinned.

Call form used: ``vfx`.`SlideIn`(D, "`left`")`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`SlideIn`(D, "`left`")])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged. RGB frames of the slid clip taken in isolation remain the source color at both an early time and a time after the slide.

### Overlay

Place the result as the later (upper) layer of a `CompositeVideoClip` whose first layer is an opaque same-size clip. Coverage of the upper color grows from near time `0` to after the slide duration (after the duration, coverage is almost the full frame). At a mid-slide time coverage is between those extremes. The four sides produce different mid-slide pictures. Exact pixel-displacement tables are not pinned.

## `clipkit.SlideOut`

Construct `SlideOut` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`SlideOut`). The clip exits toward left, right, top, or bottom over a duration. Observable when the clip is a layer in an overlay; the standalone picture is unchanged.

### Signature

```
`SlideOut`(duration, side)
```

- `duration` — first positional. Time taken for the clip to leave, in seconds. Applied over the last `duration` seconds of the clip.
- `side` — second positional. One of "`left`", "`right`", "`top`", "`bottom`". A value outside that set does not succeed. Exception class is not pinned.

Call form used: ``vfx`.`SlideOut`(D, "`left`")`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`SlideOut`(D, "`left`")])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged. RGB frames of the slid clip taken in isolation remain the source color at both an early time and a time near the end.

### Overlay

Place the result as the later (upper) layer of a `CompositeVideoClip` whose first layer is an opaque same-size clip whose length is that same duration `D`. Coverage of the upper color shrinks from near time `0` to near the end. At a mid-slide time coverage is between those extremes. The four sides produce different mid-slide pictures. Exact pixel-displacement tables are not pinned.

## `clipkit.SuperSample`

Construct `SuperSample` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`SuperSample`). Replace the frame at time `t` by the mean of N equally spaced nearby frames.

### Signature

```
`SuperSample`(d, n_frames)
```

- `d` — first positional. Half-window in seconds. Nearby times lie in `[t - d, t + d]`.
- `n_frames` — second positional. Number of equally spaced samples in that window.

Call form used: ``vfx`.`SuperSample`(0.05, 2)` and ``vfx`.`SuperSample`(d, n)`.

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: `clip.`with_effects`([`vfx`.`SuperSample`(d, n)])`.

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip that switches color at time `t`, a 1-sample window at that `t` matches one of the two source colors. A 5-sample window at that `t` matches neither source color and does not match the 1-sample result (the mean mixes both sides). Exact sample placement inside the window is not pinned beyond equally spaced nearby frames.

## `clipkit.TextClip`

Import `TextClip` from the package root `clipkit` (`from `clipkit` import `TextClip``). Still picture of rendered Unicode text. `TextClip` is an `ImageClip` (same picture at every time). Construction does not require the media encoder.

### Signature

```
`TextClip`(font=None, text=None, filename=None, font_size=None, size=(None, None), margin=(None, None), color="black", bg_color=None, stroke_color=None, stroke_width=0, method="label", text_align="left", horizontal_align="center", vertical_align="center")
```

- `font` — filesystem path as a string to an OpenType font file (`.ttf` / `.otf`). Default `None`: the built-in default font. A path that cannot be opened as an OpenType font does not succeed.
- `text` — the string to render. Unicode is accepted; `"Cafe"` and `"Café"` produce distinguishable pictures.
- `filename` — filesystem path as a string to a text file whose contents are rendered instead of `text`. A clip from a file matches a clip from the same string passed as `text`; a different file body produces a different picture. Either `text` or `filename` must be supplied. With neither, the call does not succeed.
- `font_size` — size in points, or `None`.
- `size` — picture size `(width, height)` in pixels. Either member may be `None` (compute that dimension). Caption requires a width.
- `margin` — extra padding around the text. A pair `(horizontal, vertical)` or a quadruple `(left, top, right, bottom)`. A scalar or a triple does not succeed.
- `color` — text color: an RGB triple such as `(255, 0, 0)`, an RGBA quadruple, a color name (`red`, `blue`), or hexadecimal (`#FF0000`). Hexadecimal `#FF0000` matches RGB `(255, 0, 0)`. Named `red` and `blue` produce distinguishable pictures. An RGBA fill is distinguishable from a different RGB fill.
- `bg_color` — background color, same encodings as `color`. Default `None`: transparent background (a `mask` is attached; pixels outside the glyphs have low visibility). An opaque background shows that color in the non-glyph region.
- `stroke_color` — outline color, or `None` (no stroke). Combined with `stroke_width`, the outline is adjacent to the fill.
- `stroke_width` — outline width in pixels. Default `0`. Different positive widths produce distinguishable pictures.
- `method` — layout. Only `label` and `caption` succeed. Any other string does not succeed.
- `text_align` — alignment of lines inside the text block: `left` (default), `center`, or `right`. Default matches explicit `left`. Left ink sits left of center ink, which sits left of right ink.
- `horizontal_align` — placement of the text block in the picture: `left`, `center` (default), or `right`.
- `vertical_align` — placement of the text block in the picture: `top`, `center` (default), or `bottom`. Default block placement is center on both axes. Left is left of right; top is above bottom.

Call form used: ``TextClip`(`font`=…, `text`=…, `font_size`=…, `color`=…)` and the same keywords with `filename`, `method`, `size`, `bg_color`, `text_align`, `horizontal_align`, `vertical_align`, `stroke_color`, `stroke_width`, and `margin`. Omitting `font` uses the default font. Exception class and failure wording are not pinned.

Returns a still-image clip. Newly constructed `start` is `0`.

### Frame at a time

```
`get_frame`(t)
```

Returns a numeric RGB picture. Glyph-region pixels match the requested text color, not a blank canvas. `"Hello"` is distinguishable from `"World"` at the same font, size, and color. Two different fonts at the same string, size, and color are distinguishable; the same font file copied to two paths is not.

### Layout: `label` (default)

`method` `label`, which is also the default when `method` is omitted (omitted matches explicit `label`). The picture is sized to the text. With a given `font_size`, a longer string is wider (`shape[1]` larger). A larger `font_size` at the same string is taller (`shape[0]` larger).

### Layout: `caption`

`method` `caption`. Width is mandatory: ``size`=(None, height)` does not succeed; ``size`=(width, None)` or ``size`=(width, height)` does. Height or `font_size` must be given: caption with ``size`=(width, None)` and no `font_size` does not succeed.

When `font_size` is omitted and both width and height are given, font size is chosen to fit the box. A taller box yields taller ink (larger glyph bounding-box height). The returned picture has exactly that width and height.

When height is omitted (``size`=(width, None)`) and `font_size` is given, height is computed. The picture width equals the requested width. A larger `font_size` yields a taller picture. The same wrapping text at a narrower width yields a taller picture than at a wider width.

## `clipkit.TimeMirror`

Construct `TimeMirror` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`TimeMirror`). Play the clip backward. Soundtrack and mask follow. Requires a duration.

### Signature

```
`TimeMirror`()
```

No required arguments.

Call form used: `vfx`.`TimeMirror`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`TimeMirror`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip of duration `D`, the result’s picture at time `t` matches the source’s picture at time `D - t`. An attached `mask` and soundtrack are reversed the same way: mask frames and samples at `t` match the source streams at `D - t`.

Applying to a clip that has no duration does not succeed. After a duration is assigned, the same effect succeeds. Exception class is not pinned.

## `clipkit.TimeSymmetrize`

Construct `TimeSymmetrize` on the visual-effect catalog `vfx` after `from `clipkit` import `vfx`` (`vfx`.`TimeSymmetrize`). Play forward then backward; duration doubles. Soundtrack and mask follow. Requires a duration.

### Signature

```
`TimeSymmetrize`()
```

No required arguments.

Call form used: `vfx`.`TimeSymmetrize`().

### Application

Pass the constructed effect in a one-element list to `with_effects` on a video clip:

```
`with_effects`([effect])
```

Call form used: clip.`with_effects`([`vfx`.`TimeSymmetrize`()]).

Returns a **distinct** clip. The original clip’s pictures are unchanged.

On a clip of duration `D`, the result’s `duration` is `2 * D`. After the midpoint, playback is the forward clip mirrored: the result’s picture at time `D + t` matches the source’s picture at time `D - t`. An attached `mask` and soundtrack follow that same map.

Applying to a clip that has no duration does not succeed. After a duration is assigned, the same effect succeeds. Exception class is not pinned.

## `clipkit.VideoClip`

Import `VideoClip` from the package root `clipkit` (`from `clipkit` import `VideoClip``). Base video clip. A generated clip takes a caller function of time that returns a height × width × 3 picture. Solid-color clips (`ColorClip`) are video clips and expose the same timing, soundtrack, iteration, and encode operations.

### Signature

```
`VideoClip`(frame_function=None, is_mask=False, duration=None)
```

- `frame_function` — callable `t → picture`. Required for a generated clip. `t` is a time in seconds (already converted from any accepted time encoding). The return is a numeric array: height × width × 3 with integer channels in 0–255 for a non-mask clip. At time t the clip’s frame is exactly that function’s picture at t (a function whose red channel depends on t has different pictures at t = 0 and t = 0.5).
- `duration` — length in seconds, or `None` (infinite). Supply a duration at construction for the clip to be finite.
- `is_mask` — default `False`. Callers constructing a generated RGB clip omit it.

Call form used: ``VideoClip`(`frame_function`=…, `duration`=…)`.

Returns a video clip. Newly constructed `start` is `0`. When `duration` is supplied, `end` is that duration.

### `get_frame`

```
`get_frame`(t)
```

- `t` — a time value: a number of seconds, a (minutes, seconds) pair, a (hours, minutes, seconds) triple, or a clock string. A comma is accepted as the decimal separator. `1.5`, `(0, 1.5)`, `"00:00:01.5"`, and `"00:00:01,5"` request the same moment. The frame function receives the converted number of seconds.

Returns the picture at that clip-local time. Indexing `frame[0, 0, 0]` is the first pixel’s red channel. Asking twice at the same time on a deterministic function returns pictures that match. Changing composition `start` does not shift clip-local time: `get_frame`(0) after `with_start` still matches the original `get_frame`(0), not the original frame at the new start time.

### Copy-on-modify

Each operation returns a **distinct** clip and leaves the original unchanged.

```
`with_duration`(duration, change_end=True)
```

- `duration` — a time value, or `None`. See time encodings on the product surface.
- `change_end` — default `True`: `end` = `start` + duration. `False` with `duration=None` does not succeed.

```
`with_end`(t)
```

Sets `end` from a time value and `duration` to `end` − `start`.

```
`with_start`(t, change_end=True)
```

- `t` — new composition `start` (time value). Clip-local frame 0 is unchanged.
- `change_end` — default `True`: keep duration, move end. `False`: keep end, shorten duration.

```
`with_fps`(fps, change_duration=False)
```

- `fps` — frames per second; default for iteration and encode.
- `change_duration` — default `False`: duration unchanged. `True`: conserve every frame 1:1 and scale duration inversely. After halving the rate, the picture at time `2 * t0` on the result matches the original picture at `t0`, not the original picture at `2 * t0`. The original clip’s `duration` and `fps` stay as they were.

```
`copy`()
```

No arguments. Distinct replica.

```
`with_audio`(audioclip)
```

Distinct copy; `audio` is the given `AudioClip`. Pictures unchanged. Original `audio` unchanged.

```
`without_audio`()
```

No arguments. Distinct copy; `audio` is `None`.

```
`with_mask`(mask)
```

Distinct copy; `mask` is the given mask clip (a video clip constructed with `is_mask` true). clip.`mask`.`get_frame`(t) yields that mask’s frame at t. Original pictures and `audio` unchanged.

```
`without_mask`()
```

No arguments. Distinct copy; the attached `mask` is stripped. Overlaying that stripped clip as the upper layer of a `CompositeVideoClip` covers the lower layer fully. Overlaying the still-masked sibling mixes: pixels where the mask is 1 show the upper clip; where it is 0 the lower clip shows through.

```
`with_opacity`(factor)
```

- `factor` — first positional. Call form used: `with_opacity`(0.5).

Distinct copy. Overlaying the result as the upper layer of a `CompositeVideoClip` blends with the layer below: at factor `0.5` the overlay picture is not the lower clip’s color and not the upper clip’s color. Overlaying the same faded clip on a different lower layer yields a different picture. Overlaying the original unfaded clip replaces the lower layer. Blend formula is not pinned.

### Color ↔ mask conversion

A video clip (including `ColorClip`) exposes:

```
`to_mask`()
```

No arguments. Call form used: `to_mask`().

Returns a mask clip. Frames are greyscale height × width with values in 0–1.

On an RGB clip, one channel is scaled from 0–255 into 0–1: white `(255, 255, 255)` yields values near 1; black `(0, 0, 0)` yields values near 0; a grey `(v, v, v)` yields values near `v / 255` (distinguishable from both 0 and 1 when `v` is neither extreme). Which channel is used on a non-grey RGB picture is not pinned. 8-bit rounding tables are not pinned.

On a clip that is already a mask, frames are unchanged: `get_frame` after `to_mask` matches `get_frame` before.

```
`to_RGB`()
```

No arguments. Call form used: `to_RGB`().

Returns an RGB clip. Frames are height × width × 3 with integer channels in 0–255.

On a mask clip, the greyscale value is repeated into three 0–255 channels: a mask of `1` yields white `(255, 255, 255)`; a mask of level `L` in 0–1 yields three equal channels near `L * 255`. 8-bit rounding tables are not pinned.

On a clip that is already RGB, pictures are unchanged: `get_frame` after `to_RGB` matches `get_frame` before.

### Resize, crop, and rotate

Each of the following returns a **distinct** clip and leaves the original’s pictures, `mask`, and `size` unchanged.

```
`resized`(…)
```

Call forms used:

- positional `(width, height)` pair: both axes become those pixel sizes, even when that aspect differs from the source;
- positional scale factor: both axes multiply by that factor;
- keyword `width` alone: that axis becomes the named pixel width and the other axis follows the source aspect ratio;
- keyword `height` alone: that axis becomes the named pixel height and the other axis follows the source aspect ratio.

A 1024×800 clip with `width` `480` is 480 pixels wide and 375 pixels tall. Frames from `get_frame` have that new size.

When `apply_to_mask` is omitted, an attached `mask` is scaled to the same new size (a right-heavy mask stays right-heavy on the result). Passing `apply_to_mask`=`False` still scales the picture but leaves that mask’s frames at the source size.

```
`cropped`(…)
```

Keeps a rectangular subregion. Coordinates are in pixels. Frames of the result are exactly that rectangle; pixels outside it are absent. An attached `mask` is cropped the same way. Call forms used:

- opposite corners: keywords `x1`, `y1`, `x2`, `y2`. The kept rectangle is the half-open pixel window from `(`x1`, `y1`)` to `(`x2`, `y2`)`. A 10×10 clip with `x1` `0`, `y1` `0`, `x2` `5`, `y2` `10` yields 5×10 frames;
- top-left plus size: keywords `x1`, `y1`, `width`, `height`. Same rectangle as opposite corners with `x2` `=` `x1` `+` `width` and `y2` `=` `y1` `+` `height`;
- center plus size: keywords `x_center`, `y_center`, `width`, `height`. The kept rectangle is centred on `(`x_center`, `y_center`)` with that `width` and `height` — the center is not treated as a top-left origin.

When `x2` is left of `x1`, or `y2` is above `y1`, the call either does not succeed or returns a clip whose observable `size` is a `(width, height)` pair that is **not** both-positive. A successful `get_frame` on that clip also does not yield a picture whose both spatial dimensions are positive. Exception class is not pinned. A well-ordered sibling crop of the same source still yields the positive-size rectangle.

```
`rotated`(angle, expand=…, unit=…)
```

- `angle` — first positional. Anticlockwise turn. Degrees when `unit` is omitted; radians when `unit` is the token `"rad"`. `180` with `expand` true, and `π` with `expand` true and `unit` `"rad"`, match as a half turn: on a clip whose corners differ, the source top-left color sits at the result bottom-right and the source bottom-right color sits at the result top-left. `90` with `expand` true is a quarter turn anticlockwise: the source top-left color sits at the result bottom-left, not at the top-right or bottom-right.
- `expand` — `True`: grow the canvas so a non-orthogonal turn is not clipped (result width or height exceeds the source). `False`: keep the source size; a non-orthogonal turn clips the corners. Exact expanded canvas sizes and interpolation kernels are not pinned.
- `unit` — omit for degrees; pass `"rad"` for radians.

An attached `mask` is rotated with the picture (the same corner mapping applies to mask values).

### Placement and layer index

```
`with_position`(pos, relative=…)
```

Distinct copy used when the clip is a layer in a `CompositeVideoClip`. The origin is the composition top-left. A position names the layer’s top-left. Without this call, a layer sits at `(0, 0)`. Call forms used:

- a single keyword: `"center"` (both axes centered), `"left"`, `"right"`, `"top"`, or `"bottom"` (the named edge is flush; the missing axis is centered);
- a `(horizontal, vertical)` keyword pair, for example `("center", "top")` (horizontally centered, flush top) or `("right", "bottom")` (flush bottom-right);
- a pixel pair `(x, y)`;
- a pair of fractions with `relative`=`True`: `(0.4, 0.7)` puts the top-left at 40% of the composition width and 70% of the composition height (integer pixel `int(0.4 * width)`, `int(0.7 * height)`). The same pair **without** `relative` is a pixel pair, not those percentages;
- a function of time that returns a coordinate pair: the layer’s top-left at time `t` is that function’s value at `t`.

A keyword other than `center`, `left`, `right`, `top`, or `bottom` is not a valid placement: assigning it, composing the result, or asking `get_frame` of that composition does not succeed as a placement of that keyword. Exception class is not pinned. The original clip is unchanged.

```
`with_layer_index`(index)
```

First positional is an integer. Distinct copy. When layers are composed with `CompositeVideoClip`, a greater index is drawn on top of a lesser one even when the greater-index clip is first in the clip list.

### Time slice and skip

```
`subclipped`(A, B)
```

Positional time slice. First argument is the start time value; second is the end time value and may be omitted.

- With both arguments, `duration` of the result is B − A. `get_frame`(t) is the source picture at A + t, not the source picture at t.
- Omitting the end uses the source `duration` as B: the result matches ``subclipped`(A, source.`duration`)`.
- A and B are time values (number of seconds, (minutes, seconds) pair, or clock string).
- Negative A or B count from the end: start −X on duration D is D − X. `subclipped`(-1) (end omitted) is the last second. ``subclipped`(0, -2)` drops the last two seconds.
- Attached `audio` and `mask`, if any, are sliced the same way: samples and mask frames at t are the source streams at A + t. The original clip’s duration, pictures, soundtrack, and mask stay as they were.
- Returns a distinct clip.

Does not succeed, and does not return a clip, when:

- start is at or after the source duration (end omitted, or end equal to that start);
- start is after the source duration;
- end is after the source duration;
- a negative bound is used and `duration` is `None`.

After `with_duration` assigns a duration, those negative bounds succeed. Exception class is not pinned.

```
`with_section_cut_out`(C, D)
```

Two positional time values. Returns a distinct clip that plays the source up to C and then continues from D. `duration` is shortened by D − C. `get_frame` just after C matches the source just after D — not the source at that local time, not the skipped interval, and not a stretch of the shortened duration onto the original. Attached `audio` and `mask` are skipped the same way. The original clip is unchanged.

### Time, picture, and joint filters

Each of the following returns a **distinct** clip. The original’s pictures, attached `mask`, and `audio` stay as they were.

```
`time_transform`(…)
```

First positional is a callable `t → t′`. The result’s picture at t is the source picture at t′. Mapping t to `2 * t` plays twice as fast: the picture at 0.5 matches the source at 1.0, not the source at 0.5.

- `apply_to` — keyword. A list of stream names that receive the same time map. The tokens "`mask`" and "`audio`" name the attached mask and soundtrack. `[]` names neither.

Call forms used: ``time_transform`(lambda t: 2 * t)`, ``time_transform`(…, `apply_to`=["`mask`", "`audio`"])`, and ``time_transform`(…, `apply_to`=[])`.

When `apply_to` is omitted:

- On an animated clip, the time map does not rewrite mask or soundtrack: mask frames and samples at t match the source streams at t, not at t′.
- On a still-image clip, the picture is unchanged (the same still at every time) and the time map is applied to mask and soundtrack: mask frames and samples at t match the source streams at t′.

Passing `apply_to`=`["`mask`", "`audio`"]` on an animated clip applies the time map to those streams: mask frames and samples at t match the source at t′. Passing `apply_to`=`[]` on a still-image clip leaves mask and soundtrack unmapped: they match the source at t.

```
`image_transform`(…)
```

First positional is a callable picture → picture. It is run on each frame. Swapping the green and blue channels is visible in the result.

Call form used: `image_transform`(func).

On a still-image clip, every time yields the same transformed still. On an animated clip, the callable runs on each frame: frames that differed before still differ after, and each is the transformed source frame at that time, not the untransformed source.

```
`transform`(…)
```

First positional is a callable `(get_frame, t) → picture`. The first argument fetches the source picture: get_frame(t′) is the source frame at time t′. The return is the result’s picture at t.

Call form used: ``transform`(lambda get_frame, t: get_frame(2 * t))`. The same t→2t map through this entry matches `time_transform` with that map: the picture at 0.5 matches the source at 1.0. A callable that crops a vertical window whose origin depends on t is a time-dependent crop: early and late pictures differ, and each matches the corresponding source rows. A caller-defined `Effect` may return clip.`transform`(filter) from `apply`.

### `iter_frames`

```
`iter_frames`(logger=None)
```

- `logger` — `None` is accepted (no progress bar). Uses the clip’s `fps` when no rate is passed.

Returns an iterator of pictures. Yields `int(`duration` * `fps`)` whole frames (1 second at 60 fps yields 60). The i-th picture matches `get_frame` at the corresponding time in a uniform sampling of duration at that rate (slot `1 / `fps``). Without `duration` the call does not succeed; the failure identifies that duration is missing. The same clip iterates after `with_duration`.

### Encode

`logger`=`None` is accepted. Video write uses FFmpeg; GIF write, image-sequence write, and still-frame write do not.

```
`save_frame`(filename, t=…, with_mask=…)
```

- `filename` — destination path as a string (a `.png` path). First positional argument.
- `t` — time of the frame to write. A numeric second or a clock string. Omitted: time 0.
- `with_mask` — omitted: alpha is left on (the default). `False`: omit the attached mask as alpha.

Call forms used: `save_frame`(path), ``save_frame`(path, `t`=…)`, and ``save_frame`(path, `with_mask`=False)`.

On success the path is a nonempty PNG whose pixels match `get_frame` at that time (time 0 when `t` is omitted). A numeric `t` and a clock string for the same instant write matching pictures, not the time-0 picture. When the clip has an attached `mask` and alpha is left on, that PNG has an alpha channel matching the mask: pixels where the mask is 1 are near-opaque; where it is 0 are near-transparent; distinct in-between mask values produce distinct in-between alpha. Passing `with_mask`=`False` writes the picture without that mask as alpha. Exact 8-bit rounding of mask 0–1 into alpha 0–255 is not pinned. Still-frame write does not require `duration` or `fps`.

```
`write_videofile`(filename, fps=None, audio=True, logger=None, codec=…, bitrate=…, audio_bitrate=…, pixel_format=…, preset=…, threads=…, temp_audiofile=…, remove_temp=…)
```

- `filename` — destination path as a string. First positional argument.
- `fps` — default `None`: use the clip’s `fps`. A write-time rate is used when supplied. The written container’s video frame rate matches that assigned rate (within a small muxer tolerance). Two different write-time rates produce distinguishable frame counts or container rates. Without a rate on the clip and none at write, the call does not succeed and identifies that frame rate is missing.
- `audio` — default `True`. When `True` and a soundtrack is attached, the file contains that soundtrack. `False` omits audio from the container even if a soundtrack is attached. A filesystem path string names a replacement soundtrack file: the container’s audio is that file’s sound, not the clip’s attached soundtrack.
- `codec` — video encoder name. When omitted, default by extension: mp4, mkv, and mov use libx264; ogv uses libtheora; webm uses libvpx. Extension avi has no default: the caller must name a codec (for example `"mpeg4"`); without one the call does not succeed, identifies that a codec must be supplied, and does not leave a nonempty media file. An unknown extension likewise requires a named codec. A named `codec` overrides the extension default (`"mpeg4"` on `.mp4` is mpeg4, not h264). A codec name FFmpeg does not know does not produce a nonempty media file FFmpeg can open; the call may return as completed; that return is not a successful encode.
- `bitrate` — video bitrate string (for example `"64k"`, `"4000k"`). Distinct values produce distinct encoded file sizes. The picture still matches the source within ordinary lossy tolerance.
- `audio_bitrate` — soundtrack bitrate string (for example `"32k"`, `"192k"`). Distinct values produce distinct encoded file sizes. The muxed tone is still present.
- `pixel_format` — pixel format written into the file (for example `"rgb24"`, `"rgba"`). Distinct values produce distinct probed formats. Pictures still match.
- `preset` — compression preset. One of: ultrafast, superfast, veryfast, faster, fast, medium (the default when omitted), slow, slower, veryslow, placebo. Changes file size and encode time, not the documented picture content. Each listed preset writes a loadable picture.
- `threads` — integer thread count (for example `3`). The write still produces a loadable picture.
- `temp_audiofile` — filesystem path for a companion audio file used while muxing. When omitted, a successful write leaves no leftover companion audio file next to the video.
- `remove_temp` — omitted: the named companion is not left. `False`: keep the named `temp_audiofile` after write; that path exists, is nonempty media, and contains the soundtrack.

Default audio codec in the video file is libmp3lame, except ogv and webm which default to libvorbis.

Call forms used include ``write_videofile`(path, `logger`=None)`, ``write_videofile`(path, `fps`=…, `audio`=False)`, ``write_videofile`(path, `audio`=path_string)`, ``write_videofile`(path, `codec`=…)`, ``write_videofile`(path, `bitrate`=…)`, ``write_videofile`(path, `audio_bitrate`=…)`, ``write_videofile`(path, `pixel_format`=…)`, ``write_videofile`(path, `preset`=…)`, ``write_videofile`(path, `threads`=…)`, and ``write_videofile`(path, `temp_audiofile`=…, `remove_temp`=False)`.

On success the path is a nonempty media file FFmpeg can open. Without `duration` the call does not succeed, identifies that duration is missing, and does not produce a nonempty media file. When FFmpeg is unreachable, the call does not succeed and the process status is not 0. A zero-byte file is not a successful encode.

```
`write_gif`(filename, fps=None, logger=None, loop=…)
```

- `filename` — `.gif` path as a string.
- `fps` — default `None`: use the clip’s `fps`. A write-time rate is used when supplied. Playback length matches duration at that frame rate. Two durations at the same rate, or two rates at the same duration, produce distinguishable GIF frame counts.
- `loop` — optional loop count stored in the GIF. Distinct values (for example `2` and `8`) produce distinguishable stored loop counts. GIF loop-field spelling is not pinned.

Call forms used: ``write_gif`(path, `logger`=None)` and ``write_gif`(path, `loop`=…)`.

GIF write iterates ordinary color frames; it does not store the clip’s mask as GIF transparency. Does not require FFmpeg. Without `duration`, or without a frame rate on the clip and none at write, the call does not succeed and does not leave a nonempty GIF.

```
`write_images_sequence`(name_format, fps=None, logger=None, with_mask=…)
```

- `name_format` — pattern with an integer placeholder, for example `frame%03d.png` or `frame_%d.png`. First positional.
- `fps` — default `None`: use the clip’s `fps`. A write-time rate is used when supplied.
- `with_mask` — omitted: alpha is left on (the default). When a mask is present and alpha is left on, PNG sequences include that mask as alpha (mask 1 near-opaque, mask 0 near-transparent). Passing `with_mask`=`False` writes the picture and omits that mask as alpha.

Call forms used: ``write_images_sequence`(pattern, `logger`=None)` and ``write_images_sequence`(pattern, `with_mask`=False)`.

Returns the list of paths; each path exists and is nonempty. The first image matches the frame at time 0. The count of files matches the number of frames. Does not require FFmpeg. Without `duration`, or without a frame rate on the clip and none at write, the call does not succeed and does not leave a nonempty `frame*.png`. After duration and rate are assigned, the pattern produces nonempty frame files.

### Equality

Two video clips constructed the same way from the same still pictures, same duration, and same frame rate compare equal. Changing the pictures or the duration makes them unequal.

### Observable attributes

- `start`, `end`, `duration`, `fps`, `audio` — same meaning as on `ColorClip`.
- `mask` — attached mask clip after `with_mask`; `mask`.`get_frame`(t) is that mask’s frame at t.
- `size` — pair `(width, height)` in pixels. Indexing `size`[0], `size`[1] is width then height. Present on a clip that has a defined picture size (including `ColorClip`) and on the result of `cropped`. This is not the same observable as a frame’s `shape` from `get_frame`.

## `clipkit.VideoFileClip`

Import `VideoFileClip` from the package root `clipkit` (`from `clipkit` import `VideoFileClip``). File-backed video clip: pictures come from a video file through the FFmpeg decoder. `VideoFileClip` is a `VideoClip`. Construction requires an invocable FFmpeg decoder.

### Signature

```
`VideoFileClip`(filename, audio=True, target_resolution=None)
```

- `filename` — first positional. Filesystem path as a string to a video file FFmpeg can decode, including MP4, WebM, MOV, AVI, MPEG, OGV, and GIF.
- `audio` (`bool`) — default `True`. When `True` and the file has an audio stream, the clip carries a soundtrack. When `False`, `audio` is `None` even if the file has an audio stream.
- `target_resolution` — default `None`: keep the file’s video size. Otherwise a pair `(width, height)` naming a target size for the decoder to apply while reading. Either member may be `None` (that dimension is not named).

Call form used: `VideoFileClip`(path), ``VideoFileClip`(path, `audio`=False)`, ``VideoFileClip`(path, `target_resolution`=(None, height))`, ``VideoFileClip`(path, `target_resolution`=(width, None))`, and ``VideoFileClip`(path, `target_resolution`=(width, height))`.

Returns a video clip. Newly constructed `start` is `0`. `duration`, `fps`, and `size` match the file’s video stream (duration and frame rate within ordinary muxer / container tolerance). `end` is that duration. `size` is the pair `(width, height)` in pixels.

When the FFmpeg decoder is unreachable, construction does not succeed: no clip that yields frames is returned. When the decoder is invocable, the same path constructs successfully.

A path that does not exist does not succeed. A path that is a directory does not succeed (even if a readable video file sits inside that directory; opening that nested file path does succeed). A file that is not readable media does not succeed. A corrupted video whose duration or dimensions cannot be parsed does not succeed. In each of those failures, the caller-visible failure identifies the offending path (the path’s filename or the full path string appears in the failure), and no clip that yields frames is returned. Exception class and exact wording are not pinned.

### Decoder resize

When `target_resolution` is omitted, `size` and each `get_frame` picture match the file stream’s width and height.

When only height is named (`(None, H)`), `size` height is `H` and width keeps the file’s aspect ratio (`H * (file_width / file_height)`). When only width is named (`(W, None)`), `size` width is `W` and height keeps the file’s aspect ratio. When both are named (`(W, H)`), `size` is exactly `(W, H)` even if that aspect differs from the file. Frames from `get_frame` have that size — not a later resize of a full-resolution picture.

### Soundtrack

When the file has an audio stream and `audio` is left on (the default), clip.`audio` is not `None`. That soundtrack’s `duration` matches the file’s audio stream, not the video stream, when those durations differ. Asking the soundtrack for sound at times inside that duration yields the stored audio (a written tone is present at the decode rate). The soundtrack’s `fps` is 44100 samples per second.

Passing `audio` `False` sets clip.`audio` to `None`. Pictures at time t still come from the file.

### `get_frame`

```
`get_frame`(t)
```

- `t` — a time in seconds inside the clip (less than `duration`).

Returns the picture at that time in the file, not a solid placeholder: a numeric array of shape `(height, width, 3)` with integer channels in 0–255. `frame.shape[0]` is height; `frame.shape[1]` is width. A file that is one color in the first half and another in the second returns those colors at times in each half (within ordinary lossy-codec tolerance); the two halves are distinguishable. Opening the same path after the file’s contents have been replaced returns the new file’s pictures, not the previous file’s.

Asking twice at the same time on a deterministic file returns pictures that match.

### Copy-on-modify and encode

```
`with_audio`(audioclip)
```

Returns a **distinct** clip; the original is unchanged (same `duration`, `fps`, `size`, and `audio`). The result’s `duration`, `fps`, and `size` remain those of the file. Pictures still come from the file. The result’s `audio` is the given audio clip.

```
`write_videofile`(filename, logger=None)
```

- `filename` — destination path as a string. First positional.
- `logger` — `None` is accepted (no progress bar).

When `fps` is omitted at write time, the written container’s duration, frame rate, and size match the loaded clip’s (the file’s) duration, frame rate, and size. Invokes the FFmpeg encoder. On success the path is a nonempty media file.

A derived clip from `with_audio` still needs the source file: after the source is closed, `get_frame` on the derived clip does not succeed.

### `close` and context manager

```
`close`()
```

No arguments. Releases the file. After `close`, `get_frame` on that instance does not succeed. Exception class is not pinned.

The clip is a context manager:

```
with `VideoFileClip`(path) as clip:
    ...
```

Inside the block, `get_frame` succeeds. Leaving the block has the same effect as `close`: further `get_frame` on that instance does not succeed.

## `clipkit.afx`

`afx` is the audio-effect catalog of the package `clipkit`. Import it from the package root (`from `clipkit` import `afx``). Each catalog entry is a first-class effect object: construct it, then apply it by passing a list of such objects to `with_effects` on a clip. Applying an effect returns a modified copy; the original clip is left unchanged.

These names are callable as ``afx`.<name>` after that import:

- `AudioDelay`
- `AudioFadeIn`
- `AudioFadeOut`
- `AudioLoop`
- `AudioNormalize`
- `MultiplyStereoVolume`
- `MultiplyVolume`

Typical import:

```
from `clipkit` import `afx`
```

A program that only needs those effects may import `afx` alone, for example `from `clipkit` import `afx``.

An audio effect applied to a video clip that has a soundtrack modifies that soundtrack and leaves the picture timing in place. An audio effect applied to a video clip that has no soundtrack leaves the picture unchanged and does not invent samples (`audio` stays `None`).

## `clipkit.clips_array`

Import `clips_array` from the package root `clipkit` (`from `clipkit` import `clips_array``). Juxtaposition: lay video clips out in a rectangular grid, all cells visible at the same time.

### Signature

```
`clips_array`(array)
```

- `array` — first positional. A list of rows, each row a list of video clips. ``clips_array`([[a, b, c]])` is one row of three cells. ``clips_array`([[a, b], [c, d]])` is two rows of two cells. ``clips_array`([[top], [bottom]])` is two rows of one cell.

Call form used: ``clips_array`([[clip_a, clip_b, clip_c]])`.

Returns a video clip. The layout is spatial, not a temporal sequence: every cell is present in the same frame.

### Cell size and canvas

Each column’s width is the maximum width of clips in that column. Each row’s height is the maximum height of clips in that row. The result’s width is the sum of those column widths; the result’s height is the sum of those row heights.

A 1×3 grid of equal-size clips of width W and height H therefore has width `3 × W` and height H. A two-row stack of height H1 then H2 has height H1 + H2.

A clip smaller than its cell is centered in that cell: an interior pixel of that centered rectangle shows that clip; a cell corner that lies outside that rectangle does not show that clip’s color.

### Frame at a time

```
`get_frame`(t)
```

- `t` — a time in seconds.

Returns one RGB picture of the full grid (height × width × 3, integer channels in 0–255). In a left-to-right row, cell `i` occupies horizontal pixels `[i × W, (i + 1) × W)` when every cell is width W. In a top-to-bottom stack, the second row begins at pixel row equal to the first row’s height.

### Encode without duration

A grid whose cell clips have no `duration` has no duration. Calling `write_videofile` on that result does not succeed: the failure identifies that duration is missing, and no nonempty media file is left at the destination. Assigning a duration with `with_duration` makes the same grid writable. Having a frame rate on the cell clips is not a substitute for duration. `logger`=`None` is accepted (no progress bar).

## `clipkit.concatenate_audioclips`

Import `concatenate_audioclips` from the package root `clipkit` (`from `clipkit` import `concatenate_audioclips``). Play audio clips one after another, in list order.

### Signature

```
`concatenate_audioclips`(clips)
```

- `clips` — first positional. A list of audio clips (for example `AudioClip` or `AudioArrayClip` instances).

Call form used: ``concatenate_audioclips`([clip_a, clip_b])` and ``concatenate_audioclips`([clip_a, clip_b, clip_c])`.

Returns an audio clip.

### Sequence and duration

Members play in order, not as an overlap. `duration` is the sum of the members’ durations. Composition starts are 0, then the running sum of previous durations: concatenating a 2-second clip and a 5-second clip has `duration` 7, and the second clip is the sound at t = 4 (local time 2 into that second clip). Concatenating three durations D1, D2, D3 has `duration` D1 + D2 + D3.

```
`get_frame`(t)
```

- `t` — composition time in seconds.

Returns a numeric array of length 1 (mono) or length 2 (stereo) with floating-point samples. In the first member’s span, samples match that member at local time `t`. In a later member’s span, samples match that member at `t` minus the sum of the previous durations — not that member at composition time `t`, and not a previous member’s samples.

Just before a boundary the first member is still playing; just after it the next member has started.

### Sample rate and channel count

`fps` is the maximum sample rate among the members. Channel count of `get_frame` is the maximum channel count among the members: concatenating mono with stereo yields size 2.

## `clipkit.concatenate_videoclips`

Import `concatenate_videoclips` from the package root `clipkit` (`from `clipkit` import `concatenate_videoclips``). Play video clips one after another, in list order.

### Signature

```
`concatenate_videoclips`(clips, `method`="`chain`", `transition`=None, `padding`=0)
```

- `clips` — first positional. A list of video clips. Every clip must have a `duration`.
- `method` — `chain` or `compose`. Those two tokens are the only accepted methods.
- `transition` — default `None`: nothing extra is inserted between members. Otherwise a video clip that is played between each consecutive pair.
- `padding` — default `0`. Seconds added between each consecutive pair. Positive padding is a gap; negative padding overlaps the end of one clip with the start of the next. A non-zero `padding` does not switch `method` from `chain` to `compose`.

Call forms used: ``concatenate_videoclips`([a, b], `method`="`chain`")`, ``concatenate_videoclips`([a, b], `method`="`compose`")`, ``concatenate_videoclips`([a, b], `method`="`compose`", `padding`=…)`, ``concatenate_videoclips`([a, b], `method`="`chain`", `padding`=…)`, and ``concatenate_videoclips`([a, b, c], `method`="`compose`", `transition`=trans)`.

Returns a video clip.

### `method` `chain`

Frames come from each clip in turn with no size correction. If sizes differ, each segment keeps that clip’s own size: asking `get_frame` in the first span yields the first clip’s width × height; asking in the second span yields the second clip’s width × height — not the maximum of the two.

If any input has a `mask`, the result has a concatenated `mask`. In a span whose source had a mask, that mask’s 0–1 picture is the concat mask. In a span whose source had none, the concat mask is opaque (near 1) at every pixel of that segment’s size.

### `method` `compose`

The result’s size is the maximum width × maximum height among the clips. Every `get_frame` picture has that size. A smaller clip appears centered on that canvas: an interior pixel of that centered rectangle shows the clip; a pixel just outside that rectangle does not show that clip’s color.

### Duration, padding, and transition

With no padding and no transition, `duration` is the sum of the input durations: two clips of 1 second each last 2 seconds (red at t = 0.5, blue at t = 1.5 when those are a 1-second red clip then a 1-second blue clip). Three clips last D1 + D2 + D3.

`padding` P between N clips adds P for each of the N − 1 boundaries: two clips last D1 + D2 + P; three clips last D1 + D2 + D3 + 2P. The same formula holds for `chain` and for `compose`. With positive P, the next clip is not yet visible at D1 + P/2; it is visible after D1 + P. With negative P on `compose`, the next clip appears at time D1 + P (before D1); before that instant the frame is still the first clip.

A `transition` clip of duration T is inserted between each consecutive pair (N − 1 copies). `duration` is the sum of the input durations plus T for each boundary. Mid-transition times (D1 + T/2, then D1 + T + D2 + T/2, …) show that transition clip’s picture, not the following content clip.

### Frame rate and soundtracks

`fps` is the maximum of the inputs’ frame rates among those that have one.

Soundtracks are concatenated in the same list order. When the inputs carry audio, result.`audio` is not `None`. Samples in the first video’s span match the first soundtrack; samples in the next span match the next soundtrack at that soundtrack’s local time.

```
`get_frame`(t)
```

- `t` — composition time in seconds.

Returns the picture of the clip that occupies that instant, shifted to that clip’s local time (and, for `compose`, drawn onto the max-size canvas).

### Refusals

If any input has no `duration`, the call does not succeed (including when only a later list member is missing duration). Exception class is not pinned. After `with_duration` assigns a duration to that clip, the same pair concatenates: `duration` is the sum, and each span shows that clip.

A `method` other than `chain` or `compose` does not succeed. Exception class is not pinned. The same clips still concatenate when `method` is `chain` or `compose`.

## `clipkit.vfx`

`vfx` is the visual-effect catalog of the package `clipkit`. Import it from the package root (`from `clipkit` import `vfx``). Each catalog entry is a first-class effect object: construct it, then apply it by passing a list of such objects to `with_effects` on a clip. Applying an effect returns a modified copy; the original clip is left unchanged.

These names are callable as ``vfx`.<name>` after that import:

- `CrossFadeIn`
- `CrossFadeOut`

Typical import:

```
from `clipkit` import `vfx`
```

A program that only needs those effects may import `vfx` alone, for example `from `clipkit` import `vfx``.

## `numpy`

`numpy` is the numeric-array library used for picture and sound frames. It is **not** a module of this product. Depend on it; do not reimplement it. Callers write `import `numpy`` (commonly bound as `np`).

Picture frames returned by the product are arrays from this library: they have `shape`, support `[row, col, channel]` indexing, and convert with `asarray`. Sound frames are arrays whose dtype kind is floating or complex.

These names are importable as ``numpy`.<name>` after `import `numpy``:

- `allclose`
- `array`
- `asarray`
- `clip`
- `pi`
- `sin`
- `uint8`
- `zeros`

## `numpy.abs`

Import `abs` from `numpy` (``numpy`.`abs`` after `import `numpy``). Element-wise absolute value. Not a product symbol.

### Signature

```
`abs`(x)
```

- `x` — a number or array.

Call form used: ``numpy`.`abs`(arr)` on a numeric sample array, and ``numpy`.`abs`(a - b)` on a pair of numeric pictures.

Returns an array of the same shape, each element the absolute value of the corresponding input. ``numpy`.`max`(`numpy`.`abs`(arr))` is the peak magnitude of a sound array. A picture difference ``abs`(a - b)` is non-negative at every pixel.

## `numpy.allclose`

Import `allclose` from `numpy` (``numpy`.`allclose`` after `import `numpy``). Element-wise numeric comparison with absolute and relative tolerance. Not a product symbol.

### Signature

```
`allclose`(a, b, rtol=1e-05, atol=1e-08)
```

- `a`, `b` — array-like values (pictures, sound samples, or a scalar broadcast against an array).
- `rtol` — relative tolerance. Callers pass ``rtol`=0` when only an absolute window should apply.
- `atol` — absolute tolerance. Callers pass ``atol`=0.5` when comparing RGB channels as floats against a requested color, and ``atol`=1e-5` when comparing a mask array to a scalar level.

Returns `True` when every element of `a` is within ``atol` + `rtol` * abs(b)` of the corresponding element of `b` (with broadcasting). `False` otherwise.

An RGB picture compared to ``asarray`(color, `dtype`=float).reshape(1, 1, 3)` with ``atol`=0.5` and ``rtol`=0` is true when every channel is within half a unit of the requested color. A mask array compared to a scalar level with ``atol`=1e-5` is true when every value matches that level within that window.

## `numpy.any`

Import `any` from `numpy` (``numpy`.`any`` after `import `numpy``). Whether any element of an array is true. Not a product symbol.

### Signature

```
`any`(a)
```

- `a` — an array of booleans, or a boolean expression over an array (for example `arr < 0` or `arr > 255`).

Returns `True` when at least one element is true, `False` when every element is false. Used to detect whether a mask has any ink pixels, whether any RGB channel is outside 0–255, and whether any mask value is outside 0–1.

## `numpy.arange`

Import `arange` from `numpy` (``numpy`.`arange`` after `import `numpy``). Evenly spaced values from 0 up to, but not including, a stop. Not a product symbol.

### Signature

```
`arange`(stop, dtype=float)
```

- `stop` — exclusive end. First positional. An integer `N` yields `N` values.
- `dtype` — element type. Callers pass ``dtype`=float`.

Call form used: ``numpy`.`arange`(n, `dtype`=float)`.

Returns a 1-D array of length `N`: `0, 1, …, N - 1` as floating-point. Dividing by a sample rate `R` or a frame rate `F` gives times in seconds: ``arange`(n, `dtype`=float) / R` is the grid `i / R` for `i = 0 … n-1`.

## `numpy.array`

Import `array` from `numpy` (``numpy`.`array`` after `import `numpy``). Construct a numeric array from a nested sequence. Not a product symbol.

### Signature

```
`array`(object, dtype=None)
```

- `object` — a sequence of sample values. A length-1 list is a mono sound frame; a length-2 list is a stereo sound frame.
- `dtype` — element type. Callers pass ``dtype`=float` for sound samples.

Call form used: ``numpy`.`array`([s0], `dtype`=float)` and ``numpy`.`array`([s0, s1], `dtype`=float)`.

Returns an array whose length is the number of samples and whose elements are floating-point. That array is a valid return from an `AudioClip` `frame_function`.

## `numpy.asarray`

Import `asarray` from `numpy` (``numpy`.`asarray`` after `import `numpy``). Convert a picture, a sound frame, or an RGB triple to a numeric array without copying when the input is already an array of the requested type. Not a product symbol.

### Signature

```
`asarray`(a, dtype=None)
```

- `a` — a frame returned by `get_frame`, or a sequence such as an RGB triple `(r, g, b)`.
- `dtype` — optional element type. Callers pass ``dtype`=float` when comparing colors as floats.

Returns an array. ``asarray`(frame).shape` is the frame’s shape: `(height, width, 3)` for RGB, `(height, width)` for a mask. ``asarray`(color, `dtype`=float).reshape(1, 1, 3)` is a broadcastable RGB color. The return supports `.astype(float)` for channel-wise float comparison.

## `numpy.ascontiguousarray`

Import `ascontiguousarray` from `numpy` (``numpy`.`ascontiguousarray`` after `import `numpy``). Convert a picture to a contiguous numeric array without changing its values. Not a product symbol.

### Signature

```
`ascontiguousarray`(a)
```

- `a` — an RGB picture of shape `(height, width, 3)` with integer channels in 0–255.

Call form used: ``numpy`.`ascontiguousarray`(picture)`.

Returns an array of the same shape and values, in contiguous layout. Callers then call `.copy()` on that array and return the copy from a `VideoClip` `frame_function`, so a still clip yields a distinct picture at every time. That copy is a valid RGB frame for a generated clip.

## `numpy.atleast_1d`

Import `atleast_1d` from `numpy` (``numpy`.`atleast_1d`` after `import `numpy``). Convert input to an array with at least one dimension. Not a product symbol.

### Signature

```
`atleast_1d`(a)
```

- `a` — a scalar or array, including a sound frame from `get_frame` after `asarray`.

Call form used: ``numpy`.`atleast_1d`(row).reshape(-1)` on one instant of stereo or mono samples.

Returns an array. A 0-D scalar becomes shape `(1,)`. A 1-D array is unchanged. `.reshape(-1)` then flattens to a 1-D sample row that `vstack` can stack. A stereo frame of length 2 stays length 2.

## `numpy.clip`

Import `clip` from `numpy` (`numpy`.`clip` after `import `numpy``). Limit values to a closed interval. Not a product symbol. This is the numeric helper, not a ClipKit clip object.

### Signature

```
`clip`(a, a_min, a_max)
```

- `a` — a number or array.
- a_min — lower bound (positional).
- a_max — upper bound (positional).

Call form used: ``numpy`.`clip`(t * 400.0, 0, 255)`.

Returns `a` projected into `[a_min, a_max]`. Values below a_min become a_min; values above a_max become a_max. Used inside a generated `VideoClip` `frame_function` to keep a time-dependent channel in 0–255.

## `numpy.column_stack`

Import `column_stack` from `numpy` (``numpy`.`column_stack`` after `import `numpy``). Stack 1-D sequences as columns of a 2-D array. Not a product symbol.

### Signature

```
`column_stack`(tup)
```

- `tup` — a sequence of 1-D arrays of equal length.

Call form used: ``numpy`.`column_stack`((left, right))` where `left` and `right` are length-N sample series.

Returns an array of shape `(N, 2)`. That array is a valid stereo input to `AudioArrayClip` (N samples, two channels).

## `numpy.count_nonzero`

Import `count_nonzero` from `numpy` (``numpy`.`count_nonzero`` after `import `numpy``). Number of nonzero (true) elements in an array. Not a product symbol.

### Signature

```
`count_nonzero`(a)
```

- `a` — a 2-D boolean array of shape height × width (a per-pixel match mask over a composed RGB picture).

Call form used: `int(`numpy`.`count_nonzero`(mask))`.

Returns the count of true / nonzero pixels. False and zero do not contribute. Callers wrap the result with `int(...)` to obtain a Python integer. Used to count how many pixels of a composed frame match a given RGB color within a detection window.

## `numpy.empty`

Import `empty` from `numpy` (``numpy`.`empty`` after `import `numpy``). Allocate an array of a given shape and dtype. Not a product symbol.

### Signature

```
`empty`(shape, dtype=float)
```

- `shape` — tuple of dimensions. Callers pass `(height, width, 3)` for an RGB picture.
- `dtype` — element type. Callers pass ``dtype`=`numpy`.`uint8`` for an RGB picture whose channels are integers in 0–255.

Call form used: ``numpy`.`empty`((height, width, 3), `dtype`=`numpy`.`uint8`)`.

Returns an array of that shape and dtype. Callers then write into it, for example `picture[:, :] = rgb`, so every pixel becomes that RGB triple. A valid return from a `VideoClip` `frame_function` after that assignment.

## `numpy.floor`

Import `floor` from `numpy` (``numpy`.`floor`` after `import `numpy``). Round down to the nearest integer toward −∞. Not a product symbol.

### Signature

```
`floor`(x)
```

- `x` — a number or array.

Call form used: `int(`numpy`.`floor`(duration * fps))` to count whole sample instants in a finite clip.

Returns the greatest integer (as a numeric value) that is ≤ `x`. For a positive duration and rate, that count is the number of whole frames of length `1 / fps` that fit in the duration.

## `numpy.full`

Import `full` from `numpy` (``numpy`.`full`` after `import `numpy``). Allocate an array filled with one constant value. Not a product symbol.

### Signature

```
`full`(shape, fill_value, dtype=None)
```

- `shape` — tuple of dimensions. Callers pass `(height, width)` for a greyscale mask.
- `fill_value` — scalar written into every element. Callers pass a floating-point level in 0–1.
- `dtype` — element type. Callers pass ``dtype`=float` for a mask whose values are floating-point.

Call form used: ``numpy`.`full`((height, width), float(level), `dtype`=float)`.

Returns an array of that shape, every element equal to the fill value. A valid return from a `VideoClip` `frame_function` when `is_mask` is true: the frame is height × width with values in 0–1.

## `numpy.isclose`

Import `isclose` from `numpy` (``numpy`.`isclose`` after `import `numpy``). Element-wise numeric comparison with absolute tolerance. Not a product symbol.

### Signature

```
`isclose`(a, b, atol=1e-6)
```

- `a` — a mask array of shape height × width with values in 0–1.
- `b` — a scalar level broadcast against `a`.
- `atol` — absolute tolerance. Callers pass ``atol`=1e-6`.

Call form used: ``numpy`.`isclose`(mask, 0.05, `atol`=1e-6)`.

Returns a boolean array of the same shape as `a`. An element is true when that mask value is within ``atol`` of `b`. ``any`(`isclose`(mask, 0.05, `atol`=1e-6))` is true when any mask value matches that fill level within that window, and false when none do.

## `numpy.linalg`

`linalg` is the linear-algebra submodule of `numpy`. It is **not** a module of this product. Depend on it; do not reimplement it. Callers write ``numpy`.`linalg`` after `import `numpy``.

These names are importable as ``numpy`.`linalg`.<name>`:

- `norm`

## `numpy.linalg.norm`

Import `norm` from `numpy`.`linalg` (``numpy`.`linalg`.`norm`` after `import `numpy``). Euclidean vector magnitude. Not a product symbol.

### Signature

```
`norm`(x, axis=None)
```

- `x` — an array. A height × width × 3 picture minus a broadcast RGB color is a per-pixel color difference. A length-3 mean-minus-target is a single color distance.
- `axis` — axis along which to take the magnitude. Callers pass ``axis`=2` on a height × width × 3 difference to collapse the channel axis.

Call form used: ``numpy`.`linalg`.`norm`(rgb - target, `axis`=2)` and ``numpy`.`linalg`.`norm`(mean - target)`.

With ``axis`=2`, the return is height × width: each value is the Euclidean distance of that pixel’s RGB to the target color. Without `axis`, the return is a single non-negative number (the magnitude of the whole vector). Comparing that per-pixel distance to a tolerance yields a boolean ink mask.

## `numpy.linspace`

Import `linspace` from `numpy` (``numpy`.`linspace`` after `import `numpy``). Evenly spaced numbers over a closed interval. Not a product symbol.

### Signature

```
`linspace`(start, stop, num)
```

- `start` — first value (included).
- `stop` — last value (included).
- `num` — number of samples `N` (positional).

Call form used: ``numpy`.`linspace`(-0.4, 0.5, n)` and ``numpy`.`linspace`(-0.3, 0.4, 12)`.

Returns a 1-D array of length `N`. `.reshape(N, 1)` is a valid mono input to `AudioArrayClip`. Two such arrays passed to `column_stack` form a stereo `N` × 2 array.

## `numpy.max`

Import `max` from `numpy` (``numpy`.`max`` after `import `numpy``). Maximum of an array. Not a product symbol. This is the numeric helper, not Python’s builtin `max`.

### Signature

```
`max`(a)
```

- `a` — a nonempty array.

Call form used: ``numpy`.`max`(`numpy`.`abs`(arr))` on a decoded sound array.

Returns the largest element. For ``abs`(arr)` of a sound clip, that value is the peak amplitude: silent audio is near 0; a written tone has a clearly positive peak.

## `numpy.maximum`

Import `maximum` from `numpy` (``numpy`.`maximum`` after `import `numpy``). Element-wise maximum of two arrays. Not a product symbol.

### Signature

```
`maximum`(x1, x2)
```

- `x1`, `x2` — arrays of equal shape. Callers pass two mask frames (height × width, values in 0–1).

Call form used: ``numpy`.`maximum`(a, b)`.

Returns an array of that shape. Each element is the larger of the two corresponding inputs. Two mask frames combined this way are the pixelwise-or of those masks (compare `MasksOr`).

## `numpy.mean`

Import `mean` from `numpy` (``numpy`.`mean`` after `import `numpy``). Arithmetic average of every element. Not a product symbol.

### Signature

```
`mean`(a)
```

- `a` — an array, or an indexed or boolean-selected view of an array. Callers pass a spatial slice of a PNG alpha plane (values in 0–255), a spatial slice of a mask (values in 0–1), or the elements of an alpha plane selected by `isclose` against a fill level.

Call form used: ``numpy`.`mean`(alpha[y0:y1, x0:x1])`, ``numpy`.`mean`(alpha[`isclose`(pattern, level)])`, and ``numpy`.`mean`(mask[:, :width // 2])`.

Returns a scalar: the average of every selected element. Casting that scalar to float is the region’s mean alpha or mean mask level. An opaque PNG-alpha block has a high mean; a transparent block has a low mean; two different in-between mask levels have distinguishable means.

## `numpy.median`

Import `median` from `numpy` (``numpy`.`median`` after `import `numpy``). Median along an axis. Not a product symbol.

### Signature

```
`median`(a, axis=None)
```

- `a` — an array. Callers pass an `N` × 3 array of RGB triples: a picture reshaped to one row per pixel, or the RGB pixels selected by a boolean spatial mask.
- `axis` — axis reduced. Callers pass ``axis`=0` (reduce over pixels, keep one value per channel).

Call form used: ``numpy`.`median`(rgb, `axis`=0)` and ``numpy`.`median`(rgba[:, :, :3][mask], `axis`=0)`.

Returns a length-3 1-D array: the per-channel median. Indexing `[0]`, `[1]`, `[2]` is red, green, blue. Rounding each element to int is that region’s dominant RGB. A solid-color picture’s median is that color; a boolean-selected block of a GIF RGBA frame has a median near that block’s picture color.

## `numpy.mgrid`

Import `mgrid` from `numpy` (``numpy`.`mgrid`` after `import `numpy``). Dense row and column index grids. Not a product symbol. Indexed, not called as a function.

### Signature

```
`mgrid`[0:height, 0:width]
```

- First slice — row range. `0:height` yields row indices `0 … height - 1`.
- Second slice — column range. `0:width` yields column indices `0 … width - 1`.

Call form used: ``numpy`.`mgrid`[0:height, 0:width]`.

Unpacks to two arrays of shape `(height, width)`:

- First array — row index at every pixel: value `r` at row `r`.
- Second array — column index at every pixel: value `c` at column `c`.

Used inside a `VideoClip` `frame_function` to paint a spatially varying RGB picture: channel values derived from those row and column indices so different pixels have different colors, and the pattern can still change with time.

## `numpy.minimum`

Import `minimum` from `numpy` (``numpy`.`minimum`` after `import `numpy``). Element-wise minimum of two arrays. Not a product symbol.

### Signature

```
`minimum`(x1, x2)
```

- `x1`, `x2` — arrays of equal shape. Callers pass two mask frames (height × width, values in 0–1).

Call form used: ``numpy`.`minimum`(a, b)`.

Returns an array of that shape. Each element is the smaller of the two corresponding inputs. Two mask frames combined this way are the pixelwise-and of those masks (compare `MasksAnd`).

## `numpy.ndarray`

`ndarray` is the numeric-array type of `numpy` (``numpy`.`ndarray`` after `import `numpy``). Picture and sound frames returned by the product convert to this type with `asarray`. Not a product symbol. Depend on it; do not reimplement it.

A converted RGB picture has `.ndim` 3 and `.shape` `(height, width, 3)`. A mask picture has `.ndim` 2 and `.shape` `(height, width)`. A stereo sound array has `.ndim` 2 and `.shape` `(N, 2)`. Indexing `frame[:, :, :3]` is the RGB plane; `frame[:, :, 3]` is an alpha plane when a fourth channel is present.

Observable operations used on these arrays:

- `.shape` — dimension tuple.
- `.ndim` — number of dimensions.
- `.size` — total number of elements.
- `.dtype` — element type. `.dtype.kind` is a character: numeric kinds include `b`, `i`, `u`, `f`, `c`; sound samples use a floating kind (`f` or `c`).
- `.astype(float)` — channel or sample values as floating-point. `.astype(`numpy`.`uint8`)` after rounding yields 0–255 integer channels.
- `.reshape(…)` — same data, new shape. `.reshape(1, 1, 3)` broadcasts an RGB triple; `.reshape(-1, 3)` flattens pixels; `.reshape(N, 1)` is mono audio; `.reshape(-1)` flattens samples.
- `.mean()` / `.mean(axis=0)` — average of all values, or along an axis.
- `.max()` / `.min()` — extreme values (used on index arrays from `nonzero`).
- Boolean indexing: `mask[boolean_array]` selects elements where the boolean array is true.

## `numpy.nonzero`

Import `nonzero` from `numpy` (``numpy`.`nonzero`` after `import `numpy``). Indices of true (nonzero) elements. Not a product symbol.

### Signature

```
`nonzero`(a)
```

- `a` — a 2-D boolean array (for example an ink mask of shape height × width).

Call form used: `rows, cols = `numpy`.`nonzero`(mask)`.

Returns a pair of 1-D integer index arrays `(rows, cols)`. `rows` are the row (y) indices and `cols` are the column (x) indices of every true pixel. When no element is true, `cols.size` is 0. Otherwise `cols.mean()` and `rows.mean()` are the center of mass in x and y, and `rows.max() - rows.min() + 1` is the ink bounding-box height. `.tolist()` on each array yields a Python list of those indices.

## `numpy.ones`

Import `ones` from `numpy` (``numpy`.`ones`` after `import `numpy``). Allocate an array filled with ones. Not a product symbol.

### Signature

```
`ones`(shape, dtype=float)
```

- `shape` — dimensions of the result, typically the return of `shape` on a time value.
- `dtype` — element type. Callers pass ``dtype`=float` for sound samples.

Call form used: ``numpy`.`ones`(`shape`(`asarray`(t)))` and ``numpy`.`ones`(`shape`(tt), `dtype`=float)`.

Returns an array of that shape, every element `1`. Multiplying by an amplitude yields a constant-level sound frame: `amp * `ones`(`shape`(`asarray`(t)))` is a valid mono return from an `AudioClip` `frame_function`. Pairing two such series with column-stack is a valid stereo return.

## `numpy.pi`

Import `pi` from `numpy` (``numpy`.`pi`` after `import `numpy``). The constant π, approximately `3.141592653589793`. Not a product symbol.

Used in generated audio: ``sin`(2.0 * `numpy`.`pi` * freq * t)` is a tone of `freq` hertz at time `t` seconds.

## `numpy.repeat`

Import `repeat` from `numpy` (``numpy`.`repeat`` after `import `numpy``). Repeat each element along one axis. Not a product symbol.

### Signature

```
`repeat`(a, repeats, axis=None)
```

- `a` — an array. Callers pass a 2-D height × width mask pattern.
- `repeats` — integer count of copies of each element along `axis`. Callers pass `2`.
- `axis` — axis along which to repeat. Callers pass ``axis`=0` (rows, height) and ``axis`=1` (columns, width).

Call form used: ``numpy`.`repeat`(`numpy`.`repeat`(pattern, 2, `axis`=0), 2, `axis`=1)`.

Repeating by 2 along axis 0 duplicates every row and doubles height. Repeating that result by 2 along axis 1 duplicates every column and doubles width. A pattern of shape `(h, w)` becomes `(2 * h, 2 * w)`, each source value expanded into a 2×2 block of the same value.

## `numpy.round`

Import `round` from `numpy` (``numpy`.`round`` after `import `numpy``). Round each element to the nearest integer (result still floating-point). Not a product symbol.

### Signature

```
`round`(a)
```

- `a` — a number or array.

Call form used: ``numpy`.`round`(arr[:, :, :3]).astype(`numpy`.`uint8`)` when writing RGB channels to a picture file.

Returns an array of the same shape. An RGB picture compared to ``round`(picture)` with a tiny absolute tolerance is true when every channel is integer-valued.

## `numpy.shape`

Import `shape` from `numpy` (`numpy`.`shape` after `import `numpy``). Dimensions of an array. Not a product symbol. This is the function `numpy`.`shape`(a), not a ClipKit clip.

### Signature

```
`shape`(a)
```

- `a` — an array, or a value converted with `asarray`. Callers pass a time value `t` after `asarray`(t), or a 1-D time vector.

Call form used: `numpy`.`shape`(`asarray`(t)) and `numpy`.`shape`(tt).

Returns a tuple of dimensions. For a scalar time that tuple is empty; for a length-N time vector it is (N,). Passing that tuple to `ones` allocates a sample series whose length matches the time argument of an `AudioClip` `frame_function`.

## `numpy.sin`

Import `sin` from `numpy` (``numpy`.`sin`` after `import `numpy``). Sine of an angle in radians. Not a product symbol.

### Signature

```
`sin`(x)
```

- `x` — a number or array, in radians.

Returns the sine. ``sin`(2.0 * `numpy`.`pi` * freq * t)` at `t = 0` is 0; at `t = 0.25 / freq` its magnitude is 1. Used as the body of an `AudioClip` `frame_function`.

## `numpy.stack`

Import `stack` from `numpy` (``numpy`.`stack`` after `import `numpy``). Join a sequence of equal-shape arrays along a new axis. Not a product symbol.

### Signature

```
`stack`(arrays, axis=0)
```

- `arrays` — a sequence of arrays of equal shape. Callers pass three copies of a 2-D greyscale picture: `[arr, arr, arr]` or `[grey, grey, grey]`.
- `axis` — position of the new axis. Callers pass ``axis`=-1` (last axis).

Call form used: ``numpy`.`stack`([arr, arr, arr], `axis`=-1)`.

Returns an array with one added dimension. Three height × width arrays stacked on axis `-1` yield shape `(height, width, 3)`: an RGB picture whose three channels are identical copies of that greyscale plane.

## `numpy.std`

Import `std` from `numpy` (``numpy`.`std`` after `import `numpy``). Standard deviation of every element. Not a product symbol.

### Signature

```
`std`(a)
```

- `a` — an array. Callers pass a greyscale mask, or an RGB picture converted to floating-point.

Call form used: ``numpy`.`std`(mask)` and ``numpy`.`std`(picture.astype(float))`.

Returns a scalar: how much the elements vary. A mask that is high in a spatial block and low elsewhere has a standard deviation greater than a tiny window (it is not constant). A picture whose pixels are two different colors has a larger standard deviation than a uniform field. An array filled with one constant has a standard deviation of 0.

## `numpy.uint8`

Import `uint8` from `numpy` (``numpy`.`uint8`` after `import `numpy``). Unsigned 8-bit integer dtype (integers in 0–255). Not a product symbol.

Passed as ``dtype`=`numpy`.`uint8`` to `zeros` when allocating an RGB picture. Product RGB frames use integer channels in that 0–255 range.

## `numpy.vstack`

Import `vstack` from `numpy` (``numpy`.`vstack`` after `import `numpy``). Stack arrays row-wise. Not a product symbol.

### Signature

```
`vstack`(tup)
```

- `tup` — a sequence of arrays of equal trailing width. Callers pass a list of 1-D sample rows of the same length.

Call form used: ``numpy`.`vstack`(rows)` where each row is one instant of stereo samples (length 2) from `get_frame`.

Returns a 2-D array. `N` rows of length 2 yield shape `(N, 2)`. That stacked array is the clip’s sound over those sample times: column 0 is the first channel, column 1 the second.

## `numpy.zeros`

Import `zeros` from `numpy` (``numpy`.`zeros`` after `import `numpy``). Allocate an array filled with zeros. Not a product symbol.

### Signature

```
`zeros`(shape, dtype=float)
```

- `shape` — tuple of dimensions. Callers pass `(height, width, 3)` for an RGB picture.
- `dtype` — element type. Callers pass ``dtype`=`numpy`.`uint8`` for an RGB picture whose channels are integers in 0–255.

Call form used: ``numpy`.`zeros`((height, width, 3), `dtype`=`numpy`.`uint8`)`.

Returns an array of that shape, every element 0. Assigning `picture[:, :, 0] = …` fills the red channel. A valid return from a `VideoClip` `frame_function` after the caller writes the three channels.

