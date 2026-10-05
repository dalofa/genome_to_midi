# GenBank To MIDI

Convert GenBank sequences into MIDI and render MIDI performances as block-based images.

## Install

```sh
git clone https://github.com/dalofa/genome_to_midi
cd genome_to_midi
python -m pip install -e '.[test]'
```

## Commands

### 1. Genome to MIDI

```sh
genbank-to-midi genome.gb --output genome.mid

genbank-to-midi genome.gb --output genome-chords.mid --melody-mode chords --tempo 120

genbank-to-midi genome.gb --output genome-a-minor.mid --scale A-minor
```

The bass track plays one low note per nucleotide. The melody track plays one note or triad per complete codon from each selected CDS or gene feature. Melody notes begin at the codon's first nucleotide and span the codon's three nucleotide positions. Reverse-strand features are extracted in their biological orientation.

Important options:

- `--tempo`: tempo in beats per minute; default `100`.
- `--ticks-per-beat`: MIDI resolution; default `480`.
- `--bass-duration`: bass note length in ticks; default `120`.
- `--codon-duration`: duration used when arpeggiating chords; default `480`.
- `--melody-mode`: `notes` or `chords`.
- `--scale`: named major or minor scale, such as `A-minor` or `C-major`.
- `--amino-acid-mapping`: map synonymous codons to the same melody note and skip stop codons.
- `--nucleotide-notes`: assign absolute MIDI pitches to A, C, G, and T, such as `A=A2,C=C3,G=G3,T=F#3`.
- `--arpeggiate`: play chord tones in sequence within each codon duration.
- `--melody-octaves`: limit melody mapping to the requested number of octaves.
- `--bass-root`, `--melody-root`, `--velocity`, `--bass-program`, `--melody-program`: control pitch, volume, and General MIDI instruments.

When `--scale` is provided, notes outside the scale are moved to the nearest note in that scale. Chord tones are remapped individually; they are not removed for being out of scale. Standard MIDI numbering is used (`C-1=0`, `C4=60`), with sharps and flats supported.

MIDI files contain note events and instrument program numbers, not literal oscillator definitions. The default programs approximate the requested triangle-wave bass and square-wave lead; the actual timbre depends on the synthesizer used for playback.

### 2. MIDI to visualization

The visualization command maps MIDI note events onto a time-by-pitch canvas:

- time runs from left to right;
- pitch runs from low at the bottom to high at the top;
- note duration controls each block's width;
- pitch selects a palette range;
- track and channel apply a deterministic color offset.

Create a palette file with one six-digit hex color per line. Lines beginning with `;` or `//`, as well as blank lines, are ignored:

```text
#000000
#FF0040
#00FF80
#0080FF
```

Render a PNG or SVG. The format is inferred from the output extension, or can be set explicitly with `--format`:

```sh
midi-to-visualization genome.mid \
  --palette palette.txt \
  --output genome.png \
  --width 1024 \
  --height 1024
```

```sh
midi-to-visualization genome.mid \
  --palette palette.txt \
  --output genome.svg \
  --format svg
```

The default image size is 1024 by 1024 pixels. If the output has no extension, PNG is used. To add a small amount of bounded variation, use `--randomness` from `0` to `1`. Use `--seed` when you want the same variation reproduced later:

```sh
midi-to-visualization genome.mid \
  --palette palette.txt \
  --output genome-variation.png \
  --randomness 0.25 \
  --seed 42
```

Randomness slightly changes horizontal block placement and palette selection. With the default `--randomness 0`, output is unchanged. The visualizer preserves the timing stored in the MIDI file; it does not quantize or modify the MIDI.

SVG output contains one scalable rectangle per note, plus a black background rectangle. PNG and SVG use the same layout and color mapping.

Run tests with:

```sh
pytest
```
