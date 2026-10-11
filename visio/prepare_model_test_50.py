"""Reproduce the 25 matched VidTIMIT/DeepfakeTIMIT pairs; never select on scores.

Run from the repository root with python -m visio.prepare_model_test_50.
Media, archives and local manifests stay in ignored local-data/. No model changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

from .core import file_hash

SEED = 20261011
# Both identities of each of the three previously examined DeepfakeTIMIT pairs.
EXCLUDED = {"fadg0", "fram1", "faks0", "fedw0", "fcft0", "fdrd1"}
BASE = Path("visio/local-data/model-test-50")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def download(url, path, entry=None):
    def valid():
        if not path.is_file():
            return False
        if entry is None:
            return True
        algorithm, digest = entry["checksum"].split(":")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, algorithm).hexdigest()
        return path.stat().st_size == entry["size"] and actual == digest

    if not valid():
        partial = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        partial.replace(path)
        if not valid():
            raise ValueError(f"Source checksum mismatch: {path.name}")
    return path


def probe(path):
    return json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,nb_read_frames,avg_frame_rate,duration",
        "-of", "json", str(path)], timeout=60))["streams"][0]


def transcode(inputs, dest):
    # Same final codec, rate, dimensions and quality for both labels. Prior
    # compression differs in the source datasets and remains a limitation.
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "2",
        *inputs, "-map", "0:v:0", "-an", "-vf", "setpts=N/(25*TB)",
        "-r", "25", "-c:v", "libx264", "-threads", "2", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dest)],
        check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True,
                        help="Existing seven-clip development manifest (not part of the 50 test clips)")
    parser.add_argument("--output", type=Path, default=BASE)
    args = parser.parse_args()
    base = args.output.resolve()
    sources = base / "sources"
    clips_dir = base / "clips"
    sources.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(exist_ok=True)
    if (base / "dataset.json").exists():
        raise SystemExit("dataset.json already exists; use another output directory to rebuild")

    records = {}
    for record in ("4068245", "158963"):
        path = download(f"https://zenodo.org/api/records/{record}", sources / f"zenodo-{record}.json")
        records[record] = json.loads(path.read_text())
    fake_entry = next(f for f in records["4068245"]["files"] if f["key"] == "DeepfakeTIMIT.tar.gz")
    archive = download("https://zenodo.org/records/4068245/files/DeepfakeTIMIT.tar.gz?download=1",
                       sources / fake_entry["key"], fake_entry)
    real_entries = {f["key"]: f for f in records["158963"]["files"]}
    provenance = {
        "seed": SEED, "excluded_subjects": sorted(EXCLUDED),
        "selection_rule": "25 of 26 remaining subjects, seeded sample of sorted IDs; sa1, higher_quality only",
        "sources": ["https://zenodo.org/records/4068245", "https://zenodo.org/records/158963"],
        "license": "CC-BY-NC-ND-4.0 in both Zenodo records; derived clips for local research only",
        "archive_sha256": file_hash(archive), "archive_checksum": fake_entry["checksum"],
        "ffmpeg_version": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
        "transformation": "Full sa1 sequence, no audio, 25 fps, H264 CRF18 yuv420p, normalized timestamps; no crop/resize",
        "pairs": [],
    }
    clips = []
    with tarfile.open(archive) as tar:
        candidates = {m.name.split("/")[2]: m for m in tar.getmembers()
                      if m.isfile() and m.name.startswith("DeepfakeTIMIT/higher_quality/")
                      and "/sa1-video-" in m.name and m.name.endswith(".avi")}
        subjects = sorted(random.Random(SEED).sample(sorted(set(candidates) - EXCLUDED), 25))
        selection = [{"index": i, "subject": subject,
                      "donor": candidates[subject].name.split("-")[-1][:-4],
                      "member": candidates[subject].name, "utterance": "sa1"}
                     for i, subject in enumerate(subjects, 1)]
        if any(p["donor"] in EXCLUDED for p in selection):
            raise ValueError("Donor identity overlaps previous development clips")
        save(base / "selection.json", dict(seed=SEED, excluded_subjects=sorted(EXCLUDED), pairs=selection))
        for pair in selection:
            i, subject = pair["index"], pair["subject"]
            print(f"Preparing pair {i}/25 ({subject})", flush=True)
            entry = real_entries[f"{subject}.zip"]
            url = f"https://zenodo.org/records/158963/files/{subject}.zip?download=1"
            # Sequential downloads, as requested by the VidTIMIT publisher.
            real_archive = download(url, sources / entry["key"], entry)
            fake_source = sources / f"attack-{i:02d}.avi"
            with tar.extractfile(candidates[subject]) as source, fake_source.open("wb") as dest:
                shutil.copyfileobj(source, dest)
            fake_input_frames = int(probe(fake_source)["nb_read_frames"])
            with tempfile.TemporaryDirectory(prefix="frames-", dir=base) as tmp:
                with zipfile.ZipFile(real_archive) as z:
                    frames = sorted(n for n in z.namelist()
                                    if n.startswith(f"{subject}/video/sa1/")
                                    and n.rsplit("/", 1)[-1].isdigit())
                    if not 50 <= len(frames) <= 500:
                        raise ValueError(f"Unexpected frame count: {subject}: {len(frames)}")
                    frame_hash = hashlib.sha256()
                    for idx, name in enumerate(frames):
                        data = z.read(name)  # CRC checked; no archive path is used for extraction.
                        frame_hash.update(data)
                        (Path(tmp) / f"{idx:04d}.jpg").write_bytes(data)
                real_output = clips_dir / f"real-{i:02d}.mp4"
                fake_output = clips_dir / f"attack-{i:02d}.mp4"
                transcode(["-framerate", "25", "-i", f"{tmp}/%04d.jpg"], real_output)
                transcode(["-i", str(fake_source)], fake_output)
            infos = {"real": probe(real_output), "attack": probe(fake_output)}
            for label, output in (("real", real_output), ("attack", fake_output)):
                info = infos[label]
                if not (info["width"] == 512 and info["height"] == 384
                        and 2 <= float(info["duration"]) <= 20
                        and int(info["nb_read_frames"]) == (len(frames) if label == "real" else fake_input_frames)):
                    raise ValueError(f"Unexpected dimensions, duration or frame count: {output}: {info}")
                clips.append(dict(
                    id=f"timit-{label}-{i:02d}", path=str(output.relative_to(base)),
                    sha256=file_hash(output), source_id=f"vidtimit-{subject}-sa1",
                    # Pair group includes both swapped identities, also for the real clip.
                    person_id="timit-pair-" + "-".join(sorted([subject, pair["donor"]])),
                    split="test", label=label, attack_kind="face_swap" if label == "attack" else None,
                    authorized=True, permission="Public publisher release for noncommercial research; "
                    "CC-BY-NC-ND-4.0 per Zenodo record; local evaluation requested by user; "
                    "no redistribution of derived video. Sources and attribution in provenance.json."))
            provenance["pairs"].append(pair | dict(
                real_url=url, real_archive_checksum=entry["checksum"],
                real_archive_sha256=file_hash(real_archive),
                real_frames_sha256=frame_hash.hexdigest(), fake_original_sha256=file_hash(fake_source),
                real_source_frames=len(frames), fake_source_frames=fake_input_frames,
                media=infos))
            save(base / "provenance.json", provenance)
            print(f"Ready pair {i}/25: real {len(frames)}, fake {fake_input_frames} frames", flush=True)

    # Keep the old development corpus separate; do not re-evaluate or tune on test.
    pilot = json.loads(args.pilot.read_text())
    dev = []
    for clip in pilot["clips"]:
        item = clip | dict(path=str((args.pilot.resolve().parent / clip["path"]).resolve()), split="dev")
        if clip["label"] == "attack":
            idx = int(clip["id"].split("-")[-1]) - 1
            subject, donor = [("fadg0", "fram1"), ("faks0", "fedw0"), ("fcft0", "fdrd1")][idx]
            item.update(source_id=f"vidtimit-{subject}-sa1",
                        person_id="timit-pair-" + "-".join(sorted([subject, donor])))
        dev.append(item)
    data = dict(schema_version="1.0", claimed_categories=["face_swap"], clips=dev + clips)
    save(base / "dataset.json", data)
    from .benchmark import dataset
    dataset(base / "dataset.json")
    print("Validated: 25 real + 25 attack test clips; old development clips excluded from scoring", flush=True)


if __name__ == "__main__":
    main()
