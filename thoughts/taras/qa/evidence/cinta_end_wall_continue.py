"""Run the unverified end-wall candidate once in the isolated remote container."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[4]
CANDIDATE = '07490d0afeff7a77ef08d336df6593366b91a67d'
BASELINE = 'c95a10a78a568a9580e54b1a18bc27bd9e64f737'
EVIDENCE = '92045a8d3edc03ca79ec5fb59c415a453131b056'
IMAGE = 'sha256:4bf6d623015cc92655d880a3563e8904a5467a082034fb8e3f14d19dccea120a'
REMOTE = '/srv/hackspain-coffee/diagnostics/end-wall-07490d0-16s-attempt1'
PREFIX = 'thoughts/taras/qa/evidence/'


def committed(revision, path):
    return subprocess.check_output(['git', '-C', str(REPO), 'show', f'{revision}:{path}'])


def main():
    with tempfile.TemporaryDirectory(prefix='cinta-end-wall-') as temporary:
        directory = Path(temporary)
        scene = committed(CANDIDATE, 'sim/coffee_sorter/scene.py')
        (directory/'scene.py').write_bytes(scene)
        (directory/'source-revision.txt').write_text(CANDIDATE+'\n')
        runner = committed(EVIDENCE, PREFIX+'cinta_shadow_score.py').decode()
        old = f"SOURCE_REVISION = '{BASELINE}'"
        assert runner.count(old) == 1
        (directory/'cinta_shadow_score.py').write_text(runner.replace(old, f"SOURCE_REVISION = '{CANDIDATE}'"))
        (directory/'cinta_shadow_score_summary.py').write_bytes(committed(EVIDENCE, PREFIX+'cinta_shadow_score_summary.py'))
        expected = json.loads(committed(EVIDENCE, PREFIX+'cinta_shadow_score_expected.json'))
        expected['source_revision'] = CANDIDATE
        expected['files']['sim/coffee_sorter/scene.py'] = hashlib.sha256(scene).hexdigest()
        expected['base_image_source_revision'] = BASELINE
        expected['overlays'] = ['sim/coffee_sorter/scene.py', 'source-revision.txt']
        (directory/'cinta_shadow_score_expected.json').write_text(json.dumps(expected, indent=2)+'\n')
        docker = [
            'docker', 'run', '--rm', '--name', 'cinta-end-wall-07490d0-attempt1',
            '--cpus=2', '--memory=2g', '--pids-limit=128', '--network=none', '--read-only',
            '--env', 'LP_NUM_THREADS=2',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001',
            '--mount', f'type=bind,source={REMOTE}/input,target=/audit-input,readonly',
            '--mount', f'type=bind,source={REMOTE}/output,target=/audit-output',
            '--mount', f'type=bind,source={REMOTE}/runtime.lock,target=/private/tmp/hackspain-coffee-runtime.lock',
            '--mount', f'type=bind,source={REMOTE}/input/scene.py,target=/app/sim/coffee_sorter/scene.py,readonly',
            '--mount', f'type=bind,source={REMOTE}/input/source-revision.txt,target=/app/source-revision.txt,readonly',
            '--entrypoint', 'python', IMAGE, '/audit-input/cinta_shadow_score.py',
            '--repo', '/app', '--expected', '/audit-input/cinta_shadow_score_expected.json',
            '--output', '/audit-output/run.json',
        ]
        script = '#!/bin/sh\nset -eu\n'
        script += f'test ! -e {shlex.quote(REMOTE+"/output/run.json")}\n'
        script += 'exec '+shlex.join(docker)+'\n'
        (directory/'run.sh').write_text(script)
        checksums = ''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name+'\n'
                            for path in sorted(directory.iterdir()))
        (directory/'SHA256SUMS').write_text(checksums)
        root = shlex.quote(REMOTE)
        prepare = (f'test ! -e {root} && install -d -m 0755 {root}/input && '
                   f'install -d -m 0755 -o 10001 -g 10001 {root}/output && '
                   f'install -m 0600 -o 10001 -g 10001 /dev/null {root}/runtime.lock')
        subprocess.run(['ssh', 'hackspain', prepare], check=True)
        subprocess.run(['scp', *[str(path) for path in sorted(directory.iterdir())], f'hackspain:{REMOTE}/input/'], check=True)
        execute = (f'cd {root}/input && sha256sum -c SHA256SUMS && '
                   f'sh ./run.sh > {root}/output/runner.log 2>&1')
        print('Starting one isolated candidate run. This candidate is unverified.', flush=True)
        subprocess.run(['ssh', 'hackspain', execute], check=True)
        print(f'Raw results: hackspain:{REMOTE}/output/run.json')
        print('Captured-case checks and release verification remain separate requirements.')


if __name__ == '__main__':
    main()
