"""Independently check recorded scores and locate overdue native objects."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys


def inspect(path):
    raw = path.read_bytes()
    if path.suffix == '.gz':
        raw = gzip.decompress(raw)
    data = json.loads(raw)
    assert not data['errors'], data['errors']
    assert data['identity']['source_unchanged_after_run']
    end = data['final_time_s']
    settling = data['configuration']['settling_s']
    rows = data['rows']
    mature = [row for row in rows if row['spawn_s'] <= end - settling]
    by_uid = {row['uid']: row for row in rows}
    scores = {}
    for label, field in [('old', 'old_label'), ('native', 'native_outcome')]:
        reject = [row for row in mature if row['required_reject']]
        keep = [row for row in mature if not row['required_reject']]
        counts = {
            'sorting_accuracy': (sum(row[field] == ('reject' if row['required_reject'] else 'accept') for row in mature), len(mature)),
            'reject_capture': (sum(row[field] == 'reject' for row in reject), len(reject)),
            'keep_loss': (sum(row[field] in ['reject', 'spilled'] for row in keep), len(keep)),
            'spill': (sum(row[field] == 'spilled' for row in mature), len(mature)),
            'unresolved': (sum(row[field] is None for row in mature), len(mature)),
        }
        scores[label] = {}
        for metric, (num, den) in counts.items():
            expected = data['summary']['scores'][label][metric]
            assert (expected['numerator'], expected['denominator']) == (num, den)
            scores[label][metric] = {'numerator': num, 'denominator': den, 'percent': 100 * num / den if den else None}
            if label == 'native' and metric != 'spill':
                engine = data['rolling_scores'][metric]
                assert (engine['numerator'], engine['denominator']) == (num, den)
    assert len(rows) == data['capacity']['spawned']
    assert len(data['final_active']) == data['capacity']['active']
    assert len(rows) == len(by_uid)
    assert len(data['final_active']) + sum(row['native_outcome'] is not None for row in rows) == len(rows)

    active = []
    for item in data['final_active']:
        row = by_uid[item['uid']]
        assert row['native_outcome'] is None
        assert abs(item['age_s'] - (end - row['spawn_s'])) < 1e-9
        active.append({**item, 'class': row['class'], 'shape': row['shape'],
                       'old_label': row['old_label'], 'old_retired_s': row['old_retired_s'],
                       'linear_speed_m_s': math.sqrt(sum(value * value for value in item['velocity'][:3]))})
    overdue = [item for item in active if item['age_s'] > settling]
    overdue.sort(key=lambda item: item['age_s'], reverse=True)
    support = Counter()
    for item in overdue:
        geoms = sorted({contact['other_geom'] or f"unnamed:{contact['other_geom_id']}" for contact in item['contacts']})
        support[' + '.join(geoms) if geoms else 'no_positive_contact'] += 1

    disagreements = Counter()
    failure_modes = Counter()
    false_successes = Counter()
    for row in mature:
        required = 'reject' if row['required_reject'] else 'accept'
        native = row['native_outcome'] or 'unresolved'
        old = row['old_label'] or 'unresolved'
        if old != native:
            disagreements[f'{old} -> {native}'] += 1
        if native != required:
            failure_modes[f'{required} required -> {native}'] += 1
        if old == required and native != required:
            false_successes[f'{old} -> {native}'] += 1
    spill_positions = Counter()
    for row in mature:
        if row['native_outcome'] != 'spilled':
            continue
        x, y, z = row['native_position']
        if x < 0 and abs(y) > .28:
            region = 'upstream_lateral_escape_region'
        elif x > .763:
            region = 'beyond_furthest_end_wall_exterior'
        elif z < .03:
            region = 'near_floor_elsewhere'
        else:
            region = 'other'
        spill_positions[region] += 1
    return {
        'raw_sha256': hashlib.sha256(raw).hexdigest(),
        'independent_checks': 'passed',
        'mature_rows': len(mature), 'scores': scores,
        'disagreement_count': sum(disagreements.values()),
        'disagreements': dict(disagreements),
        'native_failure_modes': dict(failure_modes),
        'old_correct_native_incorrect': dict(false_successes),
        'spill_position_regions': dict(spill_positions),
        'spill_position_note': 'Rounded final positions identify regions, not the exact triggering contact or predicate.',
        'overdue_count': len(overdue),
        'overdue_contact_sets': dict(support),
        'overdue_by_class': dict(Counter(item['class'] for item in overdue)),
        'overdue_by_shape': dict(Counter(item['shape'] for item in overdue)),
        'overdue_speed_below_1mm_s': sum(item['linear_speed_m_s'] < .001 for item in overdue),
        'overdue_ages_over_5s': sum(item['age_s'] > 5 for item in overdue),
        'oldest_10': overdue[:10],
        'samples': data['samples'],
    }


if __name__ == '__main__':
    print(json.dumps(inspect(Path(sys.argv[1])), indent=2, allow_nan=False))
