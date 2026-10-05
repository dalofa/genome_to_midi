# GenBank To MIDI

Convert GenBank nucleotide sequences and annotated genes into MIDI, then render MIDI performances as block-based visualizations.

## Install

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

## Usage

### Genome to MIDI

```sh
genbank-to-midi genome.gb --output genome.mid

genbank-to-midi genome.gb --output genome-chords.mid --melody-mode chords --tempo 120

genbank-to-midi genome.gb --output genome-a-minor.mid --scale A-minor
```

The bass track plays one low note per nucleotide. The melody track plays one note or triad per complete codon from each CDS feature, starting when the codon's middle nucleotide plays in the bass track. Gene features are used only when they do not overlap a CDS feature. Reverse-strand features are extracted in their biological orientation by Biopython.

Useful options include `--tempo`, `--bass-duration`, `--codon-duration`, `--bass-root`, `--melody-root`, `--melody-mode`, `--melody-octaves`, `--scale`, `--amino-acid-mapping`, `--nucleotide-notes`, `--arpeggiate`, and the General MIDI program options. Named major and minor scales are supported, such as `A-minor` or `C-major`. When a scale is provided, out-of-scale melody notes are omitted; in chord mode, tones are filtered individually and an empty chord is skipped. With `--amino-acid-mapping`, synonymous codons share the same melody note or chord, and stop codons are skipped. With `--nucleotide-notes`, absolute MIDI pitches can be assigned to each base using integers or note names, for example `A=A2,C=C3,G=G3,T=F#3`. Standard MIDI numbering is used (`C-1=0`, `C4=60`), with sharps and flats supported. With `--arpeggiate`, chord tones play in ascending order within each codon duration. With `--melody-octaves N`, melody roots are wrapped into `N` octaves above `--melody-root`.

MIDI files contain note events and instrument program numbers, not literal oscillator definitions. The default programs approximate the requested triangle-wave bass and square-wave lead; the actual timbre depends on the synthesizer used for playback.

### MIDI to visualization

The visualization command maps MIDI note events onto a time-by-pitch canvas. Time runs from left to right, pitch runs from low at the bottom to high at the top, and note duration controls each block's width. Pitch selects a palette range, while track and channel identity apply a deterministic color offset so notes in different channels remain visually distinct.

Create a palette file with one six-digit hex color per line. Lines beginning with `;` or `//`, as well as blank lines, are ignored:

```text
#000000
#FF0040
#00FF80
#0080FF
```

Render one PNG or SVG. The format is inferred from the output extension, or can be set explicitly with `--format`:

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

The default image size is 1024 by 1024 pixels. To add a small amount of bounded variation, use `--randomness` from `0` to `1`. Use `--seed` when you want the same variation reproduced later:

```sh
midi-to-visualization genome.mid \
	--palette palette.txt \
	--output genome-variation.png \
	--randomness 0.25 \
	--seed 42
```

Randomness slightly changes block placement and palette selection. With the default `--randomness 0`, output is unchanged. The visualizer preserves the timing stored in the MIDI file; it does not quantize or modify the MIDI.

Run tests with:

```sh
pytest
```
