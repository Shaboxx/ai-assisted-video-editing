# Dependencies and media provenance

This repository does not vendor dependency source code, FFmpeg executables, or third-party media.

| Component | Use | License / upstream |
|---|---|---|
| imageio-ffmpeg 0.6.0 | Locate the installed FFmpeg executable and inspect decoded duration | [BSD 2-Clause; copyright 2019–2025 imageio](https://github.com/imageio/imageio-ffmpeg/blob/v0.6.0/LICENSE) |
| FFmpeg | Silence detection, trimming, concatenation, encoding and decoding | [FFmpeg licensing](https://ffmpeg.org/legal.html); terms depend on the installed build |
| Python | Standard library and runtime | [Python license](https://docs.python.org/3/license.html) |

The installed Windows wheel used to generate the committed example reports FFmpeg 7.1 and GPL version 3 or later. Its binary is installed by the dependency, not committed here. Other platforms can ship different FFmpeg builds; inspect the relevant package's notices and the executable's `-L` output. Installing this project does not change any third-party license.

Example visuals, test tones, timing annotations, metadata rows, and reports are original synthetic fixtures. There is no spoken transcript, downloaded recording, identifiable person, or external dataset in the example. The image is a frame extracted from the generated preview. Fixture metadata providers such as `manifest`, `probe`, and `notes` are demonstration labels.

References: [imageio-ffmpeg source and binary distribution](https://github.com/imageio/imageio-ffmpeg), [FFmpeg source and project](https://ffmpeg.org/), and [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html).
