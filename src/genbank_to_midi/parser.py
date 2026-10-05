"""GenBank parsing and coding-feature selection."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Iterable

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectedFeature:
    """A coding feature with its strand-aware nucleotide sequence."""

    record_id: str
    feature_id: str
    kind: str
    start: int
    end: int
    strand: int | None
    sequence: str


def _feature_id(feature, kind: str, index: int) -> str:
    qualifiers = feature.qualifiers
    for key in ("locus_tag", "gene", "label", "product"):
        values = qualifiers.get(key)
        if values:
            return str(values[0])
    return f"{kind}-{index}"


def _intervals_overlap(first, second) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def _candidate_features(record: SeqRecord, kind: str) -> list[SelectedFeature]:
    candidates: list[SelectedFeature] = []
    for index, feature in enumerate(record.features, start=1):
        if feature.type != kind or feature.location is None:
            continue
        sequence = str(feature.extract(record.seq)).upper()
        if not sequence:
            continue
        start = int(feature.location.start)
        end = int(feature.location.end)
        candidates.append(
            SelectedFeature(
                record_id=str(record.id),
                feature_id=_feature_id(feature, kind, index),
                kind=kind,
                start=start,
                end=end,
                strand=feature.location.strand,
                sequence=sequence,
            )
        )
    return candidates


def select_melody_features(record: SeqRecord) -> list[SelectedFeature]:
    """Prefer CDS features and use non-overlapping genes as a fallback."""
    cds_features = _candidate_features(record, "CDS")
    gene_features = _candidate_features(record, "gene")
    cds_intervals = [(item.start, item.end) for item in cds_features]
    fallback_genes = [
        gene
        for gene in gene_features
        if not any(_intervals_overlap((gene.start, gene.end), interval) for interval in cds_intervals)
    ]
    return sorted(cds_features + fallback_genes, key=lambda item: (item.start, item.end, item.kind))


def read_records(paths: Iterable[Path]) -> list[SeqRecord]:
    """Read all GenBank records from the supplied files."""
    records: list[SeqRecord] = []
    for path in paths:
        logger.info("Reading GenBank file: %s", path)
        with path.open("r", encoding="utf-8") as handle:
            file_records = list(SeqIO.parse(handle, "genbank"))
        records.extend(file_records)
        logger.info("Read %d record(s) from %s", len(file_records), path)
    return records


def parse_genbank(paths: Iterable[Path]) -> tuple[list[SeqRecord], list[SelectedFeature]]:
    """Read records and select their melody-producing features."""
    records = read_records(paths)
    logger.info("Selecting melody features from %d record(s)", len(records))
    features = [feature for record in records for feature in select_melody_features(record)]
    logger.info("Selected %d melody feature(s)", len(features))
    return records, features
