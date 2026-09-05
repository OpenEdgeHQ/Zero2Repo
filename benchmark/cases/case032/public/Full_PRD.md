# ClipKit — Full Product Requirements Document

## Product overview

**ClipKit** is a Python library for video editing: cuts, concatenations, title insertions, video compositing (non-linear editing), video processing, and creation of custom effects. It reads and writes the common audio and video formats, including GIF. It runs on Windows, macOS, and Linux with Python 3.9 or newer.

The product’s advertised happy path is: open a video file, keep only a timed slice, scale the soundtrack volume, generate a title as a still picture, overlay that title on the video, and write the result to a new file.

ClipKit imports pictures and sounds, exposes every frame as a numeric array so pixels and samples are accessible, lets the caller mix clips in time and space, and encodes the finished clip back to MP4, WebM, GIF, and similar containers. That flexibility is slower than calling FFmpeg directly, because frames pass through Python. The product does not stream live cameras or remote live output, and it is not specialized for multi-frame analysis such as stabilization.

This document specifies **user- and integrator-observable behavior only**. Exact published symbol names, import paths, and call signatures belong in the Interface Contract, not here. Every feature point corresponds to behavior that exists in the finished product. Feature points are ordered so foundational capabilities come first; a later feature point may refine an earlier one only when it says so explicitly.

## Terminology

| Term | Meaning in this PRD |
| --- | --- |
| **Clip** | The central unit of ClipKit. A clip is a timed media object: at a given time it yields a frame. Video clips yield pictures; audio clips yield sound. Some clips are infinite (no duration) until the caller assigns one. |
| **Video clip** | Any visual clip. A standard video frame is a numeric array of height × width × 3 with integer channel values in 0–255 (red, green, blue). |
| **Audio clip** | Any sound clip. A sound frame is a numeric array of length 1 (mono) or 2 (stereo) whose samples are floating-point, conventionally in −1 to 1. |
| **Mask** | A special video clip used for visibility and transparency. A mask frame is a greyscale numeric array of height × width with values in 0–1: 1 is fully visible, 0 is fully transparent. |
| **Soundtrack** | The audio clip carried by a video clip, if any. |
| **Duration** | Length of the clip in seconds. Infinite clips have no duration. |
| **Start / end** | When a clip is placed in a composition, the composition times at which it begins and stops playing. They do not change which frame is the clip’s own first frame. Default start is 0. |
| **Frame rate** | Frames per second used when iterating or encoding. File-backed clips inherit one from the file; still pictures and generated clips have none until the caller assigns one. |
| **Time value** | A moment or duration accepted wherever ClipKit takes time. See “Time encodings” below. |
| **Composition** | A video clip that layers other video clips in space and time (non-linear editing). |
| **Effect** | A reusable transformation applied to a clip. Applying an effect returns a modified copy; the original clip is left unchanged. |
| **Media encoder / decoder** | The external FFmpeg binary ClipKit uses to read and write video and audio files. The default is the bundled FFmpeg that ships with the image-IO plugin; the caller may point at another invocable binary. This is the **mandatory substrate** for file-backed read and write. |
| **Core capability** | A user-observable capability that reflects the product’s design goal; acceptance must prove the real behavior, not a stub. |
| **Discrimination** | An assertion’s ability to distinguish a faithful implementation from a hollow, skipped, or proxy one. |

### Time encodings

Wherever this document says a **time value**, ClipKit accepts all of the following and converts them to a number of seconds:

- A number of seconds.
- A pair (minutes, seconds) or a triple (hours, minutes, seconds).
- A colon-separated clock string. Hours:minutes:seconds with a fractional part is accepted; minutes:seconds and seconds-only are accepted. A comma is accepted as the decimal separator as well as a period.

Negative time values, when this document says they are allowed, count backward from the clip’s duration.

### Position encodings

Wherever this document says a **position** in a composition, the origin is the **top-left** of the picture (vertical coordinate 0 is the top). A position names the top-left corner of the placed clip and may be:

- A pair of pixel coordinates.
- A pair whose members are the keywords center, left, right for the horizontal member and center, top, bottom for the vertical member.
- A single keyword center, left, right, top, or bottom (the missing axis is centered).
- A pair of fractions of the composition size, when relative placement is requested.
- A function of time that returns any of the above, so the clip can move.

## Public surface inventory

ClipKit is imported and used from Python. The public surface, grouped the way later feature points verify it, is:

- Clips as timed objects: ask for a frame at a time value; copy-on-modify; start, end, duration, and frame rate; iterate frames of a finite clip; carry or strip a soundtrack.
- Constructing video clips from a still image file or array, a folder or list of same-size images, a solid color, rendered text (OpenType font), a caller-supplied function of time that returns a picture, or a video clip’s frame at a given time.
- Constructing audio clips from a sound file, a numeric sound array, or a caller-supplied function of time that returns samples.
- Loading a video file (most containers FFmpeg can decode, including GIF) as a video clip, optionally with its embedded soundtrack.
- Cutting a time slice, skipping an interior interval, assigning start/end/duration, scaling playback speed, and scaling soundtrack volume.
- Resizing, cropping, rotating, and placing a clip in a composition.
- Overlay composition, concatenation (play one after another), and juxtaposition (a grid of clips). Matching audio composition: overlay mix and concatenation.
- Masks, opacity, and converting between a color clip and a mask.
- The built-in visual-effect catalog and the built-in audio-effect catalog listed under FP-08, plus caller-defined effects and per-frame / per-time filters.
- Writing a video file, an audio file, an animated GIF, an image sequence, or a single still frame.

Feature points below group these entries by independently verifiable capability. They do not invent additional product surfaces.

The following exist in the product but are **not** core capabilities of this document: on-screen preview (requires FFplay), embedding a clip in a Jupyter notebook, scientific world-step clips, subtitle and rolling-credits helpers, drawing primitives, scene-cut detectors, bitmap-letter test clips, and direct FFmpeg copy/extract helpers that bypass clip editing. They must not be treated as substitutes for the feature points below.

## Non-functional constraints

- **Form factor:** A pure-Python library. Authors edit media with it; ClipKit is not a single end-user binary and has no command-line editor of its own.
- **Language:** Python 3.9 or newer.
- **Platforms:** Windows, macOS, and Linux. This case’s acceptance targets Linux with a supported interpreter.
- **Hardware:** CPU-only. No compiled native extensions of ClipKit itself, and no GPU or accelerator requirement. Frames are numeric arrays; file encode/decode goes through the media encoder/decoder.
- **Mandatory substrate:** A working FFmpeg binary (the bundled binary by default, or another invocable binary the environment names). Constructing a short solid-color clip and encoding it to a video file through that encoder is the hardware profile’s core proof. Cheaper proxies that invent a container without invoking the encoder do **not** satisfy file write. Loading a video or audio file likewise requires the decoder; fabricating frames without reading the named file does not satisfy file load.
- **Numeric stack:** Picture and sound frames are numeric arrays as defined under Terminology.
- **Encoder configuration:** The caller can name which FFmpeg binary the library uses. If the caller names none, the library uses the bundled FFmpeg. The caller may instead name a binary that is already on the process path, or a filesystem path to an invocable binary. Preview uses a second binary (FFplay) the same way; preview is not a core capability here. Those choices may be set in the process environment before the library is used, or in a dotenv file in the working directory that the library reads.

## Capability discrimination (global)

Every feature point below is a **core capability**. File-backed load (FP-03) and file-backed encode (FP-09) are **mandatory-substrate capabilities**: they require the real FFmpeg binary.

For every feature point:

- **Present:** Real library behavior matches the described outcomes for the named inputs (clips, files, time values, compositions).
- **Absent / hollow:** Objects that cannot yield frames; “edits” that mutate the original instead of returning a copy; writes that create empty or non-media files; concatenations that ignore time; titles that are not actually rendered text; an encoder stub that does not invoke FFmpeg.

Cheaper proxies (hard-coded MP4 bytes, skipping decode, always-black frames, or substituting a different editor) do **not** satisfy core capabilities. There is no approved degradation scenario that replaces FFmpeg for file-backed read or write.

**Negative control (media encoder / decoder):** When the FFmpeg binary is deliberately disabled or unreachable in an isolated subprocess (removed from the path, and the bundled binary made unusable), loading a video file and writing a video file must **fail** with a hard error — not pass silently or skip. When the binary is present and invocable, the same load and the same write succeed and produce a real media file. Output-equality of a hand-made file is not proof that the encoder ran.

**Negative control (Python / package substrate):** When the ClipKit package is deliberately not importable in an isolated subprocess, a program that depends on it must fail to start with a hard error.

## Non-goals

- Live streaming from a webcam or rendering live to a remote machine.
- Being a frame-by-frame computer-vision toolkit (face detection and similar).
- Being a faster drop-in replacement for calling FFmpeg only to remux or transcode a file.
- Guaranteeing real-time preview on every host (preview may drop below real time on a slow machine; preview is not a core capability here).
- Supporting Python 2, or the removed first-generation all-in-one editor convenience import.
- ImageMagick, PyGame, or the other optional first-generation backends. The current product uses a still-image library for complex image work.

---

## Feature points

### FP-01: Clip as a timed media unit

**Public entry:** ClipKit’s clip objects, as obtained from any constructor in FP-02 or FP-03 or from a later editing operation. Asking a clip for the frame at a time value; assigning duration and frame rate; copying; attaching or stripping a soundtrack. This feature is the substrate every later feature point uses.

**Normal behavior:**

- A video clip, given a time value inside its playing interval, returns a picture: height × width × 3 with integer channels in 0–255, unless it is a mask (FP-07), in which case it returns height × width with values in 0–1. Asking twice at the same time returns pictures that match for a deterministic clip.
- An audio clip, given a time value, returns mono (one sample) or stereo (two samples) floating-point values.
- A newly constructed clip starts at composition time 0. End and duration are either inherited from a finite source or absent (infinite) until the caller assigns them. Assigning a duration D to a clip that starts at S sets end to S + D. Assigning an end E to a clip that starts at S sets duration to E − S. Assigning a new start can keep duration and move the end, or keep the end and shorten duration, depending on which of those two adjustments the caller requests.
- Assigning a frame rate without asking to conserve every frame does not change duration; the new rate is the default used by iteration and by encode (FP-09). Assigning a frame rate while asking to conserve every frame 1:1 changes duration so that the same frames play at the new rate (halving the rate doubles duration).
- Modifying a clip never mutates that clip. The operation returns a distinct clip. Asking the original for a frame at time t still yields the pre-modification picture or sound. The returned clip yields the modified picture or sound at the same t.
- Time values on these operations accept all encodings listed under Terminology, including a clock string and a (hours, minutes, seconds) triple. A five-second duration written as the clock string for five seconds, as the triple (0, 0, 5), and as the number 5, all produce duration 5.
- A finite clip with a frame rate can be iterated: the number of frames is duration × frame rate, using whole frames (a 1-second clip at 60 frames per second yields 60 frames). Each yielded picture is the frame at the corresponding time.
- Two clips constructed the same way from the same still pictures, same duration, and same frame rate compare as equal. Changing the pictures or the duration makes them unequal.
- A video clip may carry a soundtrack. Assigning an audio clip as that soundtrack, or stripping the soundtrack, returns a copy: the original still has or lacks the soundtrack as before. When a soundtrack is present, asking that soundtrack for sound at time t yields the assigned audio clip’s samples at t. Encode (FP-09) includes that soundtrack when audio is left on, and omits it when the soundtrack has been stripped.

**Boundary / error behavior:**

- Asking a clip that has no duration to encode to a video file, GIF, or image sequence (FP-09), or to iterate all frames, does not succeed. The failure is distinguishable from a successful write or iteration; it identifies that duration is missing. The same clip becomes writable after a duration is assigned.
- Asking to assign a missing duration while also asking to keep the existing end and move the start does not succeed.
- A time slice whose start is at or after the clip’s duration does not succeed (FP-04).

**Verifiable oracle:**

- Success: a solid-color clip of known size, after a duration and frame rate are assigned, returns a picture of that size whose pixels match the requested color at time 0; assigning duration 5 via a clock string, a (hours, minutes, seconds) triple, and the number 5 all yield duration 5 and end = start + 5; a modification leaves the original’s frame at time 0 unchanged and returns a different clip whose frame at time 0 reflects the modification; iterating a 1-second clip at 60 frames per second yields 60 pictures; assigning a generated tone as soundtrack and then encoding with audio left on produces a file that contains that tone, while stripping the soundtrack first produces a file with no soundtrack.
- Failure / absence: frames are not numeric arrays of the documented shapes; modifications overwrite the original; clock-string times are rejected; a clip with no duration still encodes as if it were finite; iteration count does not match duration × frame rate; assigning a soundtrack mutates the original clip.

---

### FP-02: Construct clips from pictures, color, text, sequences, and generated frames

**Public entry:** ClipKit’s constructors for a still-image clip, a solid-color clip, a text clip, an image-sequence clip, a generated video clip (caller function of time → picture), a generated audio clip (caller function of time → samples), and an audio clip from a numeric sound array. A still-image clip may also be taken from a video clip’s frame at a given time. These entries do not require FFmpeg. File-backed video and audio load is FP-03.

**Normal behavior:**

- A still-image clip, given an image file (PNG, JPEG, TIFF, and similar) or a numeric picture array, displays that same picture at every time. Size is the picture’s width and height. Duration is absent unless the caller supplies one (the still lasts for the whole composition when used as a layer, FP-06). If the image has an alpha layer and transparency is left on (the default), that alpha becomes the clip’s mask (FP-07). Passing transparency off ignores the alpha layer. Taking a still from a video clip at time t yields a still-image clip whose picture matches the video clip’s frame at t.
- A solid-color clip, given a pixel size (width, height) and an RGB triple, displays that color at every pixel. Default color when none is given is black (0, 0, 0). A four-channel color is accepted: the fourth channel is treated as alpha and becomes a mask, and the first three channels are the picture. A mask-mode color clip uses a single scalar in 0–1 instead of RGB, and its frames are greyscale masks.
- A text clip renders a Unicode string (or the contents of a text file) into a still picture using an OpenType font file the caller names by path, or the built-in default font when no font is named. Color may be an RGB or RGBA triple, a color name, or hexadecimal. Background color may be omitted (transparent background) or set the same way. Two layout methods exist, and only those two:
  - **label** (default): the picture is sized to the text. If a font size is given, width and height are computed; if a width is given, font size may be computed.
  - **caption**: the picture has a caller-supplied width (mandatory). Text wraps onto multiple lines. If height and font size are both omitted, the operation does not succeed; if font size is omitted but width and height are given, font size is chosen to fit; if height is omitted but font size is given, height is computed.
  Text alignment inside the block is left, center, or right (default left). The block’s placement in the picture is horizontal left, center, or right (default center) and vertical top, center, or bottom (default center). Optional stroke color and stroke width draw an outline. Optional margin is a pair (horizontal, vertical) or a quadruple (left, top, right, bottom). The rendered picture’s pixels in the glyph region match the requested text color, not a blank canvas; a clip rendered from “Hello” is distinguishable from one rendered from “World” at the same size and color.
- An image-sequence clip plays a list of image files in the given order, or all images in a folder in alphanumerical order, or a list of same-size numeric pictures. The caller supplies either a frame rate or a per-image duration list. Sequence duration is the sum of those per-image durations. PNG alpha becomes a mask when that option is left on.
- A generated video clip takes a function of time that returns a height × width × 3 picture. Duration must be supplied at construction for the clip to be finite. Frame rate is still required later for encode (FP-09). At time t the clip’s frame is exactly that function’s picture at t (a pulsing circle whose radius depends on t has a different picture at t = 0 and t = 0.5).
- A generated audio clip takes a function of time that returns mono or stereo samples and a duration. Channel count is inferred from the value at time 0. An audio clip from a numeric array of shape N × 1 (mono) or N × 2 (stereo) plus a sample rate has duration N / sample rate and plays those samples in order.

**Boundary / error behavior:**

- A text clip with neither a string nor a text file does not succeed. A layout method other than label or caption does not succeed. Caption without a width does not succeed. Caption with neither height nor font size does not succeed. A named font path that cannot be opened as an OpenType font does not succeed. A margin that is not a pair or a quadruple does not succeed.
- A solid-color clip in mask mode does not accept a non-scalar color. A non-mask color clip does not accept a scalar color or a color given as a string.
- An image-sequence clip with neither a frame rate nor a duration list does not succeed. If any image in the sequence has a different size from the first, the operation does not succeed.
- A still-image clip given a path that is not an image file does not succeed.

**Verifiable oracle:**

- Success: a 16×16 color clip of (255, 0, 0) yields a 16×16 picture whose pixels are red; a text clip of a known string, font, size, and white color yields a picture in which the glyph region is white and is distinguishable from a clip of a different string; an image-sequence of two different pictures at 1 frame per second has duration 2 and shows the first picture at t = 0 and the second at t = 1; a generated clip whose function returns a picture that depends on t returns different pictures at two different times; an array-backed audio clip of N stereo samples at sample rate R has duration N / R and round-trips those samples when converted back to an array (within ordinary numeric tolerance); a still taken from a color clip at time 0 matches that color clip’s frame at time 0.
- Failure / absence: color clips ignore the requested color; text clips produce a blank or unrelated picture; sequences mix sizes without failing; generated clips ignore t; array audio duration is not N / R.

---

### FP-03: Load video and audio files

**Public entry:** ClipKit’s file-backed video clip and file-backed audio clip. Both use the FFmpeg media decoder (mandatory substrate). Releasing the file by closing the clip, including using the clip as a context manager, is part of this entry.

**Normal behavior:**

- Opening a video file that FFmpeg can decode (including MP4, WebM, MOV, AVI, MPEG, OGV, and GIF) produces a video clip whose duration, frame rate, and size match the file’s video stream. Asking for a frame at time t returns the picture at that time in the file, not a solid placeholder. If the file has an audio stream and audio is left on (the default), the clip carries a soundtrack whose duration matches that audio. If the caller turns audio off, the clip has no soundtrack.
- Opening an audio file that FFmpeg can decode (including WAV, MP3, OGG, FLAC, and audio inside a video container) produces an audio clip whose duration matches the file. The decoder yields stereo samples at 44100 per second unless the caller names another rate; converting that clip to a sound array at that decode rate reproduces the stored samples within ordinary encode/decode tolerance.
- After a copy-on-modify that does not change geometry or timing, the loaded clip’s duration, frame rate, and size remain those of the file and remain the defaults for encode (FP-09).
- The caller may ask the decoder to resize frames while reading, by naming a target width and/or height. If only one dimension is named, aspect ratio is kept. Frames obtained from the loaded clip have that size — not a later resize of a full-resolution picture.
- After a clip that was actually constructed from a file is closed (explicitly, or by leaving a context-manager block), further frame reads on that clip do not succeed. Derived clips that still need the file also fail once the source is closed. Closing a composition does not close the clips it was built from; those still need their own close.

**Boundary / error behavior:**

- A path that does not exist does not succeed. A path that is a directory does not succeed. A file that is not readable media does not succeed. The failure identifies the offending path; no clip that yields frames is returned.
- A corrupted video whose duration or dimensions cannot be parsed does not succeed.
- After close, a frame request on that instance does not succeed.

**Verifiable oracle:**

- Success: writing a 5-second, 10 fps, known-size clip that is red in the first half and blue in the second to MP4 (FP-09) and loading that file yields duration 5 (within ordinary muxer tolerance), frame rate 10, and the same size; a frame in the first half is red and a frame in the second half is blue (within ordinary lossy-codec tolerance); loading a stereo WAV written at 44100 from a known array reproduces those samples within tolerance; reading with a named target height of 128 yields frames 128 pixels tall.
- Failure / absence: load ignores the file and returns a generated placeholder; duration or size do not match the file; audio in a file with a soundtrack is missing when audio was left on; a missing path is treated as success; load succeeds when the FFmpeg binary has been deliberately disabled in an isolated subprocess (negative control).

This feature is a **mandatory-substrate capability**. Negative control: with FFmpeg unreachable, opening a real video file must fail.

---

### FP-04: Cut, skip, and schedule on the timeline

**Public entry:** Taking a time slice of a clip; skipping an interior interval; assigning start, end, and duration for use in a composition (FP-01 states the arithmetic; this feature states the editorial outcomes). Speed change is the multiply-speed effect in FP-08; volume change is the multiply-volume effect in FP-08.

**Normal behavior:**

- A time slice from start time A to end time B (both time values) is a new clip whose duration is B − A. The picture (and soundtrack, and mask, if any) at time 0 of the slice is the source’s picture at time A; at time t it is the source at A + t. Omitting B uses the source duration as the end. The original clip is unchanged (FP-01).
- Negative A or B count from the end: a slice from −20 to −10 on a clip of duration D is the interval (D − 20, D − 10). A slice from 0 to −2 drops the last two seconds.
- Skipping the open interval from C to D produces a clip that plays the source up to C and then continues from D, with duration shortened by D − C when the source had a duration. Soundtrack and mask are skipped the same way. The picture just after C matches the source just after D, not the skipped interval.
- Start and end on a clip control when that clip plays **inside a composition** (FP-06). Setting start to 10 seconds does not drop the clip’s first frames: the first frame still appears, but only when the composition reaches 10 seconds. Until then, the composition shows whatever is under this clip. End stops it at that composition time.
- A clip is playing at composition time t when t is at least its start and strictly less than its end (or any t at or after start when end is absent).

**Boundary / error behavior:**

- A slice whose start is at or after the source duration does not succeed.
- A slice whose end is after the source duration (beyond a tiny numeric tolerance) does not succeed.
- A negative slice bound on a clip that has no duration does not succeed.

**Verifiable oracle:**

- Success: a three-color clip that is red for 1 s, then green for 1 s, then blue for 1 s, sliced from 1 to 2, is green at t = 0.5 of the slice and has duration 1; slicing the same clip from −1 to the end is blue; skipping 1 to 2 yields a 2-second clip that is red then blue with no green; a layer whose start is 5 in a 10-second composition is absent at t = 4 and present at t = 5.
- Failure / absence: a slice still plays from the source’s time 0; negative times are rejected or treated as zero; skip leaves the skipped interval in place; start time crops the source instead of delaying it in the composition.

---

### FP-05: Resize, crop, rotate, and place

**Public entry:** Resizing a video clip, cropping it to a rectangle, rotating it, and setting its position for composition (FP-06). These operations return copies (FP-01). By default, an attached mask is resized, cropped, and rotated with the picture so mask geometry stays aligned with the picture. For resize, the caller can request that the mask be left unchanged.

**Normal behavior:**

- Resize accepts a target size as a (width, height) pair, or a single new width, or a single new height, or a scale factor. When only width or only height is given, the other dimension follows the original aspect ratio. Frames of the result have the new size. A clip that was 1024×800, resized to width 480, is 480 pixels wide and 375 pixels tall.
- Crop keeps a rectangular subregion. The region may be given as opposite corners, as a top-left corner plus width and height, or as a center plus width and height. Coordinates are in pixels. The result’s size is that rectangle. Pixels outside the rectangle are absent.
- Rotate turns the picture anticlockwise by the given angle. Angle units are degrees by default and may be radians when requested. Requesting expand grows the canvas so a non-orthogonal turn is not clipped; without expand the canvas stays the source size and a non-orthogonal turn clips corners. A 180-degree turn with expand, on a clip whose corners differ, places the source top-left color at the result bottom-right.
- Position (Terminology) is used when the clip is a layer in a composition. Default position is (0, 0) — top-left of the composition. A clip placed at center is centered on both axes. A clip placed at (center, top) is horizontally centered and flush with the top. Relative (0.4, 0.7) puts the top-left at 40% of the composition width and 70% of the composition height. A function of time moves the clip: the position at t is that function’s value at t.
- A layer index, when set, is used by composition (FP-06): a greater index is drawn on top of a lesser one.

**Boundary / error behavior:**

- Crop coordinates that invert the rectangle (right edge left of left edge, or equivalent) do not produce a clip whose width and height are both positive.
- A position keyword other than the documented set is not a valid position when the clip is placed in a composition.

**Verifiable oracle:**

- Success: resizing a known-size clip to a given width (keeping aspect) yields frames of that width and the matching height; cropping a 10×10 color clip to the left 5×10 half yields 5×10 frames of the same color; a 180-degree turn with expand requested, on a clip whose top-left and bottom-right differ, places the source top-left color at the bottom-right; a clip placed at the bottom-right of a larger composition is visible in the bottom-right pixels of the composition and not in the top-left; a clip whose position is a function of time occupies different coordinates at two different times.
- Failure / absence: resize ignores the requested size; crop returns the full frame; position is ignored and every layer sits at the origin; a 180-degree turn with expand requested on that asymmetric clip leaves the picture unrotated.

---

### FP-06: Overlay, concatenate, and juxtapose

**Public entry:** A composite video clip (layers played together); concatenating video clips into one sequence; laying video clips out in a grid. Matching audio: a composite audio clip (overlapping mix) and concatenating audio clips. When video clips are composed, their soundtracks and masks are mixed automatically unless the caller has already stripped them.

**Normal behavior:**

- **Overlay.** A composite built from a list of video clips plays them together. Later clips in the list are drawn on top of earlier clips when they share the same layer index; a higher layer index is drawn on top of a lower one regardless of list order. Default composition size is the size of the first clip. The caller may name a larger size so smaller clips float on a canvas. Default background fill is black (0, 0, 0). If background fill is omitted as “no color”, unfilled regions are transparent (the composite has a mask). If the first clip is designated as the background, it is the canvas and must match the final size; if that background has no mask, the composite has no mask.
- Each layer plays only while it is playing (FP-04). A title whose start is 0, duration is 10, and position is center is visible in the center for the first 10 seconds and absent afterward. Pixels of a fully opaque upper layer replace the lower layer; pixels of a partly transparent upper layer blend (FP-07).
- If every layer has an end, the composite’s duration is the maximum end; if any layer has no end, the composite has no duration until the caller assigns one. Frame rate of the composite is the maximum of the layers’ frame rates when those exist. Soundtracks of the layers are mixed into one composite soundtrack with the same starts.
- **Concatenate video.** Playing clip 1 then clip 2 then clip 3 produces a clip whose duration is the sum of the durations (plus any padding between each pair, and plus any inserted transition). Two methods exist, and only those two:
  - **chain:** frames are taken from each clip in turn with no size correction. If sizes differ, each segment keeps its own size. If any clip has a mask, the result has a concatenated mask (opaque where a clip had none).
  - **compose:** the result’s size is the maximum width × maximum height among the clips. Smaller clips appear centered. Padding between clips is allowed; a non-zero padding value does not by itself switch the method from chain to compose. Negative padding overlaps the end of one clip with the start of the next. An optional transition clip is inserted between each pair.
  Concatenation requires every input to have a duration. The result’s frame rate is the maximum of the inputs’ frame rates. Soundtracks are concatenated in the same order.
- **Grid.** A rectangular array of clips is laid out in rows and columns, each cell the size of the largest clip in that row/column; smaller clips are centered in their cell. The result is one clip whose width is the sum of column widths and whose height is the sum of row heights.
- **Audio overlay.** A composite audio clip plays its members together according to each member’s start. Duration is the maximum end. Channel count is the maximum channel count. Sample rate is the maximum sample rate among members that have one.
- **Audio concatenate.** Members play one after another. Duration is the sum of durations. Starts are 0, then the running sum of previous durations. Sample rate and channel count are the maxima.

**Boundary / error behavior:**

- Concatenating video with a method other than chain or compose does not succeed.
- Writing a grid or overlay of stills that still have no duration does not succeed (FP-01 / FP-09), even if size is known.
- Writing a composite that has duration but no frame rate, and without supplying a frame rate at write time, does not succeed.

**Verifiable oracle:**

- Success: overlay of a full-size red clip and a smaller green clip placed at center is green in the center pixels and red outside them; a half-opacity green overlay on red at t = 0.5 is a blend of red and green, not pure red and not pure green; concatenating a 1-second red clip and a 1-second blue clip is red at t = 0.5 and blue at t = 1.5 with duration 2; a 1×3 grid of red, green, and blue clips of equal size has width 3× one clip’s width and shows those three colors left to right; concatenating a 2-second tone and a 5-second tone yields duration 7, with the second tone starting at t = 2.
- Failure / absence: overlay shows only the first clip; concatenation plays all clips at once; grid stacks in time instead of in space; audio concatenate overlaps instead of sequencing; a composite of finite stills encodes without duration having been set.

---

### FP-07: Masks, opacity, and transparency

**Public entry:** Declaring a clip as a mask; attaching a mask to a video clip; setting opacity; converting a color clip to a mask and a mask to a color clip; PNG/GIF alpha as a mask (FP-02, FP-03). Masks are what overlay and PNG frame export use to decide visibility.

**Normal behavior:**

- A mask clip’s frames are greyscale height × width with values in 0–1. A non-mask clip’s frames are height × width × 3 with values in 0–255. Declaring a clip as a mask or not switches which of those contracts it obeys.
- Attaching a mask to a video clip of the same size makes that mask the visibility map in an overlay (FP-06): pixels where the mask is 1 show the upper clip; where it is 0 the lower clip shows through; in-between values blend. The same mask is written into the alpha channel when saving a PNG frame (FP-09) when alpha is left on (the default).
- Opacity multiplies the existing mask by a factor. Factor 0.5 on a fully opaque clip yields a mask of 0.5; overlay then blends half-and-half with the layer below. Factors outside 0–1 are accepted and scale the mask the same way.
- A color clip with a four-channel color uses the fourth channel as a mask scaled into 0–1 (a fourth channel of 76.5 on the 0–255 picture scale yields a mask near 0.3). Stacking several such layers accumulates coverage: one such layer, then two, then three, are distinguishable at the overlapping pixel (more layers cover more of the background).
- Converting a color clip to a mask uses one channel scaled from 0–255 into 0–1. Converting a mask to a color clip repeats the greyscale value into three 0–255 channels. A clip that is already a mask, converted to a mask, is unchanged; a color clip converted to color is unchanged.
- A PNG still with an alpha layer, loaded with transparency on (default), has that alpha as its mask. Loading with transparency off does not.
- Cross-fade in makes the clip go from fully transparent to fully opaque over a duration. Cross-fade out does the reverse. Overlay of a cross-fading upper clip therefore moves from the lower clip visible to the upper clip visible (or the reverse).

**Boundary / error behavior:**

- A mask-mode solid-color clip does not accept an RGB triple (FP-02).
- Attaching a mask whose size does not match the clip is not a successful same-size attach: overlay visibility is specified only when the mask and the clip share the same size.

**Verifiable oracle:**

- Success: a red clip with a mask that is 1 on the left half and 0 on the right, overlaid on blue, is red on the left and blue on the right; opacity 0.5 on green over red is a blend, not either pure color; a PNG saved from a masked clip has an alpha channel that matches the mask; converting a white color clip to a mask yields values near 1; a four-channel color of alpha 76.5 over a void background has mask near 0.3.
- Failure / absence: masks are ignored and the upper clip fully covers; opacity does not change the overlay; PNG export drops alpha; mask frames are 0–255 three-channel pictures.

---

### FP-08: Built-in effects and caller-defined transformations

**Public entry:** Applying a list of effects to a clip (each effect is a first-class object). The library exposes a **visual-effect catalog** and an **audio-effect catalog**, listed exhaustively below. The caller may also supply a custom effect (an object that, given a clip, returns a modified clip) and three filters: change only time, change only the picture (or sound), or change both as a function of “frame at time” and time. Applying an audio effect to a video clip that has a soundtrack modifies the soundtrack and leaves the picture timing in place unless the effect is a visual one.

**Normal behavior:**

- Applying effects returns a copy (FP-01). Several effects in one list are applied in list order. The same effect object may be applied to several clips; each application behaves independently.
- Multiply-speed, loop, time-mirror, and time-symmetrize also transform the clip’s mask and soundtrack when those exist, so picture, mask, and sound stay aligned. Crop, resize, rotate, horizontal mirror, and vertical mirror transform the mask with the picture and leave the soundtrack’s samples unchanged. Color-only effects (invert, black and white, gamma, multiply color, luminosity and contrast) change the picture and leave the soundtrack’s samples unchanged.
- Blink, slide in, and slide out are observable when the clip is a layer in an overlay (FP-06): blink toggles visibility via the mask, and slide in/out move the clip’s position from or toward one side; the standalone picture is unchanged.
- Time-only filter: a function that maps t to a new time t′ makes the result’s frame at t equal to the source’s frame at t′. A filter that maps t to 2t plays twice as fast. On an animated clip, time-only filters do not rewrite mask or soundtrack unless the caller asks to apply the same time map there. On a still-image clip the picture is unchanged and the time map is applied to mask and soundtrack unless the caller names otherwise.
- Picture-only filter: a function that maps a picture to a picture is run on each frame. Swapping two color channels is visible in the result. On a still-image clip, a picture-only filter yields the same transformed still at every time.
- Joint filter: a function that receives both a way to fetch the source picture at any time and the current time, and returns the picture for that time. A vertical scroll of a fixed window is visible as a time-dependent crop.
- A custom effect receives the clip, may use those filters, and returns a clip. Applying it through the same effect list as built-ins produces the returned clip. A progress-bar effect that reads duration and draws a bar at the bottom is visible at t near duration as a completed bar and at t = 0 as an empty bar.

**Built-in visual effects (complete list):**

1. **Accelerate then decelerate** — playback eases in and out; useful for GIFs.
2. **Black and white** — desaturates the picture.
3. **Blink** — alternates visible and invisible for given on/off durations.
4. **Crop** — keep a rectangle (same outcomes as FP-05 crop).
5. **Cross-fade in** — appear progressively from transparent to opaque over a duration.
6. **Cross-fade out** — disappear progressively from opaque to transparent over a duration.
7. **Even size** — crop so width and height are even.
8. **Fade in** — appear from a color (black by default) over a duration; on a mask, the color is a 0–1 scalar.
9. **Fade out** — fade to a color (black by default) over a duration.
10. **Freeze** — hold the frame at a given time for a duration.
11. **Freeze region** — one rectangle stays frozen while the rest animates.
12. **Gamma correction** — apply a gamma exponent to the picture.
13. **Head blur** — blur a moving region whose position is a function of time.
14. **Invert colors** — each channel is inverted against full scale, so a red (255, 0, 0) pixel becomes (0, 255, 255).
15. **Loop** — repeat the clip; when a repeat count or a total duration is given, duration becomes that looped length, otherwise the result has no duration (infinite loop).
16. **Luminosity and contrast** — add a luminosity offset and a contrast factor.
17. **Make loopable** — fade the end into the beginning so a loop is seamless.
18. **Margin** — add a colored (or transparent) border around the frame, growing the size.
19. **Masks AND** — pixelwise minimum of two masks.
20. **Mask from color** — build a transparency mask where the picture matches a given color (with a tolerance).
21. **Masks OR** — pixelwise maximum of two masks.
22. **Mirror horizontally** — flip left-right (mask too, by default).
23. **Mirror vertically** — flip top-bottom (mask too, by default).
24. **Multiply color** — multiply RGB by a factor.
25. **Multiply speed** — play faster or slower by a factor, or fit a final duration; duration changes accordingly. Soundtrack and mask follow.
26. **Painting** — posterize toward a painted look.
27. **Resize** — same outcomes as FP-05 resize.
28. **Rotate** — same outcomes as FP-05 rotate.
29. **Scroll** — move the picture horizontally and/or vertically (for example end credits).
30. **Slide in** — the clip enters from left, right, top, or bottom over a duration.
31. **Slide out** — the clip exits toward one of those four sides over a duration.
32. **Super-sample** — replace the frame at t by the mean of N equally spaced nearby frames.
33. **Time mirror** — play the clip backward.
34. **Time symmetrize** — play forward then backward; duration doubles.

**Built-in audio effects (complete list):**

1. **Delay** — repeat the sound at a constant interval, each repeat quieter by a factor, a given number of times.
2. **Audio fade in** — from silence to full over a duration.
3. **Audio fade out** — from full to silence over a duration.
4. **Audio loop** — repeat the sound a given number of times or out to a given duration; duration becomes that looped length.
5. **Normalize** — scale volume so the peak reaches full scale.
6. **Multiply stereo volume** — scale left and right channels by independent factors.
7. **Multiply volume** — scale volume by a factor, optionally only between two time values. Applies to an audio clip, or to a video clip’s soundtrack. Factor 0.8 yields samples 0.8 times the original; factor 0 silences.

**Boundary / error behavior:**

- Multiply speed without a factor and without a final duration does not succeed.
- Looping a clip that has no duration does not succeed.
- Audio loop without a repeat count and without a total duration does not succeed.
- Time mirror and time symmetrize require a duration.
- Slide in/out require a side among left, right, top, and bottom.
- An audio effect on a video clip that has no soundtrack leaves the video clip’s picture unchanged and does not invent samples.

**Verifiable oracle:**

- Success: invert-colors on a red (255, 0, 0) clip yields (0, 255, 255) at a sampled pixel; mirror-horizontal on an asymmetric picture swaps left and right pixels; multiply-speed by 2 on a 4-second clip yields duration 2 and the source’s t = 2 picture at the result’s t = 1; a loop with neither a repeat count nor a total duration has no duration; multiply-volume by 0.5 halves sample amplitude; fade-in from black on a white clip is darker at t near 0 than at t after the fade duration; cross-fade-in overlaid on another clip goes from the lower clip visible to the upper clip visible; a picture-only filter that swaps green and blue is visible in the result; a custom effect that paints a progress bar shows a longer bar at late t than at t = 0.
- Failure / absence: applying an effect mutates the original; invert does not change channels; speed change does not change duration; volume scale does not change samples; the catalogs above are missing members; a custom effect cannot be applied through the same effect list as built-ins.

---

### FP-09: Encode clips to video, audio, GIF, and images

**Public entry:** Writing a video clip to a video file; writing an audio clip to an audio file; writing a video clip to an animated GIF; writing every frame to a numbered image sequence; saving one frame to an image file. Video and audio file write use the FFmpeg encoder (mandatory substrate). GIF write, image-sequence write, and still-frame write do not require FFmpeg; they use the still-image writer. This feature **does not** treat a hand-built container, a renamed dummy file, or an in-memory fake as success.

**Normal behavior:**

- **Video file.** A finite video clip with a frame rate (on the clip or supplied at write time) is encoded to the path the caller names. After a successful write, that path is a non-empty media file that FFmpeg can open. Loading it (FP-03) yields a clip whose duration matches the source (within ordinary muxer tolerance), whose size matches, and whose frames match the source frames (within ordinary lossy-codec tolerance). If the clip has a soundtrack and audio is left on (the default), the file contains that soundtrack. Audio may be turned off, or replaced by naming a separate audio file as the soundtrack.
- Default video codec by extension, when the caller does not name a codec: mp4 and mkv use libx264; ogv uses libtheora; webm uses libvpx; mov uses libx264. Extension avi has no default codec; the caller must name one. Default audio codec is libmp3lame, except ogv and webm which default to libvorbis. The caller may override codec, bitrate, audio bitrate, pixel format, thread count, and the compression preset. Preset is one of: ultrafast, superfast, veryfast, faster, fast, medium (default), slow, slower, veryslow, placebo. Preset changes file size and encode time, not the documented picture content.
- **Audio file.** A finite audio clip is encoded to the path the caller names. Default codec by extension: mp3 uses libmp3lame; ogg uses libvorbis; wav uses 16-bit PCM (pcm_s16le); m4a uses the AAC encoder libfdk_aac; flac uses FLAC. For mp3, ogg, wav, and flac, loading the file reproduces the samples within ordinary codec tolerance. Writing to m4a with that default, or with that encoder named, is the unknown-codec case below: no non-empty media file that FFmpeg can open, even if the write call returns; the same clip still writes an openable wav, mp3, ogg, or flac.
- **GIF.** A finite video clip with a frame rate is written as an animated GIF. The file exists and is non-empty. Playback length matches duration at that frame rate. An optional loop count is stored in the GIF. GIF write iterates ordinary color frames; it does not store the clip’s mask as GIF transparency (mask-as-alpha is PNG frame save, FP-07).
- **Image sequence.** A finite clip with a frame rate is written as one image per frame, using a name pattern with an integer placeholder (for example a three-digit index and a PNG extension). The write returns the list of paths; each path exists; the first image matches the frame at t = 0; the count of files matches the number of frames. When a mask is present and alpha is left on (the default), PNG sequences include that mask as alpha; turning alpha off omits it.
- **Single frame.** Saving the frame at a time value writes an image file whose pixels match the clip’s picture at that time. Time 0 is the default. If a mask is present and alpha is requested (the default), PNG alpha matches the mask (0 maps to fully transparent, 1 to fully opaque). Turning alpha off writes the picture without that alpha.
- When a video file is written with a soundtrack, the product muxes sound into the video file. By default, after a successful write, no leftover companion audio file remains next to the video. The caller may name a companion audio path and may ask to keep it; then that path exists after write and contains the soundtrack.

**Boundary / error behavior:**

- A clip with no duration does not encode to video, GIF, or an image sequence. The failure identifies that duration is missing.
- A clip with no frame rate, and no frame rate supplied at write time, does not encode to video, GIF, or an image sequence. The failure identifies that frame rate is missing.
- A video extension with no default codec and no caller-supplied codec does not succeed. The failure identifies that a codec must be supplied.
- A codec name FFmpeg does not know does not produce a non-empty media file that FFmpeg can open. The public write entry may return as a completed call for that input; that return is not a successful encode.
- When the FFmpeg binary is missing, disabled, or the configured path is not invocable, video and audio file write do not succeed (negative control). A zero-byte file, if any, is not a successful encode.
- GIF, image-sequence, and still-frame write do not require FFmpeg. Still-frame write does not require duration or a frame rate.

**Verifiable oracle:**

- Success: a 16×16 red color clip with duration 0.2 s and 10 fps, written to MP4, produces a non-empty file; loading that file yields a clip whose first frame is red (within lossy tolerance) and whose duration is about 0.2 s; the same clip written with audio off has no soundtrack; a 2-second generated tone written to WAV loads back with matching duration and samples; a GIF path exists after GIF write; an image sequence of a 0.04 s clip at the clip’s frame rate produces one PNG per frame and the first PNG matches t = 0; saving a frame of a masked clip to PNG has alpha matching the mask.
- Failure / absence: write returns success without creating a media file; the file cannot be opened as video; frames do not match the source clip; encode succeeds when FFmpeg has been deliberately disabled in an isolated subprocess (negative control for video/audio files); a still with no duration is encoded as if it were finite; an unknown extension encodes without a codec.

This feature is a **mandatory-substrate capability** for video and audio files. Negative control: with FFmpeg unreachable, writing MP4 or WAV must fail. GIF and still-frame write are not substitutes for that proof.
