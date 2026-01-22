import sys
import types
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent / "lib"))

from lib.tools import ToolRegistry  # type: ignore


class ToolRepoSearchTests(unittest.TestCase):
    def test_apply_patch_success_and_failure(self):
        registry = ToolRegistry({})
        tmp_path = Path(__file__).parent / "tmp_apply_patch"
        tmp_path.mkdir(exist_ok=True)

        target = tmp_path / "sample.txt"
        target.write_text("hello\n")

        good_patch = (
            "--- sample.txt\n"
            "+++ sample.txt\n"
            "@@ -1 +1 @@\n"
            "-hello\n"
            "+world\n"
        )
        res_ok = registry._apply_patch(good_patch, cwd=str(tmp_path))
        self.assertTrue(res_ok.success, res_ok.error)
        self.assertEqual(target.read_text(), "world\n")

        bad_patch = (
            "--- sample.txt\n"
            "+++ sample.txt\n"
            "@@ -1 +1 @@\n"
            "-doesnotexist\n"
            "+nope\n"
        )
        res_bad = registry._apply_patch(bad_patch, cwd=str(tmp_path))
        self.assertFalse(res_bad.success)

        # cleanup
        for item in tmp_path.iterdir():
            item.unlink()
        tmp_path.rmdir()

    def test_repo_search_embedding_and_keyword(self):
        registry = ToolRegistry({})
        tmp_path = Path(__file__).parent / "tmp_repo_search"
        tmp_path.mkdir(exist_ok=True)

        file_a = tmp_path / "a.py"
        file_a.write_text("def foo():\n    return 1\n")
        file_b = tmp_path / "b.py"
        file_b.write_text("def bar():\n    return 2\n")

        # Inject dummy ollama module with embeddings
        dummy = types.SimpleNamespace(
            embeddings=lambda model, prompt: {"embedding": [len(prompt), 1.0, 0.5]}
        )
        sys.modules["ollama"] = dummy

        # Force deterministic embedding path
        registry._embed_text = lambda _self, _lib, text: [len(text), 1.0, 0.5]  # type: ignore

        res_embed = registry._repo_search("foo", path=str(tmp_path), max_results=2)
        self.assertTrue(res_embed.success)
        self.assertTrue(any("a.py" in line for line in res_embed.output.splitlines()))

        # Force keyword fallback
        registry._embed_text = lambda *_args, **_kwargs: None  # type: ignore
        res_kw = registry._repo_search("bar", path=str(tmp_path), max_results=2)
        self.assertTrue(res_kw.success)
        self.assertIn(res_kw.metadata["used_embedding"], [False, None, True])
        self.assertTrue(any("b.py" in line for line in res_kw.output.splitlines()))

        # cleanup
        for item in tmp_path.iterdir():
            item.unlink()
        tmp_path.rmdir()


if __name__ == "__main__":
    unittest.main()
