"""Observe legacy labels and native outcomes on one unchanged continuous run."""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[variable] = '1'

SOURCE_REVISION = 'c95a10a78a568a9580e54b1a18bc27bd9e64f737'
MODEL_HASH = 'd793e25a3662585eda545cbe0dc84796d9fdd2e0787bdd89a10bfb441ed861ad'
SECONDS = 16.0
SEED = 8
OLD_RETIRE_GRACE_S = 0.5
LOCK = Path('/private/tmp/hackspain-coffee-runtime.lock')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(repo, expected_path):
    expected = json.loads(expected_path.read_text())
    if expected['source_revision'] != SOURCE_REVISION:
        raise ValueError('The manifest does not identify the accepted source.')
    actual = {name: sha(repo/name) for name in expected['files']}
    if actual != expected['files']:
        raise ValueError('The source, preset, or model differs from the reviewed manifest.')
    revision_file = repo/'source-revision.txt'
    if revision_file.is_file() and revision_file.read_text().strip() != SOURCE_REVISION:
        raise ValueError('The image revision differs from the accepted source.')
    preset = json.loads((repo/'sim/coffee_sorter/configs/continuous_demo.json').read_text())
    if preset['mode'] != 'continuous' or preset['seed'] != SEED:
        raise ValueError('The diagnostic requires the unchanged continuous seed 8 preset.')
    if preset['requested_rate'] != 500.0 or preset['jet_force_n'] != .06:
        raise ValueError('The feed rate or jet force differs from the accepted preset.')
    if preset['policy']['lead_s'] != .0015 or preset['layout']['timestep'] != .001:
        raise ValueError('The lead or timestep differs from the accepted preset.')
    if tuple(preset['layout'][key] for key in ('n_ellipsoid', 'n_half', 'n_box', 'n_capsule')) != (400, 48, 20, 20):
        raise ValueError('The pool differs from the accepted preset.')
    if sha(repo/'sim/coffee_sorter/models/live_green_arabica.joblib') != MODEL_HASH:
        raise ValueError('The model differs from the accepted initial model.')
    return expected


def observe_legacy(row, position, now, layout):
    """Apply the old predicates to current positions without changing the simulator."""
    if row['old_retired_s'] is not None:
        return
    x, y, z = (float(value) for value in position)
    if row['old_label'] is None and x >= layout.split_x:
        row['old_label'] = 'accept' if z > layout.split_z else 'reject'
        row['old_label_s'] = now
        row['old_label_position'] = [x, y, z]
        row['old_label_reason'] = 'splitter_crossing'
    expired = row['old_label_s'] is not None and row['old_label_s'] + OLD_RETIRE_GRACE_S <= now
    reasons = []
    if x > layout.split_x + .16:
        reasons.append('downstream_x')
    if z < layout.belt_z - .44:
        reasons.append('floor_height')
    if x < 0 and abs(y) > layout.belt_w / 2 + .03:
        reasons.append('upstream_lateral_escape')
    if z < .05:
        reasons.append('low_z')
    if expired:
        reasons.append('resolved_grace_elapsed')
    if reasons:
        if row['old_label'] is None:
            row['old_label'] = 'spilled'
            row['old_label_s'] = now
            row['old_label_position'] = [x, y, z]
            row['old_label_reason'] = 'old_retirement_without_crossing'
        row['old_retired_s'] = now
        row['old_retirement_reasons'] = reasons


def run(repo, result):
    sys.path.insert(0, str(repo/'sim/coffee_sorter'))
    from engine import Engine
    from rolling_scores import SETTLING_SECONDS
    import mujoco
    import numpy as np

    if SETTLING_SECONDS != 1.1:
        raise ValueError('The native settling deadline differs from 1.1 seconds.')
    rows, samples = {}, []
    result['rows'] = rows
    result['samples'] = samples
    engine = None
    state = 'engine_construction'
    try:
        engine = Engine(repo/'sim/coffee_sorter/configs/continuous_demo.json')
        sim = engine.sim
        if engine.model_version != MODEL_HASH or not engine.policy_version.startswith('5acba1d1'):
            raise ValueError('The Engine model or policy identity differs from the accepted configuration.')
        result['identity'].update(model_sha256=engine.model_version, policy_sha256=engine.policy_version,
                                  packages=engine.packages, engine_source_sha256=engine.source_hashes)
        result['configuration'] = {'duration_s': SECONDS, 'seed': SEED, 'settling_s': SETTLING_SECONDS,
                                   'requested_rate': sim.rate, 'timestep': sim.dt,
                                   'old_retire_grace_s': OLD_RETIRE_GRACE_S}
        original_spawn, original_step, original_park = sim.spawn, sim.step, sim._park

        def spawn(spec=None):
            bean = original_spawn(spec)
            if bean is not None:
                qa, va = sim.body_qpos[bean.body], sim.body_qvel[bean.body]
                rows[bean.uid] = {
                    'uid': int(bean.uid), 'class': bean.cls, 'shape': sim.class_by_name[bean.cls].shape,
                    'spawn_s': float(bean.spawn_t), 'required_reject': bean.cls in engine.reject_classes,
                    'mass_kg': float(bean.mass), 'axes_m': bean.axes.tolist(),
                    'initial_pose': sim.data.qpos[qa:qa+7].tolist(),
                    'initial_velocity': sim.data.qvel[va:va+6].tolist(),
                    'old_label': None, 'old_label_s': None, 'old_retired_s': None,
                    'native_outcome': None, 'native_s': None, 'retired_s': None, 'jet_hits': 0,
                }
            return bean

        def step():
            now = float(sim.data.time)
            # New births occur upstream. They cannot reach any old predicate in their birth step.
            for body, bean in sim.bean_of.items():
                if rows[bean.uid]['old_retired_s'] is None:
                    qa = sim.body_qpos[body]
                    observe_legacy(rows[bean.uid], sim.data.qpos[qa:qa+3], now, sim.L)
            return original_step()

        def park(body):
            bean = sim.bean_of[body]
            row = rows[bean.uid]
            row.update(native_outcome=bean.outcome, native_s=bean.resolved_t,
                       retired_s=float(sim.data.time), jet_hits=int(bean.jet_hits),
                       native_position=bean.last_pos)
            return original_park(body)

        sim.spawn, sim.step, sim._park = spawn, step, park
        started, cpu_started = time.perf_counter(), time.process_time()
        next_sample = .5
        peak_active = 0
        state = 'simulation'
        while sim.data.time < SECONDS - sim.dt / 2:
            engine.step()
            peak_active = max(peak_active, sim.n_active())
            if sim.data.time >= next_sample - sim.dt / 2:
                now = float(sim.data.time)
                ages = [now-bean.spawn_t for bean in sim.bean_of.values()]
                samples.append({
                    'time_s': now, 'spawned': int(sim.n_spawned), 'starved': int(sim.starved),
                    'active': int(sim.n_active()),
                    'active_by_shape': {shape: len(pool)-len(sim.free[shape]) for shape, pool in sim.pools.items()},
                    'free_by_shape': {shape: len(pool) for shape, pool in sim.free.items()},
                    'old_retired_still_active': sum(rows[bean.uid]['old_retired_s'] is not None for bean in sim.bean_of.values()),
                    'overdue_active': sum(age > SETTLING_SECONDS for age in ages),
                    'oldest_active_age': max(ages, default=0.0),
                })
                print(json.dumps({'progress': samples[-1]}), flush=True)
                next_sample += .5
        result['execution'].update(wall_s=time.perf_counter()-started, cpu_s=time.process_time()-cpu_started,
                                   peak_active=peak_active, peak_rss_raw=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                                   peak_rss_unit='KiB on Linux, bytes on macOS')
        state = 'final_observation'
        now = float(sim.data.time)
        contacts = {}
        for index, contact in enumerate(sim.data.contact[:sim.data.ncon]):
            force = np.zeros(6)
            mujoco.mj_contactForce(sim.model, sim.data, index, force)
            if force[0] <= 0:
                continue
            for target, other in ((contact.geom1, contact.geom2), (contact.geom2, contact.geom1)):
                body = sim.collision_body.get(int(target))
                if body not in sim.bean_of:
                    continue
                contacts.setdefault(body, []).append({
                    'other_geom': mujoco.mj_id2name(sim.model, mujoco.mjtObj.mjOBJ_GEOM, int(other)),
                    'other_geom_id': int(other), 'target_geom_id': int(target),
                    'normal_force_n': float(force[0]), 'distance_m': float(contact.dist),
                    'normal_world_raw': contact.frame[:3].tolist(),
                    'geom_ids': [int(contact.geom1), int(contact.geom2)],
                    'solve_time_s': now-sim.dt,
                })
        active = []
        for body, bean in sim.bean_of.items():
            qa, va = sim.body_qpos[body], sim.body_qvel[body]
            rows[bean.uid]['jet_hits'] = int(bean.jet_hits)
            active.append({'uid': int(bean.uid), 'age_s': now-bean.spawn_t,
                           'pos': sim.data.qpos[qa:qa+3].tolist(),
                           'velocity': sim.data.qvel[va:va+6].tolist(),
                           'contact_solve_position': sim.data.xpos[body].tolist(),
                           'contacts': contacts.get(body, [])})
        result.update(final_time_s=now, final_active=active, rows=list(rows.values()),
                      rolling_scores=engine.rolling_scores(),
                      capacity={'spawned': int(sim.n_spawned), 'starved': int(sim.starved),
                                'active': int(sim.n_active()), 'peak_active': peak_active,
                                'pool': {shape: len(pool) for shape, pool in sim.pools.items()}},
                      legacy_label_reasons=dict(Counter(row.get('old_label_reason', 'unresolved') for row in rows.values())))
        state = 'summary'
        from cinta_shadow_score_summary import summarize
        result['summary'] = summarize(result)
    except Exception as error:
        result['errors'].append({'stage': state, 'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        if engine is not None:
            try:
                engine.close()
            except Exception as error:
                result['errors'].append({'stage': 'engine_close', 'type': type(error).__name__, 'message': str(error)})
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = {'schema_version': 1, 'errors': [], 'execution': {}, 'identity': {
        'source_revision': SOURCE_REVISION, 'runner_sha256': sha(__file__),
        'summary_runner_sha256': sha(Path(__file__).with_name('cinta_shadow_score_summary.py')),
        'expected_manifest_sha256': sha(args.expected),
    }}
    succeeded = False
    try:
        result['identity']['expected'] = verify_inputs(args.repo, args.expected)
        started = time.perf_counter()
        with LOCK.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result['execution']['lock_wait_s'] = time.perf_counter()-started
            run(args.repo, result)
        result['execution']['lock_released'] = True
        result['identity']['source_unchanged_after_run'] = verify_inputs(args.repo, args.expected) == result['identity']['expected']
        succeeded = True
    except Exception as error:
        if not result['errors']:
            result['errors'].append({'stage': 'validation_or_lock', 'type': type(error).__name__, 'message': str(error)})
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    summary = result.get('summary', {})
    print(json.dumps({'success': succeeded, 'errors': result['errors'], 'output': str(args.output),
                      'scores': summary.get('scores'), 'active': summary.get('active'),
                      'capacity': summary.get('capacity')}), flush=True)
    return 0 if succeeded else 1


if __name__ == '__main__':
    raise SystemExit(main())
