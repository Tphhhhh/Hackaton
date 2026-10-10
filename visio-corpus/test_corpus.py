"""Artificial bytes only: tests of admission, never benchmark media or real permissions."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from corpus import build_manifest, validate


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="visio-corpus-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "media").mkdir()
        (self.root / "private").mkdir()
        proof = b"Artificial test evidence; no real permission asserted."
        (self.root / "private/proof.txt").write_bytes(proof)
        self.proof_hash = hashlib.sha256(proof).hexdigest()

    def clip(self, identifier, split="dev", person=None, source=None, attack=False):
        payload = ("Artificial fixture " + identifier).encode()
        path = "media/" + identifier + ".mp4"
        (self.root / path).write_bytes(payload)
        person, source = person or identifier, source or identifier
        return dict(id=identifier, path=path, split=split, label="attack" if attack else "real",
                    attack_kind="screen" if attack else None, authorized=True,
                    permission="Artificial test fixture only", person_id=person, source_id=source,
                    person_ids=[person], source_ids=[source], sha256=hashlib.sha256(payload).hexdigest(),
                    review=dict(label_verified=True, permission_verified=True, lineage_verified=True,
                                media_verified=True, reviewer="test", reviewed_on="2026-10-10"),
                    provenance=dict(provider="fixture", source_url="fixture:test", original_id=identifier,
                                    acquired_on="2026-10-10", transformations="none",
                                    domain="physical_presentation" if attack else "bona_fide",
                                    presentation_medium="display" if attack else "live_person"),
                    evidence={k:dict(path="private/proof.txt", sha256=self.proof_hash)
                              for k in ("label", "permission", "lineage", "media")})

    def data(self, *clips):
        return dict(schema_version="1.0", clips=list(clips))

    def test_empty_is_auditable_but_not_buildable(self):
        self.assertEqual(validate(self.data(), self.root)["clips"], 0)
        with self.assertRaisesRegex(ValueError, "vide"):
            build_manifest(self.data(), self.root)

    def test_valid_both_partitions_preserve_evidence(self):
        records = [self.clip(f"{s}-{i}", split=s, person=s, attack=bool(i))
                   for s in ("dev", "test") for i in (0, 1)]
        manifest = build_manifest(self.data(*records), self.root)
        self.assertEqual(manifest["claimed_categories"], ["screen"])
        self.assertEqual(manifest["clips"][0]["evidence"], records[0]["evidence"])

    def test_unauthorized_unverified_and_unknown_label_rejected(self):
        c = self.clip("a")
        for field, value in (("authorized", False), ("label", "unknown"), ("attack_kind", "unknown")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(self.data(dict(c, **{field:value})), self.root)
        for flag in ("label_verified", "permission_verified", "lineage_verified", "media_verified"):
            bad = copy.deepcopy(c)
            bad["review"][flag] = False
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                validate(self.data(bad), self.root)

    def test_secondary_person_or_source_cannot_cross_splits(self):
        for field in ("person_ids", "source_ids"):
            a, b = self.clip("a"), self.clip("b", split="test")
            a[field].append("shared-donor")
            b[field].append("shared-donor")
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "Fuite"):
                validate(self.data(a, b), self.root)

    def test_transitive_variant_chain_cannot_cross_splits(self):
        a, b, c = self.clip("a"), self.clip("b"), self.clip("c", split="test")
        b["person_ids"].append("a")
        b["source_ids"].append("c")
        with self.assertRaisesRegex(ValueError, "Fuite"):
            validate(self.data(a, b, c), self.root)

    def test_duplicate_bytes_rejected_within_split(self):
        a, b = self.clip("a"), self.clip("b")
        b.update(path=a["path"], sha256=a["sha256"])
        with self.assertRaisesRegex(ValueError, "dupliqué"):
            validate(self.data(a, b), self.root)

    def test_media_or_evidence_tampering_rejected(self):
        a = self.clip("a")
        (self.root / a["path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256 différent"):
            validate(self.data(a), self.root)
        a = self.clip("a")
        (self.root / "private/proof.txt").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA-256 différent"):
            validate(self.data(a), self.root)

    def test_physical_screen_cannot_be_digital_manipulation(self):
        a = self.clip("a", attack=True)
        a["provenance"]["domain"] = "digital_manipulation"
        with self.assertRaisesRegex(ValueError, "Domaine/support"):
            validate(self.data(a), self.root)

    def test_missing_or_oversized_media_rejected(self):
        a = self.clip("a")
        (self.root / a["path"]).unlink()
        with self.assertRaisesRegex(ValueError, "absent"):
            validate(self.data(a), self.root)
        with (self.root / a["path"]).open("wb") as stream:
            stream.truncate(50 * 1024**2 + 1)
        with self.assertRaisesRegex(ValueError, "Taille"):
            validate(self.data(a), self.root)

    def test_traversal_and_symlink_escape_rejected(self):
        a = self.clip("a")
        a["path"] = "media/../private/proof.txt"
        with self.assertRaisesRegex(ValueError, "traversée"):
            validate(self.data(a), self.root)
        (self.root / "media/out.mp4").symlink_to("/etc/hosts")
        a["path"] = "media/out.mp4"
        with self.assertRaisesRegex(ValueError, "sortant"):
            validate(self.data(a), self.root)

    def test_missing_test_category_rejected(self):
        records = [self.clip("a"), self.clip("b", attack=True), self.clip("c", split="test")]
        with self.assertRaisesRegex(ValueError, "absente de test"):
            build_manifest(self.data(*records), self.root)


if __name__ == "__main__":
    unittest.main()
